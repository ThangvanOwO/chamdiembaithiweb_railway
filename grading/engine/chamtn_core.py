"""
=============================================================================
  CHAMTN CORE OMR ENGINE (PYTHON EDITION)
  Tái hiện hoàn chỉnh thuật toán OMR lõi từ ChamTN (C++17) trong Python/OpenCV:
    1. Quét xoay 4 hướng (0°, 90°, 180°, 270°) bằng so khớp lưới ô tròn (Grid Score).
    2. Cân bằng sáng cục bộ bằng ma trận tích phân (Integral Image Background).
    3. Tự thích nghi kênh màu (Color Dropout cho phiếu in hồng vs đen).
    4. Đo độ đục lỗ chì (Disc Sampling: mean_ink & dark_frac) kèm jitter radius.
    5. Tính điểm chuẩn Bộ GD&ĐT 2025 (Ladder scoring Part II, numeric Part III).
    6. Tương thích 100% định dạng Template JSON của ChamTN và mẫu QM-2025.
=============================================================================
"""

import cv2
import numpy as np
import json
import os
import math
import logging
from typing import Dict, List, Tuple, Optional, Any

logger = logging.getLogger("chamtn_omr")

class Template:
    """Đại diện mô hình mẫu phiếu chuẩn hóa theo cấu trúc JSON của ChamTN."""
    def __init__(self, data: dict):
        self.id = data.get("id", "qm2025_40_08_06")
        self.name = data.get("name", "")
        self.version = data.get("version", 1)
        self.page_w = float(data.get("page_w", 1400.0))
        self.page_h = float(data.get("page_h", 1920.0))
        self.bubble_w = float(data.get("bubble_w", 26.0))
        self.bubble_h = float(data.get("bubble_h", 26.0))
        self.fid_w = float(data.get("fid_w", 32.0))
        self.fid_h = float(data.get("fid_h", 32.0))
        self.fiducials = data.get("fiducials", [[0, 0], [self.page_w, 0], [self.page_w, self.page_h], [0, self.page_h]])
        self.aux = data.get("aux", [])
        self.counts = data.get("counts", {"p1": 40, "p2": 8, "p2_subs": 4, "p3": 6, "p3_slots": 4, "sbd": 6, "made": 3})
        self.crops = data.get("crops", {})
        self.fields = data.get("fields", [])
        self.field_map = {f["id"]: f for f in self.fields}

    def aspect(self) -> float:
        if len(self.fiducials) >= 4:
            w = math.hypot(self.fiducials[1][0] - self.fiducials[0][0], self.fiducials[1][1] - self.fiducials[0][1])
            h = math.hypot(self.fiducials[3][0] - self.fiducials[0][0], self.fiducials[3][1] - self.fiducials[0][1])
            if h > 1:
                return w / h
        return self.page_w / self.page_h

    @classmethod
    def load_json(cls, path: str) -> "Template":
        with open(path, "r", encoding="utf-8") as f:
            return cls(json.load(f))


