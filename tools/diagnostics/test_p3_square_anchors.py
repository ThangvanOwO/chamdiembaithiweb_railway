"""
Test script: Part III Square Anchors & Local Skew Alignment Analysis
Tự động phát hiện các ô vuông đen định vị (timing squares) ở vùng Part III (y ~ 1300-1350)
và cặp marker mép đáy để đo độ nghiêng xoay mép đáy và căn chỉnh cục bộ cho Phần III.
"""
import os
import sys
import cv2
import numpy as np
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
ENGINE_DIR = REPO_ROOT / 'grading' / 'engine'
sys.path.insert(0, str(ENGINE_DIR))

import hi

hi.load_template(str(ENGINE_DIR / 'templates' / 'template_default.json'))

def detect_part3_square_anchors(warped_gray):
    """
    Phát hiện hàng ô vuông đen (timing squares) ở đầu Phần III (y: 1300-1350).
    """
    h, w = warped_gray.shape[:2]
    roi_top = warped_gray[1300:1355, 0:w]

    blur = cv2.GaussianBlur(roi_top, (3, 3), 0)
    _, thresh = cv2.threshold(blur, 110, 255, cv2.THRESH_BINARY_INV)

    cnts, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    anchors = []
    for c in cnts:
        area = cv2.contourArea(c)
        if area < 100 or area > 600:
            continue
        x, y, bw, bh = cv2.boundingRect(c)
        aspect = bw / float(bh)
        solidity = area / float(bw * bh)

        if 0.65 <= aspect <= 1.45 and solidity > 0.70:
            cx = x + bw / 2.0
            cy = 1300 + y + bh / 2.0
            anchors.append({
                "center": (cx, cy),
                "area": area,
                "aspect": round(aspect, 2),
                "solidity": round(solidity, 2)
            })

    anchors.sort(key=lambda a: a["center"][0])
    return anchors

def calculate_part3_tilt_and_shift(anchors):
    """
    Tính độ nghiêng (angle in degrees) và độ lệch dọc (y_offset) của Phần III
    dựa trên đường hồi quy tuyến tính của hàng ô vuông đen.
    """
    if len(anchors) < 2:
        return 0.0, 0.0

    xs = np.array([a["center"][0] for a in anchors], dtype=np.float64)
    ys = np.array([a["center"][1] for a in anchors], dtype=np.float64)

    # Linear regression y = m*x + c
    slope, intercept = np.polyfit(xs, ys, 1)
    angle_deg = np.degrees(np.arctan(slope))

    # Expected mean Y for top timing squares is ~1330
    mean_y = float(np.mean(ys))
    expected_y = 1330.0
    y_shift = mean_y - expected_y

    return angle_deg, y_shift

def run_part3_anchors_test():
    img_dir = str(REPO_ROOT / 'anh')
    images = sorted([
        os.path.join(img_dir, f) for f in os.listdir(img_dir)
        if f.lower().endswith('.jpg') and not any(s in f for s in ['_result', '_thresh', '_name', '_overlay', '_calibration', '_gray', '_cleaned', '_detect'])
    ])

    print("=" * 80)
    print("  GRADEFLOW — PART III SQUARE ANCHORS ALGORITHM TEST RESULTS")
    print("=" * 80)

    results = []

    for path in images:
        name = os.path.basename(path)
        img = cv2.imread(path)
        if img is None:
            continue

        res = hi.auto_deskew_and_crop(img, debug=False)
        warped = res["warped"]
        gray = cv2.cvtColor(warped, cv2.COLOR_BGR2GRAY) if len(warped.shape) == 3 else warped.copy()

        anchors = detect_part3_square_anchors(gray)
        angle, y_shift = calculate_part3_tilt_and_shift(anchors)

        # Baseline engine result
        p3_res = hi.process_sheet(path, debug=False)
        p3_ans = p3_res.get("part3", {})

        print(f"\n  ▶ FILE: {name}")
        print(f"    • Detected Anchors : {len(anchors)} square timing blocks")
        for i, a in enumerate(anchors, 1):
            print(f"      Anchor #{i}: x={a['center'][0]:6.1f}, y={a['center'][1]:6.1f} | Area={a['area']:.0f} px²")

        print(f"    • Part III Tilt Angle: {angle:+.3f}°")
        print(f"    • Part III Y-Shift   : {y_shift:+.1f} px")
        print(f"    • Extracted Answers  : {p3_ans}")

        results.append({
            "file": name,
            "anchors_count": len(anchors),
            "angle": round(angle, 3),
            "y_shift": round(y_shift, 1),
            "p3_ans": p3_ans
        })

    print(f"\n{'='*80}")
    print("  SUMMARY TEST REPORT")
    print(f"{'='*80}")
    print(f"  {'FILE':<12} | {'ANCHORS':<8} | {'TILT ANGLE':<12} | {'Y-SHIFT':<10} | {'P3 ANSWERS'}")
    print("-" * 80)
    for r in results:
        ans_str = ", ".join([f"Q{k}:{v}" for k, v in sorted(r['p3_ans'].items()) if v])
        print(f"  {r['file']:<12} | {r['anchors_count']:<8d} | {r['angle']:>+11.3f}° | {r['y_shift']:>+9.1f}px | {ans_str}")
    print("=" * 80 + "\n")

if __name__ == "__main__":
    run_part3_anchors_test()
