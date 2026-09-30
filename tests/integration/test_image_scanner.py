import cv2
import numpy as np
import sys
import os
import functools
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
ENGINE_DIR = REPO_ROOT / 'grading' / 'engine'
sys.path.insert(0, str(ENGINE_DIR))

print = functools.partial(print, flush=True)

def detect_document_contour(frame, debug=False):
    h, w = frame.shape[:2]
    img_area = h * w
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    blur = cv2.GaussianBlur(gray, (5, 5), 0)

    def _find_quad(binary_img, min_ratio=0.08, max_ratio=0.98, poly_eps=0.02):
        kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (9, 9))
        closed = cv2.morphologyEx(binary_img, cv2.MORPH_CLOSE, kernel)
        edges = cv2.Canny(closed, 30, 120)
        edges = cv2.dilate(edges, np.ones((5, 5), np.uint8), iterations=2)
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

    # Strategy 1: OTSU
    _, otsu = cv2.threshold(blur, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    contour, closed1, edges1 = _find_quad(otsu)
    strategy = "Otsu"

    # Strategy 2: ADAPTIVE THRESHOLD
    if contour is None:
        adapt = cv2.adaptiveThreshold(blur, 255,
            cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 51, 10)
        k_open = cv2.getStructuringElement(cv2.MORPH_RECT, (5, 5))
        adapt = cv2.morphologyEx(adapt, cv2.MORPH_OPEN, k_open)
        contour, closed1, edges1 = _find_quad(adapt, poly_eps=0.03)
        strategy = "AdaptiveThreshold"

    # Strategy 3: EDGE-ONLY
    if contour is None:
        sobelx = cv2.Sobel(blur, cv2.CV_64F, 1, 0, ksize=3)
        sobely = cv2.Sobel(blur, cv2.CV_64F, 0, 1, ksize=3)
        sobel = np.uint8(np.clip(np.sqrt(sobelx**2 + sobely**2), 0, 255))
        _, sobel_bin = cv2.threshold(sobel, 30, 255, cv2.THRESH_BINARY)
        contour, closed1, edges1 = _find_quad(sobel_bin, min_ratio=0.05, poly_eps=0.04)
        strategy = "Sobel Gradient"

    # Strategy 4: HULL
    if contour is None:
        edges2 = cv2.Canny(blur, 20, 100)
        edges2 = cv2.dilate(edges2, np.ones((5,5), np.uint8), iterations=3)
        cnts, _ = cv2.findContours(edges2, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        large = [c for c in cnts if cv2.contourArea(c) > img_area * 0.005]
        if large:
            all_pts = np.concatenate(large)
            hull = cv2.convexHull(all_pts)
            hull_area = cv2.contourArea(hull)
            if hull_area > img_area * 0.08:
                peri = cv2.arcLength(hull, True)
                approx = cv2.approxPolyDP(hull, 0.05 * peri, True)
                if len(approx) == 4:
                    contour = approx
                    strategy = "ConvexHull"
        closed1, edges1 = edges2, edges2

    if contour is not None:
        print(f"[OK] Phat hien bang: {strategy}")
    else:
        print("[WARN] Tat ca 4 strategy deu that bai!")

    if debug:
        return contour, (gray, otsu if 'otsu' in locals() else gray, closed1, edges1)
    return contour, None


def order_points(pts):
    pts = pts.reshape(4, 2).astype("float32")
    rect = np.zeros((4, 2), dtype="float32")
    s = pts.sum(axis=1)
    rect[0] = pts[np.argmin(s)]
    rect[2] = pts[np.argmax(s)]
    diff = np.diff(pts, axis=1)
    rect[1] = pts[np.argmin(diff)]
    rect[3] = pts[np.argmax(diff)]
    return rect


def four_point_warp(image, pts):
    rect = order_points(pts)
    tl, tr, br, bl = rect
    maxW = max(int(np.linalg.norm(br - bl)), int(np.linalg.norm(tr - tl)))
    maxH = max(int(np.linalg.norm(tr - br)), int(np.linalg.norm(tl - bl)))
    if maxW <= 0 or maxH <= 0:
        return None
    dst = np.array([[0, 0], [maxW-1, 0], [maxW-1, maxH-1], [0, maxH-1]], dtype="float32")
    M = cv2.getPerspectiveTransform(rect, dst)
    return cv2.warpPerspective(image, M, (maxW, maxH))


def run(img_path):
    print(f"[INPUT] Ảnh: {img_path}")
    img = cv2.imread(img_path)
    if img is None:
        print("[LỖI] Không đọc được ảnh!")
        return

    h, w = img.shape[:2]
    print(f"[INFO] Kích thước gốc: {w}x{h}")

    contour, debug_imgs = detect_document_contour(img, debug=True)
    gray, otsu, closed, edges = debug_imgs

    SCALE = 600 / max(h, w)

    def show_step(name, img_gray):
        resized = cv2.resize(img_gray, (int(img_gray.shape[1]*SCALE), int(img_gray.shape[0]*SCALE)))
        cv2.imshow(name, resized)

    show_step("Buoc 1: Anh Goc (Gray)", gray)
    show_step("Buoc 2: Otsu Threshold", otsu)
    show_step("Buoc 3: Morph Close", closed)
    show_step("Buoc 4: Canny + Dilate", edges)

    annotated = img.copy()
    if contour is not None:
        cv2.drawContours(annotated, [contour], -1, (0, 255, 0), 4)
        pts = order_points(contour.reshape(4, 2))
        labels = ["TL", "TR", "BR", "BL"]
        colors = [(0,0,255),(0,165,255),(255,0,0),(0,255,255)]
        for label, pt, col in zip(labels, pts, colors):
            cv2.circle(annotated, (int(pt[0]), int(pt[1])), 18, col, -1)
            cv2.putText(annotated, label, (int(pt[0])+10, int(pt[1])-10),
                        cv2.FONT_HERSHEY_SIMPLEX, 1.2, col, 3)
        print(f"[OK] Phát hiện tài liệu! 4 góc: {pts.astype(int).tolist()}")
    else:
        print("[WARN] Không phát hiện được contour 4 cạnh!")
        cv2.putText(annotated, "KHONG PHAT HIEN DUOC!", (50, h//2),
                    cv2.FONT_HERSHEY_SIMPLEX, 2, (0,0,255), 5)

    show_step("Buoc 5: Phat Hien 4 Goc", cv2.cvtColor(annotated, cv2.COLOR_BGR2GRAY))
    cv2.imshow("Buoc 5: Phat Hien 4 Goc (MAU)", cv2.resize(annotated,
        (int(w*SCALE), int(h*SCALE))))

    if contour is not None:
        warped = four_point_warp(img, contour)
        if warped is not None:
            wh, ww = warped.shape[:2]
            ws = 800 / max(wh, ww)
            cv2.imshow("Buoc 6: SAU KHI WARP (Ket qua)", cv2.resize(warped,
                (int(ww*ws), int(wh*ws))))

            out_path = img_path.replace(".jpg", "_warped.jpg")
            cv2.imwrite(out_path, warped)
            print(f"[OK] Đã lưu ảnh warp: {out_path}")
            print(f"[INFO] Kích thước sau warp: {ww}x{wh}")

            print("\n[?] Nhấn [C] để chấm điểm bằng engine hi.py, [ESC] để thoát")

    print("\n[UI] Nhấn bất kỳ phím nào để tiếp tục...")

    while True:
        key = cv2.waitKey(0) & 0xFF
        if key == 27:
            break
        elif key == ord('c') or key == ord('C'):
            if contour is not None:
                tmp = img_path.replace(".jpg", "_warped.jpg")
                print(f"[CHẤM] Đang gọi engine hi.py cho ảnh: {tmp}")
                hi_path = str(ENGINE_DIR / 'hi.py')
                os.system(f'python "{hi_path}" "{tmp}"')
            break
        else:
            break

    cv2.destroyAllWindows()


if __name__ == "__main__":
    raw_path = sys.argv[1] if len(sys.argv) > 1 else "anh/1.jpg"
    path = str(REPO_ROOT / raw_path) if not Path(raw_path).is_absolute() else raw_path
    run(path)
