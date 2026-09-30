"""
Test Camera Document Scanner - GradeFlow Mobile Experience
Mô phỏng trải nghiệm quét phiếu trắc nghiệm của APK GradeFlow trên điện thoại / Webcam:
- 4 Khung căn góc ("Đưa 4 ô vuông đen vào khung")
- Cảnh báo góc nghiêng real-time ("⚠️ Giấy nghiêng ~X°")
- Kiểm tra 4 điểm neo đen đã nằm đúng trong khung hay chưa
- Kết nối linh hoạt (Iriun Webcam, DroidCam, IP Cam URL, webcam USB/built-in)
- Tự động / Thủ công chấm bài trực tiếp bằng engine hi.py
- Tự động hỗ trợ Headless Mode nếu opencv-python thiếu GUI (cv2.imshow)

Sử dụng:
  python tests/integration/test_camera_scanner.py              (Tự động tìm Iriun / Camera)
  python tests/integration/test_camera_scanner.py --cam 0      (Dùng webcam index 0)
  python tests/integration/test_camera_scanner.py --cam http://192.168.1.5:8080/video (IP Camera)

Phím tắt (khi mở Cửa sổ GUI):
  [S]   - Chụp và lưu ảnh warped hiện tại
  [C]   - Chấm điểm ngay phiếu hiện tại (gọi hi.py)
  [A]   - Bật / Tắt chế độ Auto-Scan (Tự động chấm khi đúng vị trí)
  [D]   - Debug mode (Xem Otsu, Morph, Canny)
  [ESC] - Thoát
"""

import cv2
import numpy as np
import sys
import os
import time
import argparse
import math
import subprocess
from pathlib import Path

# Thêm đường dẫn tới grading engine
REPO_ROOT = Path(__file__).resolve().parents[2]
ENGINE_DIR = REPO_ROOT / 'grading' / 'engine'
sys.path.insert(0, str(ENGINE_DIR))

# Đảm bảo UTF-8 cho Windows Terminal
if sys.platform == 'win32':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass


def find_camera_source(cam_arg=None):
    """Tìm camera theo argument hoặc tự quét Iriun / DroidCam / Webcam."""
    if cam_arg is not None:
        if str(cam_arg).isdigit():
            idx = int(cam_arg)
            print(f"[CAMERA] Đang thử kết nối camera index={idx}...")
            cap = cv2.VideoCapture(idx, cv2.CAP_DSHOW if sys.platform == 'win32' else cv2.CAP_ANY)
            if cap.isOpened():
                return cap, f"Webcam Index {idx}"
        else:
            print(f"[CAMERA] Đang thử kết nối IP Camera URL: {cam_arg}...")
            cap = cv2.VideoCapture(str(cam_arg))
            if cap.isOpened():
                return cap, f"IP Cam ({cam_arg})"

    try:
        from pygrabber.dshow_graph import FilterGraph
        graph = FilterGraph()
        devices = graph.get_input_devices()
        print("[CAMERA] Các thiết bị camera tìm thấy:")
        for i, name in enumerate(devices):
            print(f"   [{i}] {name}")
            if "iriun" in name.lower() or "droidcam" in name.lower():
                print(f"[CAMERA] -> Ưu tiên chọn: {name} (Index {i})")
                cap = cv2.VideoCapture(i, cv2.CAP_DSHOW)
                if cap.isOpened():
                    return cap, name
    except ImportError:
        pass

    for idx in range(6):
        cap = cv2.VideoCapture(idx, cv2.CAP_DSHOW if sys.platform == 'win32' else cv2.CAP_ANY)
        if cap.isOpened():
            ret, frame = cap.read()
            if ret and frame is not None:
                print(f"[CAMERA] Đã kết nối camera index={idx}")
                return cap, f"Camera #{idx}"
            cap.release()

    return None, "Không tìm thấy Camera"