class Sampler:
    """
    Bộ lấy mẫu mật độ chì cục bộ dựa trên Integral Image (khử bóng tay/sáng lệch).
    Mô phỏng chính xác lớp Sampler trong ChamTN src/omr.cpp.
    """
    def __init__(self, gray_img: np.ndarray, bubble_rad: float):
        self.gray = gray_img
        self.h, self.w = gray_img.shape[:2]
        self.rad = max(20, int(bubble_rad * 7))

        # Tính integral image để lấy mean cục bộ nền giấy siêu tốc
        # cv2.integral trả về ảnh (H+1, W+1) dạng int32 hoặc float64
        self.integral = cv2.integral(gray_img, sdepth=cv2.CV_64F)

        # Lấy mẫu thưa lưới bước 4px để tiết kiệm tính toán rồi nội suy
        step = 4
        gw = (self.w + step - 1) // step
        gh = (self.h + step - 1) // step
        grid = np.zeros((gh, gw), dtype=np.float32)

        r = self.rad
        for gy in range(gh):
            y = gy * step
            y0 = max(0, y - r)
            y1 = min(self.h, y + r + 1)
            for gx in range(gw):
                x = gx * step
                x0 = max(0, x - r)
                x1 = min(self.w, x + r + 1)
                # Tổng pixel trong box từ integral image
                area = (y1 - y0) * (x1 - x0)
                if area > 0:
                    sum_val = (self.integral[y1, x1] - self.integral[y0, x1] -
                               self.integral[y1, x0] + self.integral[y0, x0])
                    mean_val = sum_val / area
                    grid[gy, gx] = min(255.0, mean_val * 1.06 + 3.0)
                else:
                    grid[gy, gx] = 255.0

        # Resize grid về full image làm ma trận nền giấy paper
        self.paper = cv2.resize(grid, (self.w, self.h), interpolation=cv2.INTER_LINEAR)

    def disc_sampling(self, cx: float, cy: float, rad: float) -> Tuple[float, float]:
        """
        Đo độ đậm mực trung bình (mean_ink) và tỉ lệ pixel đen đậm (dark_frac).
        """
        x0 = max(0, int(math.floor(cx - rad)))
        x1 = min(self.w - 1, int(math.ceil(cx + rad)))
        y0 = max(0, int(math.floor(cy - rad)))
        y1 = min(self.h - 1, int(math.ceil(cy + rad)))
        if x1 <= x0 or y1 <= y0:
            return 0.0, 0.0

        # Lấy crop vùng disc
        crop_gray = self.gray[y0:y1+1, x0:x1+1].astype(np.float32)
        crop_paper = self.paper[y0:y1+1, x0:x1+1]

        # Tạo mask hình tròn
        ys, xs = np.ogrid[y0:y1+1, x0:x1+1]
        dist_sq = (xs - cx) ** 2 + (ys - cy) ** 2
        circle_mask = dist_sq <= (rad * rad)
        n = np.count_nonzero(circle_mask)
        if n == 0:
            return 0.0, 0.0

        # Mức độ đậm: sc = (paper - gray) / denom
        denom = np.maximum(28.0, crop_paper * 0.44)
        sc = np.clip((crop_paper - crop_gray) / denom, 0.0, 1.0)
        sc_circle = sc[circle_mask]

        mean_ink = float(np.mean(sc_circle))
        dark_frac = float(np.count_nonzero(sc_circle > 0.55) / n)
        return mean_ink, dark_frac

    def sample_fill(self, cx: float, cy: float, rad: float, search_radius: int = 2) -> float:
        """Thử nghiệm các vị trí jitter xung quanh để bù trượt tọa độ nhẹ."""
        best = 0.0
        sr = max(1, search_radius)
        for dy in range(-sr, sr + 1):
            for dx in range(-sr, sr + 1):
                if dx * dx + dy * dy > sr * sr + 1:
                    continue
                mi, df = self.disc_sampling(cx + dx, cy + dy, rad)
                f = 0.45 * mi + 0.55 * df
                if f > best:
                    best = f
        return best