def order_points(pts):
    """Sắp xếp 4 điểm theo thứ tự: [TL, TR, BR, BL]"""
    pts = pts.reshape(4, 2).astype("float32")
    rect = np.zeros((4, 2), dtype="float32")
    s = pts.sum(axis=1)
    rect[0] = pts[np.argmin(s)]
    rect[2] = pts[np.argmax(s)]
    diff = np.diff(pts, axis=1)
    rect[1] = pts[np.argmin(diff)]
    rect[3] = pts[np.argmax(diff)]
    return rect


def calculate_paper_tilt(pts):
    """Tính góc nghiêng (Tilt Angle in degrees) của phiếu thi."""
    rect = order_points(pts)
    tl, tr, br, bl = rect

    vec_top = tr - tl
    angle_top = math.degrees(math.atan2(vec_top[1], vec_top[0]))

    vec_bot = br - bl
    angle_bot = math.degrees(math.atan2(vec_bot[1], vec_bot[0]))

    rot_angle = (abs(angle_top) + abs(angle_bot)) / 2.0

    w_top = np.linalg.norm(tr - tl)
    w_bot = np.linalg.norm(br - bl)
    h_left = np.linalg.norm(bl - tl)
    h_right = np.linalg.norm(br - tr)

    w_ratio = min(w_top, w_bot) / (max(w_top, w_bot) + 1e-5)
    h_ratio = min(h_left, h_right) / (max(h_left, h_right) + 1e-5)

    persp_tilt_w = math.degrees(math.acos(np.clip(w_ratio, 0.0, 1.0)))
    persp_tilt_h = math.degrees(math.acos(np.clip(h_ratio, 0.0, 1.0)))
    persp_tilt = max(persp_tilt_w, persp_tilt_h)

    total_tilt = math.sqrt(rot_angle**2 + persp_tilt**2)
    return round(total_tilt, 1), round(rot_angle, 1)


def detect_document_contour(frame):
    """Phát hiện khung phiếu thi với nhiều strategy."""
    h, w = frame.shape[:2]
    img_area = h * w
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    blur = cv2.GaussianBlur(gray, (5, 5), 0)

    def _find_quad(binary_img, min_ratio=0.08, max_ratio=0.98, poly_eps=0.02):
        kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (7, 7))
        closed = cv2.morphologyEx(binary_img, cv2.MORPH_CLOSE, kernel)
        edges = cv2.Canny(closed, 30, 120)
        edges = cv2.dilate(edges, np.ones((3, 3), np.uint8), iterations=2)
        contours, _ = cv2.findContours(edges, cv2.RETR_LIST, cv2.CHAIN_APPROX_SIMPLE)
        contours = sorted(contours, key=cv2.contourArea, reverse=True)
        for cnt in contours:
            area = cv2.contourArea(cnt)
            if area < img_area * min_ratio or area > img_area * max_ratio:
                continue
            peri = cv2.arcLength(cnt, True)
            approx = cv2.approxPolyDP(cnt, poly_eps * peri, True)
            if len(approx) == 4:
                return approx, closed, edges
        return None, closed, edges

    _, otsu = cv2.threshold(blur, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    contour, closed, edges = _find_quad(otsu)

    if contour is None:
        adapt = cv2.adaptiveThreshold(blur, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 51, 10)
        contour, closed, edges = _find_quad(adapt, poly_eps=0.03)

    return contour, (otsu, closed, edges)


def four_point_warp(image, pts):
    """Biến đổi perspective warp thành hình chữ nhật chuẩn."""
    rect = order_points(pts)
    tl, tr, br, bl = rect

    w1 = np.linalg.norm(br - bl)
    w2 = np.linalg.norm(tr - tl)
    maxW = max(int(w1), int(w2))

    h1 = np.linalg.norm(tr - br)
    h2 = np.linalg.norm(tl - bl)
    maxH = max(int(h1), int(h2))

    if maxW <= 50 or maxH <= 50:
        return None

    dst = np.array([
        [0, 0],
        [maxW - 1, 0],
        [maxW - 1, maxH - 1],
        [0, maxH - 1],
    ], dtype="float32")

    M = cv2.getPerspectiveTransform(rect, dst)
    return cv2.warpPerspective(image, M, (maxW, maxH))


def draw_gradeflow_overlay(frame, contour, stable_frames, required_frames=8, auto_mode=False):
    """
    Vẽ giao diện quét GradeFlow APK chuyên nghiệp:
    - 4 Khung chữ nhật màu trắng ở 4 góc màn hình
    - Dòng chữ hướng dẫn: "Đưa 4 ô vuông đen vào khung"
    - Hiển thị Cảnh báo nghiêng: "⚠️ Giấy nghiêng ~X°"
    """
    h, w = frame.shape[:2]
    overlay = frame.copy()

    box_w = int(w * 0.16)
    box_h = int(h * 0.12)
    margin_x = int(w * 0.04)
    margin_y = int(h * 0.04)

    corners_in_target = [False] * 4
    tilt_deg = 0.0
    is_tilted = False

    if contour is not None:
        pts = order_points(contour.reshape(4, 2))
        tilt_deg, _ = calculate_paper_tilt(pts)
        if tilt_deg > 18.0:
            is_tilted = True

        for idx, pt in enumerate(pts):
            px, py = pt[0], pt[1]
            if idx == 0:
                corners_in_target[0] = (margin_x <= px <= margin_x + box_w * 1.5) and (margin_y <= py <= margin_y + box_h * 1.5)
            elif idx == 1:
                corners_in_target[1] = (w - margin_x - box_w * 1.5 <= px <= w - margin_x) and (margin_y <= py <= margin_y + box_h * 1.5)
            elif idx == 2:
                corners_in_target[2] = (w - margin_x - box_w * 1.5 <= px <= w - margin_x) and (h - margin_y - box_h * 1.5 <= py <= h - margin_y)
            elif idx == 3:
                corners_in_target[3] = (margin_x <= px <= margin_x + box_w * 1.5) and (h - margin_y - box_h * 1.5 <= py <= h - margin_y)

        poly_color = (0, 165, 255) if is_tilted else ((0, 255, 0) if stable_frames >= required_frames else (0, 230, 255))
        cv2.polylines(overlay, [np.int32(pts)], True, poly_color, 3, cv2.LINE_AA)
        for pt in pts:
            cv2.circle(overlay, (int(pt[0]), int(pt[1])), 8, poly_color, -1, cv2.LINE_AA)

    for i, (bx1, by1, bx2, by2) in enumerate([
        (margin_x, margin_y, margin_x + box_w, margin_y + box_h),
        (w - margin_x - box_w, margin_y, w - margin_x, margin_y + box_h),
        (w - margin_x - box_w, h - margin_y - box_h, w - margin_x, h - margin_y),
        (margin_x, h - margin_y - box_h, margin_x, h - margin_y)
    ]):
        box_color = (0, 255, 0) if corners_in_target[i] else (255, 255, 255)
        thick = 4 if corners_in_target[i] else 3
        arm = int(min(box_w, box_h) * 0.4)
        if i == 0:
            cv2.line(overlay, (bx1, by1), (bx1 + arm, by1), box_color, thick)
            cv2.line(overlay, (bx1, by1), (bx1, by1 + arm), box_color, thick)
        elif i == 1:
            cv2.line(overlay, (bx2, by1), (bx2 - arm, by1), box_color, thick)
            cv2.line(overlay, (bx2, by1), (bx2, by1 + arm), box_color, thick)
        elif i == 2:
            cv2.line(overlay, (bx2, by2), (bx2 - arm, by2), box_color, thick)
            cv2.line(overlay, (bx2, by2), (bx2, by2 - arm), box_color, thick)
        elif i == 3:
            cv2.line(overlay, (bx1, by2), (bx1 + arm, by2), box_color, thick)
            cv2.line(overlay, (bx1, by2), (bx1, by2 - arm), box_color, thick)

        cv2.rectangle(overlay, (bx1, by1), (bx2, by2), box_color, 1)

    cv2.addWeighted(overlay, 0.85, frame, 0.15, 0, frame)

    if contour is not None and tilt_deg >= 5.0:
        warning_text = f"Giay nghieng ~{int(tilt_deg)} deg"
        text_size = cv2.getTextSize(warning_text, cv2.FONT_HERSHEY_SIMPLEX, 0.8, 2)[0]
        tx = (w - text_size[0]) // 2
        ty = margin_y + box_h + 30
        badge_color = (0, 140, 255) if is_tilted else (0, 180, 220)
        cv2.rectangle(frame, (tx - 15, ty - text_size[1] - 8), (tx + text_size[0] + 15, ty + 8), badge_color, -1)
        cv2.putText(frame, f"[!] {warning_text}", (tx, ty), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255, 255, 255), 2, cv2.LINE_AA)

    bar_h = 70
    cv2.rectangle(frame, (0, h - bar_h), (w, h), (15, 15, 15), -1)

    guide_str = "Dua 4 o vuong den vao khung"
    if contour is None:
        status_str = "Dang tim phieu thi..."
        status_color = (180, 180, 180)
    elif is_tilted:
        status_str = "Hay giu phieu thang bang..."
        status_color = (0, 165, 255)
    elif stable_frames < required_frames:
        status_str = f"Dang can chinh... ({stable_frames}/{required_frames})"
        status_color = (0, 230, 255)
    else:
        status_str = "SAN SANG! Nhan [C] cham diem [S] chup"
        status_color = (0, 255, 100)

    cv2.putText(frame, guide_str, ((w - cv2.getTextSize(guide_str, cv2.FONT_HERSHEY_SIMPLEX, 0.75, 2)[0]) // 2, h - 38),
                cv2.FONT_HERSHEY_SIMPLEX, 0.75, (255, 255, 255), 2, cv2.LINE_AA)

    mode_str = "[AUTO-SCAN: BAT]" if auto_mode else "[AUTO-SCAN: TAT]"
    cv2.putText(frame, f"{status_str}  |  {mode_str}", (15, h - 12),
                cv2.FONT_HERSHEY_SIMPLEX, 0.45, status_color, 1, cv2.LINE_AA)

    cv2.putText(frame, "[S] Chup  [C] Cham  [A] Auto  [D] Debug  [ESC] Thoat",
                (w - 370, h - 12), cv2.FONT_HERSHEY_SIMPLEX, 0.42, (180, 180, 180), 1, cv2.LINE_AA)

    return tilt_deg, corners_in_target


def check_contour_stable(prev, curr, threshold=25):
    """Kiểm tra phiếu thi có đứng yên ổn định không."""
    if prev is None or curr is None:
        return False
    p = order_points(prev.reshape(4, 2))
    c = order_points(curr.reshape(4, 2))
    diff = np.max(np.abs(p - c))
    return diff < threshold


def run_grading_engine(warped_img, out_dir):
    """Gọi engine hi.py để chấm bài và hiển thị kết quả."""
    tmp_path = os.path.join(out_dir, "_tmp_camera_grade.jpg")
    cv2.imwrite(tmp_path, warped_img)
    abs_path = os.path.abspath(tmp_path)
    hi_path = str(ENGINE_DIR / 'hi.py')

    print("\n" + "=" * 50)
    print(" 🚀 ĐANG GỌI ENGINE CHẤM BÀI (hi.py)...")
    print("=" * 50)

    cmd = [sys.executable, hi_path, abs_path]
    try:
        res = subprocess.run(cmd, capture_output=True, text=True, timeout=15)
        print(res.stdout)
        if res.returncode == 0:
            print(" ✅ CHẤM THÀNH CÔNG!")
            return True, tmp_path
        else:
            print(f" ❌ ENGINE LỖI (Exit Code {res.returncode}):")
            print(res.stderr)
            return False, tmp_path
    except Exception as e:
        print(f" ❌ LỖI KHI GỌI ENGINE: {e}")
        return False, tmp_path


def main():
    parser = argparse.ArgumentParser(description="GradeFlow Mobile Camera Scanner Test")
    parser.add_argument("--cam", type=str, default=None, help="Index camera (0, 1...) hoặc IP Cam URL")
    parser.add_argument("--auto", action="store_true", help="Bật chế độ Auto Scan tự động chấm khi ổn định")
    args = parser.parse_args()

    print("=" * 60)
    print(" 📱 GRADEFLOW MOBILE CAMERA SCANNER TEST")
    print(" 🎯 Giao diện & tính năng tương tự ứng dụng GradeFlow APK")
    print("=" * 60)

    cap, cam_name = find_camera_source(args.cam)
    if cap is None:
        print("\n [LỖI] Không kết nối được camera!")
        print(" 💡 Gợi ý:")
        print("   1. Mở app Iriun Webcam / DroidCam trên điện thoại")
        print("   2. Hoặc dùng IP Camera và chạy: python tests/integration/test_camera_scanner.py --cam http://192.168.1.X:8080/video")
        sys.exit(1)

    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1920)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 1080)
    cap.set(cv2.CAP_PROP_AUTOFOCUS, 1)

    actual_w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    actual_h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    print(f"[OK] Đã kết nối: {cam_name}")
    print(f"[CAMERA] Độ phân giải màn hình: {actual_w}x{actual_h}")

    out_dir = str(REPO_ROOT / "test_scan_output")
    os.makedirs(out_dir, exist_ok=True)

    # 🛑 Kiểm tra xem OpenCV có hỗ trợ HighGUI (cv2.imshow) hay không
    gui_supported = True
    window_name = "GradeFlow Scanner - Mobile Camera Test"
    try:
        cv2.namedWindow(window_name, cv2.WINDOW_NORMAL)
    except cv2.error as e:
        gui_supported = False
        print("\n [LƯU Ý] Phiên bản opencv-python hiện tại đang là bản Headless (không có cửa sổ GUI).")
        print(" 💡 Đã tự động chuyển sang CHẾ ĐỘ SCAN TỰ ĐỘNG & LƯU ĐĨA (Headless Auto-Scan Mode).")
        print(" 📌 Ảnh quét preview và kết quả chấm bài sẽ tự động cập nhật vào thư mục: test_scan_output/")
        print(" 📌 Để bật GUI cửa sổ màn hình, bạn hãy chạy: pip install opencv-python --force-reinstall\n")

    prev_contour = None
    stable_counter = 0
    STABLE_REQUIRED = 8
    debug_mode = False
    auto_mode = args.auto or (not gui_supported)  # Tự bật Auto mode nếu ở Headless
    scan_count = 0
    last_auto_grade_time = 0
    last_headess_log_time = 0
    scale = 0.55 if actual_w > 1280 else 0.85

    print("\n[HƯỚNG DẪN DRAG & SNAP]")
    print(" - Đưa 4 góc đen của phiếu vào đúng 4 khung trắng ở góc màn hình")
    print(" - Giữ điện thoại song song với phiếu thi (tránh nghiêng quá 15 deg)")
    if gui_supported:
        print(" - Nhấn [C] để chấm ngay  |  [S] để lưu ảnh  |  [A] bật Auto-Scan  |  [ESC] thoát")
    else:
        print(" - (Headless Mode): Ứng dụng sẽ tự động chấm khi phiếu thi thẳng hàng & ghi kết quả ra đĩa!")

    try:
        while True:
            ret, frame = cap.read()
            if not ret or frame is None:
                time.sleep(0.1)
                continue

            contour, dbg_imgs = detect_document_contour(frame)

            if check_contour_stable(prev_contour, contour, threshold=20):
                stable_counter = min(stable_counter + 1, STABLE_REQUIRED + 5)
            else:
                stable_counter = max(0, stable_counter - 2)
            prev_contour = contour

            display_frame = frame.copy()
            tilt_deg, corners_ok = draw_gradeflow_overlay(display_frame, contour, stable_counter, STABLE_REQUIRED, auto_mode)

            warped_current = None
            if contour is not None:
                warped_current = four_point_warp(frame, contour)

            # --- Hiển thị GUI nếu OpenCV hỗ trợ GUI ---
            if gui_supported:
                disp_w = int(display_frame.shape[1] * scale)
                disp_h = int(display_frame.shape[0] * scale)
                cv2.imshow(window_name, cv2.resize(display_frame, (disp_w, disp_h)))

                if warped_current is not None:
                    wh = min(420, warped_current.shape[0])
                    ww = int(wh * warped_current.shape[1] / warped_current.shape[0])
                    cv2.imshow("Warped Document Preview", cv2.resize(warped_current, (ww, wh)))

                if debug_mode:
                    otsu, closed, edges = dbg_imgs
                    dw = min(540, frame.shape[1])
                    dh = int(dw * frame.shape[0] / frame.shape[1])
                    cv2.imshow("1. Otsu Threshold", cv2.resize(otsu, (dw, dh)))
                    cv2.imshow("2. Morph Close", cv2.resize(closed, (dw, dh)))
                    cv2.imshow("3. Canny Edges", cv2.resize(edges, (dw, dh)))

                key = cv2.waitKey(1) & 0xFF
                if key == 27:  # ESC
                    break
                elif key == ord('d') or key == ord('D'):
                    debug_mode = not debug_mode
                    print(f"[DEBUG] Chế độ debug: {'BẬT' if debug_mode else 'TẮT'}")
                elif key == ord('a') or key == ord('A'):
                    auto_mode = not auto_mode
                    print(f"[AUTO-SCAN] Chế độ tự động chấm: {'BẬT' if auto_mode else 'TẮT'}")
                elif key == ord('s') or key == ord('S'):
                    if warped_current is not None:
                        fname = os.path.join(out_dir, f"gradeflow_scan_{scan_count:03d}.jpg")
                        cv2.imwrite(fname, warped_current)
                        scan_count += 1
                        print(f"[LƯU] Đã lưu ảnh warped: {fname}")
                elif key == ord('c') or key == ord('C'):
                    if warped_current is not None:
                        run_grading_engine(warped_current, out_dir)

            else:
                # --- Headless Mode (Ghi log console & tự động lưu file live preview) ---
                now_log = time.time()
                if now_log - last_headess_log_time > 1.2:
                    last_headess_log_time = now_log
                    # Lưu file preview trực tiếp ra đĩa
                    live_preview_path = os.path.join(out_dir, "live_scan_preview.jpg")
                    cv2.imwrite(live_preview_path, display_frame)

                    status_msg = "Đã tìm thấy phiếu thi" if contour is not None else "Đang tìm phiếu thi..."
                    print(f"[HEADLESS STREAM] 📷 {status_msg} | Nghiêng: ~{tilt_deg}° | Ổn định: {stable_counter}/{STABLE_REQUIRED} | File: test_scan_output/live_scan_preview.jpg")

            # --- Tự động chấm điểm khi Auto-Scan được bật ---
            now = time.time()
            if auto_mode and contour is not None and stable_counter >= STABLE_REQUIRED and (now - last_auto_grade_time > 4.0):
                if warped_current is not None:
                    print("\n[AUTO-SCAN] ⚡ Phát hiện phiếu thi chuẩn & ổn định, tự động chấm điểm...")
                    run_grading_engine(warped_current, out_dir)
                    last_auto_grade_time = now

    except KeyboardInterrupt:
        print("\n[DỪNG] Người dùng hủy chương trình bằng Ctrl+C.")
    finally:
        cap.release()
        if gui_supported:
            cv2.destroyAllWindows()
        print(f"\n[OK] Đã kết thúc. Ảnh preview & lưu trữ tại: {out_dir}")


if __name__ == "__main__":
    main()