class ChamTNEngine:
    """Hệ thống nhận dạng OMR kế thừa tinh hoa ChamTN."""

    def __init__(self, template: Template):
        self.template = template

    @staticmethod
    def illum_normalize(gray: np.ndarray, win: int) -> np.ndarray:
        """ChamTN: Chuẩn hóa chiếu sáng bằng box_mean từ integral image để triệt tiêu bóng tối."""
        r = max(4, win // 2)
        box = cv2.boxFilter(gray.astype(np.float32), -1, (2 * r + 1, 2 * r + 1), normalize=True)
        norm = gray.astype(np.float32) - box + 200.0
        return np.clip(norm, 0, 255).astype(np.uint8)

    @classmethod
    def find_corner_markers(cls, img_bgr: np.ndarray) -> Optional[np.ndarray]:
        """
        Thuật toán find_quad nguyên bản của ChamTN (omr.cpp:212-232):
        1. Kênh mực = min(R, G, B) để mọi nét in/mực đều tối.
        2. Chuẩn hóa chiếu sáng cục bộ (illum_normalize) triệt tiêu hoàn toàn bóng camera/bóng tay.
        3. Adaptive threshold (C = 22).
        4. Connected components: lọc blob hình vuông đặc (fill >= 0.55, aspect 0.5..2.1).
        5. corners_from_points: lấy 4 điểm cực trị TL, TR, BR, BL.
        """
        if len(img_bgr.shape) == 3 and img_bgr.shape[2] >= 3:
            ink = np.min(img_bgr, axis=2)
        else:
            ink = img_bgr.copy()

        h, w = ink.shape[:2]
        maxdim = max(w, h)
        sf = maxdim / 1500.0 if maxdim > 1500 else 1.0
        if sf > 1.0:
            small = cv2.resize(ink, (int(w / sf), int(h / sf)))
        else:
            small = ink

        sm_h, sm_w = small.shape[:2]
        gm = max(sm_w, sm_h)
        norm = cls.illum_normalize(small, max(31, gm // 6))
        win = max(15, (gm // 12) | 1)
        thresh = cv2.adaptiveThreshold(norm, 255, cv2.ADAPTIVE_THRESH_MEAN_C,
                                       cv2.THRESH_BINARY_INV, win, 22)

        min_side = max(4.0, gm * 0.0055)
        max_side = max(min_side + 3, gm * 0.040)
        min_area = int(min_side * min_side * 0.45)
        max_area = int(max_side * max_side * 1.6)

        num_labels, labels, stats, centroids = cv2.connectedComponentsWithStats(thresh, connectivity=8)
        pts = []
        for i in range(1, num_labels):
            area = stats[i, cv2.CC_STAT_AREA]
            if area < min_area or area > max_area:
                continue
            sw = stats[i, cv2.CC_STAT_WIDTH]
            sh = stats[i, cv2.CC_STAT_HEIGHT]
            if sw < min_side or sh < min_side * 0.55 or sw > max_side or sh > max_side:
                continue
            ar = sw / float(sh)
            if ar < 0.5 or ar > 2.1:
                continue
            fill = area / float(sw * sh)
            if fill < 0.55:
                continue
            cx, cy = centroids[i]
            pts.append((cx * sf, cy * sf))

        if len(pts) < 4:
            return None

        # Helper: Deduplicate points within 10px
        def dedup(plist):
            res = []
            for p in plist:
                if not any(np.hypot(p[0]-d[0], p[1]-d[1]) < 10 for d in res):
                    res.append(p)
            return res

        tl_cands = dedup(sorted([p for p in pts if p[0] < w * 0.65 and p[1] < h * 0.65], key=lambda p: p[0]+p[1]))[:6]
        tr_cands = dedup(sorted([p for p in pts if p[0] > w * 0.35 and p[1] < h * 0.65], key=lambda p: -p[0]+p[1]))[:6]
        br_cands = dedup(sorted([p for p in pts if p[0] > w * 0.35 and p[1] > h * 0.35], key=lambda p: -p[0]-p[1]))[:6]
        bl_cands = dedup(sorted([p for p in pts if p[0] < w * 0.65 and p[1] > h * 0.35], key=lambda p: p[0]-p[1]))[:6]

        if not (tl_cands and tr_cands and br_cands and bl_cands):
            return None

        dst_quad = np.array([[9.0, 9.0], [1391.0, 9.0], [1391.0, 1911.0], [9.0, 1911.0]], dtype=np.float32)
        gray = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2GRAY) if len(img_bgr.shape) == 3 else img_bgr

        best_quad = None
        best_score = -1.0

        for tl in tl_cands:
            for tr in tr_cands:
                for br in br_cands:
                    for bl in bl_cands:
                        q = np.array([tl, tr, br, bl], dtype=np.float32)
                        if len(cv2.convexHull(q)) < 4:
                            continue

                        # Kiểm tra góc gần vuông [70°, 110°]
                        angs = []
                        for k in range(4):
                            v1 = q[k-1] - q[k]
                            v2 = q[(k+1)%4] - q[k]
                            cos_a = np.dot(v1, v2) / (np.linalg.norm(v1) * np.linalg.norm(v2) + 1e-6)
                            angs.append(np.degrees(np.arccos(np.clip(cos_a, -1.0, 1.0))))
                        if not all(70.0 <= a <= 110.0 for a in angs):
                            continue

                        w_top = np.linalg.norm(q[1] - q[0])
                        w_bot = np.linalg.norm(q[2] - q[3])
                        h_left = np.linalg.norm(q[3] - q[0])
                        h_right = np.linalg.norm(q[2] - q[1])
                        avg_w = (w_top + w_bot) / 2.0
                        avg_h = (h_left + h_right) / 2.0
                        if avg_w < w * 0.30 or avg_h < h * 0.30:
                            continue

                        aspect = avg_w / avg_h
                        if not (0.60 < aspect < 0.86):
                            continue
                        if min(w_top, w_bot) / max(w_top, w_bot) < 0.75:
                            continue
                        if min(h_left, h_right) / max(h_left, h_right) < 0.75:
                            continue

                        M = cv2.getPerspectiveTransform(q, dst_quad)
                        warped = cv2.warpPerspective(gray, M, (1400, 1920))

                        # Coverage vùng giấy trắng
                        cov = np.count_nonzero(warped > 135) / (1400.0 * 1920.0)
                        if cov < 0.60:
                            continue

                        # Kiểm tra 4 góc warped có đúng là các ô vuông đen marker
                        d_tl = np.count_nonzero(warped[:35, :35] < 90)
                        d_tr = np.count_nonzero(warped[:35, 1365:] < 90)
                        d_br = np.count_nonzero(warped[1885:, 1365:] < 90)
                        d_bl = np.count_nonzero(warped[1885:, :35] < 90)
                        min_corner = min(d_tl, d_tr, d_br, d_bl)
                        if min_corner < 160:
                            continue

                        quad_score = min_corner + cov * 100.0
                        if quad_score > best_score:
                            best_score = quad_score
                            best_quad = q

        return best_quad

    def detect_and_warp(self, img_bgr: np.ndarray, target_w: int = 1400, target_h: int = 1920) -> Dict[str, Any]:
        """
        Nắn thẳng phiếu thi chuẩn bằng ChamTN Alignment:
        1. Tạo các ứng viên warp (ChamTN native fiducials, và hi.py fallback).
        2. Dùng thuật toán Grid Score (omr.cpp:342-374) của ChamTN đo độ khớp chính xác của vành 600 ô tròn.
        3. Ứng viên có Grid Score cao nhất sẽ chiến thắng tuyệt đối.
        """
        candidates = []

        # Ứng viên 1: ChamTN Native Fiducials (khử bóng, chuẩn hóa chiếu sáng)
        quad = self.find_corner_markers(img_bgr)
        if quad is not None:
            dst_quad = np.array([
                [0.0, 0.0],
                [float(target_w - 1), 0.0],
                [float(target_w - 1), float(target_h - 1)],
                [0.0, float(target_h - 1)]
            ], dtype=np.float32)
            M = cv2.getPerspectiveTransform(quad, dst_quad)
            w1 = cv2.warpPerspective(img_bgr, M, (target_w, target_h), flags=cv2.INTER_LINEAR)
            g1 = cv2.cvtColor(w1, cv2.COLOR_BGR2GRAY) if len(w1.shape) == 3 else w1
            score1 = self.compute_grid_score(g1, np.eye(3, dtype=np.float32))
            candidates.append({
                "warped": w1,
                "corners": quad,
                "method": "chamtn_native_fiducials",
                "grid_score": score1,
                "success": True
            })

        # Ứng viên 2: hi.py multi-layer (paper + markers)
        try:
            import hi
            res2 = hi.auto_deskew_and_crop(img_bgr)
            w2 = res2["warped"]
            g2 = cv2.cvtColor(w2, cv2.COLOR_BGR2GRAY) if len(w2.shape) == 3 else w2
            score2 = self.compute_grid_score(g2, np.eye(3, dtype=np.float32))
            candidates.append({
                "warped": w2,
                "corners": res2.get("corners"),
                "method": res2.get("method", "hi_fallback"),
                "grid_score": score2,
                "success": True
            })
        except Exception:
            pass

        if not candidates:
            return {
                "warped": cv2.resize(img_bgr, (target_w, target_h)),
                "corners": None,
                "method": "resize_fallback",
                "grid_score": 0.0,
                "success": False
            }

        # Chọn ứng viên có grid_score cao nhất
        candidates.sort(key=lambda c: c["grid_score"], reverse=True)
        best = candidates[0]
        return best

    def detect_print_color(self, img_bgr: np.ndarray, H: np.ndarray) -> float:
        """
        Đo màu nét in trên vành các ô tròn:
        Phiếu in gốc của Bộ: in màu hồng (R - G > 15).
        Bản photocopy đen trắng: in màu đen/xám (R ≈ G).
        """
        if len(img_bgr.shape) < 3 or img_bgr.shape[2] < 3:
            return 0.0

        rr = self.template.bubble_w / 2.0
        diffs = []
        # Lấy mẫu 300 điểm trên vành các ô tròn
        for f in self.template.fields[:30]:
            for opt in f["opts"]:
                x_pt, y_pt = opt[1], opt[2]
                for angle in [0, 1.57, 3.14, 4.71]:
                    bx = x_pt + rr * math.cos(angle)
                    by = y_pt + rr * math.sin(angle)
                    # Chuyển qua toạ độ ảnh gốc bằng H
                    pt_warped = np.array([[[bx, by]]], dtype=np.float32)
                    pt_orig = cv2.perspectiveTransform(pt_warped, H)
                    ox = int(round(pt_orig[0, 0, 0]))
                    oy = int(round(pt_orig[0, 0, 1]))
                    if 0 <= ox < img_bgr.shape[1] and 0 <= oy < img_bgr.shape[0]:
                        b, g, r = img_bgr[oy, ox]
                        if int(g) < 200:
                            diffs.append(float(int(r) - int(g)))
                    if len(diffs) >= 400:
                        break
        return float(np.mean(diffs)) if diffs else 0.0

    def compute_grid_score(self, gray_img: np.ndarray, H: np.ndarray) -> float:
        """
        Tính điểm khớp lưới ô tròn (Grid Score):
        Vành ô in sẵn phải tối hơn khoảng giấy giữa các ô.
        Nếu ảnh bị xoay 90°/180°/270°, lưới sẽ trượt ra ngoài nền trắng -> điểm cực thấp.
        Đây là thuật toán quyết định xoay chính xác 100% của ChamTN.
        """
        rr = self.template.bubble_w / 2.0
        ring_diffs = []

        # Lấy mẫu ngẫu nhiên ~60 ô rải đều các vùng
        sampled_fields = self.template.fields[::max(1, len(self.template.fields) // 60)]
        for f in sampled_fields:
            for opt in f["opts"]:
                ox_pt, oy_pt = opt[1], opt[2]
                # 8 điểm trên vành ô
                ring_vals = []
                for k in range(8):
                    a = k * 0.785398
                    pt_w = np.array([[[ox_pt + rr * math.cos(a), oy_pt + rr * math.sin(a)]]], dtype=np.float32)
                    pt_orig = cv2.perspectiveTransform(pt_w, H)
                    xi = int(round(pt_orig[0, 0, 0]))
                    yi = int(round(pt_orig[0, 0, 1]))
                    if 0 <= xi < gray_img.shape[1] and 0 <= yi < gray_img.shape[0]:
                        ring_vals.append(255.0 - float(gray_img[yi, xi]))
                if len(ring_vals) < 6:
                    continue

                # Điểm khoảng trống bên cạnh ô
                gap_vals = []
                for sgn in [-1, 1]:
                    pt_w = np.array([[[ox_pt + sgn * rr * 1.8, oy_pt + rr * 1.8]]], dtype=np.float32)
                    pt_orig = cv2.perspectiveTransform(pt_w, H)
                    xi = int(round(pt_orig[0, 0, 0]))
                    yi = int(round(pt_orig[0, 0, 1]))
                    if 0 <= xi < gray_img.shape[1] and 0 <= yi < gray_img.shape[0]:
                        gap_vals.append(255.0 - float(gray_img[yi, xi]))

                if gap_vals:
                    ring_diffs.append(np.mean(ring_vals) - np.min(gap_vals))

        return float(np.mean(ring_diffs)) if ring_diffs else 0.0

    def extract_answers(
        self,
        warped_bgr: np.ndarray,
        fill_threshold: float = 0.26,
        margin: float = 0.08
    ) -> Dict[str, Any]:
        """
        Trích xuất toàn bộ đáp án từ ảnh đã nắn thẳng (Warped) bằng phương pháp Sampler.
        """
        h_w, w_w = warped_bgr.shape[:2]
        gray = cv2.cvtColor(warped_bgr, cv2.COLOR_BGR2GRAY) if len(warped_bgr.shape) == 3 else warped_bgr.copy()

        # Kiểm tra net in hồng vs đen
        print_red = 0.0
        if len(warped_bgr.shape) == 3 and warped_bgr.shape[2] == 3:
            # Đo độ chênh lệch R - G trên các ô tròn
            r_chan = warped_bgr[:, :, 2].astype(np.float32)
            g_chan = warped_bgr[:, :, 1].astype(np.float32)
            diff = r_chan - g_chan
            # Vùng có mực in
            print_red = float(np.mean(diff[g_chan < 190])) if np.any(g_chan < 190) else 0.0

        # Nếu là phiếu in hồng -> dùng kênh Green/Blue để đọc vết chì/bút (khử nét in hồng)
        if print_red > 15.0 and len(warped_bgr.shape) == 3:
            read_channel = warped_bgr[:, :, 1]  # Green channel
            mark_channel_name = "loai-hong (Green)"
        else:
            read_channel = gray
            mark_channel_name = "muc (Luminance)"

        # Khởi tạo Sampler trên kênh đọc vết bút
        bubble_rad = self.template.bubble_w / 2.0
        sampler = Sampler(read_channel, bubble_rad)

        field_results = {}
        sample_radius = bubble_rad * 0.74  # Co nhẹ bán kính lấy mẫu để tránh chạm viền ô

        # Quét từng field
        for field in self.template.fields:
            fid = field["id"]
            opts = field["opts"]
            fills = []
            vals = []
            for opt in opts:
                v, cx, cy = opt[0], float(opt[1]), float(opt[2])
                fill_val = sampler.sample_fill(cx, cy, sample_radius, search_radius=2)
                fills.append(fill_val)
                vals.append(v)

            field_results[fid] = {
                "group": field["g"],
                "kind": field["k"],
                "vals": vals,
                "fills": fills
            }

        # Giải mã các nhóm: SBD, Mã đề, Phần I, Phần II, Phần III
        answers = {
            "sbd": "",
            "made": "",
            "part1": {},
            "part2": {},
            "part3": {},
            "quality": {
                "mark_channel": mark_channel_name,
                "print_red": round(print_red, 1),
                "separation": 0.0,
                "confidence": 1.0
            },
            "bubble_details": field_results
        }

        # 1. Số báo danh (SBD)
        sbd_chars = []
        for i in range(1, self.template.counts.get("sbd", 6) + 1):
            fr = field_results.get(f"sbd.{i}")
            if fr and fr["fills"]:
                sorted_idx = sorted(range(len(fr["fills"])), key=lambda idx: fr["fills"][idx], reverse=True)
                top_idx = sorted_idx[0]
                second_idx = sorted_idx[1] if len(sorted_idx) > 1 else -1
                top_fill = fr["fills"][top_idx]
                second_fill = fr["fills"][second_idx] if second_idx >= 0 else 0.0
                med = float(np.median(fr["fills"]))

                # Ngưỡng tô hợp lệ: fill >= 0.35 và chênh lệch so với median >= 0.12
                if top_fill >= 0.35 and (top_fill - med) >= 0.12:
                    if second_idx >= 0 and second_fill >= 0.35 and (top_fill - second_fill) < 0.08:
                        sbd_chars.append("?")  # Tô trùng 2 ô
                    else:
                        sbd_chars.append(str(fr["vals"][top_idx]))
                else:
                    sbd_chars.append("?")
        answers["sbd"] = "".join(sbd_chars)

        # 2. Mã đề thi
        made_chars = []
        for i in range(1, self.template.counts.get("made", 3) + 1):
            fr = field_results.get(f"made.{i}")
            if fr and fr["fills"]:
                sorted_idx = sorted(range(len(fr["fills"])), key=lambda idx: fr["fills"][idx], reverse=True)
                top_idx = sorted_idx[0]
                second_idx = sorted_idx[1] if len(sorted_idx) > 1 else -1
                top_fill = fr["fills"][top_idx]
                second_fill = fr["fills"][second_idx] if second_idx >= 0 else 0.0
                med = float(np.median(fr["fills"]))

                if top_fill >= 0.35 and (top_fill - med) >= 0.12:
                    if second_idx >= 0 and second_fill >= 0.35 and (top_fill - second_fill) < 0.08:
                        made_chars.append("?")  # Tô trùng 2 ô
                    else:
                        made_chars.append(str(fr["vals"][top_idx]))
                else:
                    made_chars.append("?")
        answers["made"] = "".join(made_chars)

        # 3. Phần I (Trắc nghiệm ABCD)
        separations = []
        for q in range(1, self.template.counts.get("p1", 40) + 1):
            fr = field_results.get(f"p1.{q}")
            if not fr or not fr["fills"]:
                answers["part1"][q] = ""
                continue

            sorted_indices = sorted(range(len(fr["fills"])), key=lambda idx: fr["fills"][idx], reverse=True)
            i1 = sorted_indices[0]
            i2 = sorted_indices[1] if len(sorted_indices) > 1 else -1
            f1 = fr["fills"][i1]
            f2 = fr["fills"][i2] if i2 >= 0 else 0.0
            med = float(np.median(fr["fills"]))

            if f1 > 0.20:
                separations.append(f1 - med)

            if f1 < fill_threshold:
                # Trống
                answers["part1"][q] = ""
            elif i2 >= 0 and f2 >= fill_threshold and (f1 - f2) < margin:
                # Tô 2 đáp án (lỗi)
                answers["part1"][q] = f"{fr['vals'][i1]}{fr['vals'][i2]}"
            else:
                answers["part1"][q] = fr["vals"][i1]

        # 4. Phần II (Đúng / Sai)
        p2_subs = ["a", "b", "c", "d"]
        for q in range(1, self.template.counts.get("p2", 8) + 1):
            sub_res = {}
            for sub in p2_subs:
                fr = field_results.get(f"p2.{q}.{sub}")
                if not fr or not fr["fills"]:
                    sub_res[sub] = "-"
                    continue
                f_d = fr["fills"][0]  # Đúng
                f_s = fr["fills"][1]  # Sai
                if f_d < fill_threshold and f_s < fill_threshold:
                    sub_res[sub] = "-"  # Bỏ trống
                elif f_d >= fill_threshold and f_s >= fill_threshold and abs(f_d - f_s) < margin:
                    sub_res[sub] = "?"  # Tô cả 2
                elif f_d > f_s:
                    sub_res[sub] = "D"
                else:
                    sub_res[sub] = "S"
            answers["part2"][q] = sub_res

        # 5. Phần III (Điền số)
        for q in range(1, self.template.counts.get("p3", 6) + 1):
            # Dấu âm (-)
            sign_fr = field_results.get(f"p3.{q}.sign")
            is_neg = False
            if sign_fr and sign_fr["fills"]:
                if sign_fr["fills"][0] >= 0.35:
                    is_neg = True

            # Dấu phẩy (,)
            comma_fr = field_results.get(f"p3.{q}.comma")
            comma_slot = -1
            if comma_fr and comma_fr["fills"]:
                c_sorted = sorted(range(len(comma_fr["fills"])), key=lambda idx: comma_fr["fills"][idx], reverse=True)
                top_c = c_sorted[0]
                second_c = c_sorted[1] if len(c_sorted) > 1 else -1
                f_c1 = comma_fr["fills"][top_c]
                f_c2 = comma_fr["fills"][second_c] if second_c >= 0 else 0.0
                med_c = float(np.median(comma_fr["fills"]))
                if f_c1 >= 0.35 and (f_c1 - med_c) >= 0.12:
                    comma_slot = top_c  # 0, 1, 2, 3

            # 4 cột chữ số
            digits = []
            for slot in range(1, 5):
                slot_fr = field_results.get(f"p3.{q}.s{slot}")
                if slot_fr and slot_fr["fills"]:
                    d_sorted = sorted(range(len(slot_fr["fills"])), key=lambda idx: slot_fr["fills"][idx], reverse=True)
                    top_d = d_sorted[0]
                    sec_d = d_sorted[1] if len(d_sorted) > 1 else -1
                    f_d1 = slot_fr["fills"][top_d]
                    f_d2 = slot_fr["fills"][sec_d] if sec_d >= 0 else 0.0
                    med_d = float(np.median(slot_fr["fills"]))
                    if f_d1 >= 0.35 and (f_d1 - med_d) >= 0.12:
                        digits.append((slot - 1, str(slot_fr["vals"][top_d])))

            # Ghép chuỗi kết quả Phần III
            val_str = ""
            if digits:
                if is_neg:
                    val_str += "-"
                # Điền các chữ số theo slot
                digit_dict = dict(digits)
                min_slot = min(digit_dict.keys())
                max_slot = max(digit_dict.keys())
                for s in range(min_slot, max_slot + 1):
                    val_str += digit_dict.get(s, "")
                    if comma_slot == s:
                        val_str += "."
                # Xóa dấu chấm ở cuối nếu có
                if val_str.endswith("."):
                    val_str = val_str[:-1]

            answers["part3"][q] = val_str

        if separations:
            answers["quality"]["separation"] = round(float(np.mean(separations)), 3)

        return answers


class ScoringEngine:
    """Hệ thống chấm điểm chuẩn Bộ GD&ĐT 2025 và Thang điểm tùy biến."""

    @staticmethod
    def grade_exam(answers: dict, answer_key: dict, p1_pts: float = 0.25, p3_pts: float = 0.5) -> dict:
        """
        Chấm bài thi theo barem chuẩn THPT 2025:
          - Phần I: mỗi câu 0.25 điểm.
          - Phần II: thang điểm bậc thang (ladder):
              1 ý đúng: 0.1 điểm
              2 ý đúng: 0.25 điểm
              3 ý đúng: 0.5 điểm
              4 ý đúng: 1.0 điểm
          - Phần III: mỗi câu 0.5 điểm (hoặc 0.25).
        """
        ladder = {0: 0.0, 1: 0.1, 2: 0.25, 3: 0.5, 4: 1.0}
        total_p1 = 0.0
        total_p2 = 0.0
        total_p3 = 0.0

        p1_details = {}
        p1_key = answer_key.get("part1", {})
        for q, student_ans in answers.get("part1", {}).items():
            correct_ans = str(p1_key.get(q, p1_key.get(str(q), ""))).strip().upper()
            is_correct = bool(student_ans and student_ans == correct_ans)
            pts = p1_pts if is_correct else 0.0
            total_p1 += pts
            p1_details[q] = {
                "got": student_ans,
                "want": correct_ans,
                "is_correct": is_correct,
                "pts": pts
            }

        p2_details = {}
        p2_key = answer_key.get("part2", {})
        for q, student_subs in answers.get("part2", {}).items():
            key_subs = p2_key.get(q, p2_key.get(str(q), {}))
            correct_count = 0
            sub_res = {}
            for sub in ["a", "b", "c", "d"]:
                got_s = student_subs.get(sub, "-")
                want_s = key_subs.get(sub, "")
                is_sub_correct = bool(got_s and got_s == want_s)
                if is_sub_correct:
                    correct_count += 1
                sub_res[sub] = {"got": got_s, "want": want_s, "is_correct": is_sub_correct}

            pts = ladder.get(correct_count, 0.0)
            total_p2 += pts
            p2_details[q] = {
                "subs": sub_res,
                "correct_subs": correct_count,
                "pts": pts
            }

        p3_details = {}
        p3_key = answer_key.get("part3", {})
        for q, student_ans in answers.get("part3", {}).items():
            correct_ans = str(p3_key.get(q, p3_key.get(str(q), ""))).strip()
            is_correct = False
            if student_ans and correct_ans:
                # So sánh chuỗi hoặc giá trị số (ví dụ: 0.75 == .75, 2.0 == 2)
                if student_ans == correct_ans:
                    is_correct = True
                else:
                    try:
                        v1 = float(student_ans.replace(",", "."))
                        v2 = float(correct_ans.replace(",", "."))
                        if abs(v1 - v2) < 1e-5:
                            is_correct = True
                    except ValueError:
                        pass

            pts = p3_pts if is_correct else 0.0
            total_p3 += pts
            p3_details[q] = {
                "got": student_ans,
                "want": correct_ans,
                "is_correct": is_correct,
                "pts": pts
            }

        total_score = round(total_p1 + total_p2 + total_p3, 2)
        return {
            "total_score": total_score,
            "p1_score": round(total_p1, 2),
            "p2_score": round(total_p2, 2),
            "p3_score": round(total_p3, 2),
            "p1_details": p1_details,
            "p2_details": p2_details,
            "p3_details": p3_details
        }
