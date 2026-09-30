"""
EXPERIMENTAL SIMULATION: Part III Square Anchors & Local Deskew Benchmark
Does NOT modify grading/engine/hi.py.
Runs pure read-only simulation using temporary scratch image files in tmp/.
"""
import os
import sys
import time
import cv2
import numpy as np
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
ENGINE_DIR = REPO_ROOT / 'grading' / 'engine'
sys.path.insert(0, str(ENGINE_DIR))

import hi

hi.load_template(str(ENGINE_DIR / 'templates' / 'template_default.json'))

# Ground truth expected answers for active test images
GROUND_TRUTH = {
    "1.jpg": {1: "-1", 2: "2", 3: "0.75", 4: "-90", 5: "1.2", 6: "1925"},
    "1111.jpg": {1: "-1", 2: "2", 3: "0.75", 4: "-90", 5: "1.2", 6: "1925"},
    "2.jpg": {1: "5", 2: "2", 3: "4", 4: "7", 5: "", 6: ""},
    "3.jpg": {1: "6", 2: "2", 3: "5", 4: "", 5: "4", 6: ""},
    "4.jpg": {1: "6", 2: "7", 3: "8", 4: "4", 5: "2", 6: ""},
}

TMP_DIR = REPO_ROOT / 'tmp'
TMP_DIR.mkdir(exist_ok=True)

def detect_p3_top_bottom_anchors(gray):
    """Detect top square timing blocks (y~1332) and bottom timing blocks (y~1905)."""
    h, w = gray.shape[:2]
    
    # Top ROI (1300-1355)
    roi_top = gray[1300:1355, :]
    blur_top = cv2.GaussianBlur(roi_top, (3, 3), 0)
    _, thresh_top = cv2.threshold(blur_top, 110, 255, cv2.THRESH_BINARY_INV)
    cnts_top, _ = cv2.findContours(thresh_top, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    
    top_blocks = []
    for c in cnts_top:
        area = cv2.contourArea(c)
        if 250 <= area <= 550:
            x, y, bw, bh = cv2.boundingRect(c)
            aspect = bw / float(bh)
            solidity = area / float(bw * bh)
            if 0.75 <= aspect <= 1.35 and solidity > 0.75:
                top_blocks.append((x + bw / 2.0, 1300 + y + bh / 2.0))
    top_blocks.sort(key=lambda b: b[0])
    
    # Bottom ROI (1890-1925)
    roi_bot = gray[1890:1925, :]
    blur_bot = cv2.GaussianBlur(roi_bot, (3, 3), 0)
    _, thresh_bot = cv2.threshold(blur_bot, 110, 255, cv2.THRESH_BINARY_INV)
    cnts_bot, _ = cv2.findContours(thresh_bot, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    
    bot_blocks = []
    for c in cnts_bot:
        area = cv2.contourArea(c)
        if 120 <= area <= 450:
            x, y, bw, bh = cv2.boundingRect(c)
            aspect = bw / float(bh)
            solidity = area / float(bw * bh)
            if 0.7 <= aspect <= 2.5 and solidity > 0.75:
                bot_blocks.append((x + bw / 2.0, 1890 + y + bh / 2.0))
    bot_blocks.sort(key=lambda b: b[0])
    
    return top_blocks, bot_blocks

def apply_local_p3_deskew(warped_img, top_blocks, bot_blocks):
    """
    Applies local affine correction to Part III region on a COPY of the image.
    """
    corrected = warped_img.copy()
    if len(top_blocks) < 2:
        return corrected, 0.0, 0.0

    xs = np.array([b[0] for b in top_blocks])
    ys = np.array([b[1] for b in top_blocks])

    slope, intercept = np.polyfit(xs, ys, 1)
    angle_deg = np.degrees(np.arctan(slope))
    mean_y = float(np.mean(ys))
    y_shift = mean_y - 1332.0

    if abs(angle_deg) > 0.05 or abs(y_shift) > 2.0:
        h, w = warped_img.shape[:2]
        center = (w / 2.0, 1332.0)
        M = cv2.getRotationMatrix2D(center, angle_deg, 1.0)
        M[1, 2] -= y_shift
        
        p3_region = warped_img[1200:h, :].copy()
        corrected_p3 = cv2.warpAffine(p3_region, M, (w, h - 1200), flags=cv2.INTER_CUBIC, borderMode=cv2.BORDER_REPLICATE)
        corrected[1200:h, :] = corrected_p3

    return corrected, angle_deg, y_shift

def benchmark_image(img_path):
    name = os.path.basename(img_path)
    gt = GROUND_TRUTH.get(name, {})

    # 1. Baseline Extraction
    t0 = time.time()
    res_base = hi.process_sheet(img_path, debug=False)
    time_base = time.time() - t0
    ans_base = res_base.get("part3", {})
    conf_base = res_base.get("avg_confidence", 0.0)

    # 2. Experimental Anchor-Based Correction on COPY
    t0_exp = time.time()
    img_raw = cv2.imread(img_path)
    res_warp = hi.auto_deskew_and_crop(img_raw, debug=False)
    warped = res_warp["warped"]
    gray = cv2.cvtColor(warped, cv2.COLOR_BGR2GRAY) if len(warped.shape) == 3 else warped.copy()

    t0_detect = time.time()
    top_b, bot_b = detect_p3_top_bottom_anchors(gray)
    time_detect = time.time() - t0_detect

    t0_trans = time.time()
    corrected_copy, angle, y_shift = apply_local_p3_deskew(warped, top_b, bot_b)
    time_trans = time.time() - t0_trans

    temp_corr_file = str(TMP_DIR / f"_tmp_corr_{name}")
    cv2.imwrite(temp_corr_file, corrected_copy)

    t0_ext = time.time()
    res_corr = hi.process_sheet(temp_corr_file, debug=False)
    time_ext = time.time() - t0_ext
    time_total_corr = time.time() - t0_exp

    ans_corr = res_corr.get("part3", {})
    conf_corr = res_corr.get("avg_confidence", 0.0)

    correct_base = sum(1 for q, a in gt.items() if ans_base.get(q, "") == a)
    correct_corr = sum(1 for q, a in gt.items() if ans_corr.get(q, "") == a)
    total_gt = len([a for a in gt.values() if a])

    return {
        "name": name,
        "gt": gt,
        "top_blocks": len(top_b),
        "bot_blocks": len(bot_b),
        "angle": round(angle, 3),
        "y_shift": round(y_shift, 1),
        "ans_base": ans_base,
        "ans_corr": ans_corr,
        "conf_base": round(conf_base, 3),
        "conf_corr": round(conf_corr, 3),
        "acc_base": f"{correct_base}/{total_gt}" if total_gt else "N/A",
        "acc_corr": f"{correct_corr}/{total_gt}" if total_gt else "N/A",
        "time_base": round(time_base, 3),
        "time_detect": round(time_detect, 3),
        "time_trans": round(time_trans, 3),
        "time_ext": round(time_ext, 3),
        "time_total_corr": round(time_total_corr, 3),
        "changed": ans_base != ans_corr
    }

def benchmark_distorted_image(img_path, skew_perspective=20):
    """
    Creates an artificially distorted COPY of the image (vertical perspective distortion + bottom skew)
    and tests baseline vs anchor-corrected extraction.
    """
    name = os.path.basename(img_path)
    gt = GROUND_TRUTH.get(name, {})

    img_raw = cv2.imread(img_path)
    res_warp = hi.auto_deskew_and_crop(img_raw, debug=False)
    warped = res_warp["warped"].copy()
    h, w = warped.shape[:2]

    # Synthesize bottom perspective distortion on COPY
    pts1 = np.float32([[0, 0], [w, 0], [0, h], [w, h]])
    pts2 = np.float32([[0, 0], [w, 0], [skew_perspective, h], [w - skew_perspective, h + 15]])
    M_persp = cv2.getPerspectiveTransform(pts1, pts2)
    distorted_copy = cv2.warpPerspective(warped, M_persp, (w, h))

    temp_dist_base_file = str(TMP_DIR / f"_tmp_dist_base_{name}")
    cv2.imwrite(temp_dist_base_file, distorted_copy)

    # Test baseline on distorted copy
    res_base_dist = hi.process_sheet(temp_dist_base_file, debug=False)
    ans_base_dist = res_base_dist.get("part3", {})

    # Test anchor-corrected on distorted copy
    gray_dist = cv2.cvtColor(distorted_copy, cv2.COLOR_BGR2GRAY) if len(distorted_copy.shape) == 3 else distorted_copy
    top_b, bot_b = detect_p3_top_bottom_anchors(gray_dist)
    corrected_dist, angle, y_shift = apply_local_p3_deskew(distorted_copy, top_b, bot_b)

    temp_dist_corr_file = str(TMP_DIR / f"_tmp_dist_corr_{name}")
    cv2.imwrite(temp_dist_corr_file, corrected_dist)

    res_corr_dist = hi.process_sheet(temp_dist_corr_file, debug=False)
    ans_corr_dist = res_corr_dist.get("part3", {})

    correct_base = sum(1 for q, a in gt.items() if ans_base_dist.get(q, "") == a)
    correct_corr = sum(1 for q, a in gt.items() if ans_corr_dist.get(q, "") == a)
    total_gt = len([a for a in gt.values() if a])

    return {
        "name": name,
        "angle_detected": round(angle, 3),
        "y_shift_detected": round(y_shift, 1),
        "ans_base_dist": ans_base_dist,
        "ans_corr_dist": ans_corr_dist,
        "acc_base_dist": f"{correct_base}/{total_gt}" if total_gt else "N/A",
        "acc_corr_dist": f"{correct_corr}/{total_gt}" if total_gt else "N/A",
        "improved": correct_corr > correct_base
    }

def main():
    img_dir = str(REPO_ROOT / 'anh')
    images = sorted([
        os.path.join(img_dir, f) for f in os.listdir(img_dir)
        if f.lower().endswith('.jpg') and not any(s in f for s in ['_result', '_thresh', '_name', '_overlay', '_calibration', '_gray', '_cleaned', '_detect'])
    ])

    print("=" * 85)
    print("  PART III SQUARE ANCHORS — EXPERIMENTAL VALIDATION SUITE")
    print("=" * 85)

    base_results = []
    for path in images:
        r = benchmark_image(path)
        base_results.append(r)

    print("\n" + "=" * 85)
    print("  PART 1: ACTIVE DATASET BENCHMARK (BASELINE vs ANCHOR-CORRECTED)")
    print("=" * 85)
    print(f"{'FILE':<10} | {'TOP/BOT':<8} | {'ANGLE':<8} | {'Y-SHIFT':<8} | {'ACC BASE':<9} | {'ACC CORR':<9} | {'TIME BASE':<9} | {'TIME CORR':<9} | {'CHANGED'}")
    print("-" * 85)
    for r in base_results:
        tb_str = f"{r['top_blocks']}/{r['bot_blocks']}"
        print(f"{r['name']:<10} | {tb_str:<8} | {r['angle']:>+7.2f}° | {r['y_shift']:>+7.1f}p | {r['acc_base']:<9} | {r['acc_corr']:<9} | {r['time_base']:<9.2f}s | {r['time_total_corr']:<9.2f}s | {r['changed']}")

    print("\n" + "=" * 85)
    print("  PART 2: DISTORTED-IMAGE ROBUSTNESS SIMULATION (SYNTHETIC SKEW)")
    print("=" * 85)
    dist_results = []
    for path in images:
        rd = benchmark_distorted_image(path)
        dist_results.append(rd)
        print(f"  File: {rd['name']:<10} | Distorted Baseline Acc: {rd['acc_base_dist']:<5} -> Corrected Acc: {rd['acc_corr_dist']:<5} | Improved: {rd['improved']}")

    print("\n" + "=" * 85)
    print("  PART 3: OVERHEAD PERFORMANCE BREAKDOWN (AVERAGE ACROSS 5 IMAGES)")
    print("=" * 85)
    avg_base = sum(r['time_base'] for r in base_results) / len(base_results)
    avg_det = sum(r['time_detect'] for r in base_results) / len(base_results)
    avg_trans = sum(r['time_trans'] for r in base_results) / len(base_results)
    avg_ext = sum(r['time_ext'] for r in base_results) / len(base_results)
    avg_tot_corr = sum(r['time_total_corr'] for r in base_results) / len(base_results)
    overhead = avg_tot_corr - avg_base

    print(f"  • Baseline Processing Time : {avg_base:.3f}s")
    print(f"  • Anchor Detection Time    : {avg_det:.3f}s")
    print(f"  • Transformation Time      : {avg_trans:.3f}s")
    print(f"  • Extraction Time on Copy  : {avg_ext:.3f}s")
    print(f"  • Total Experimental Time  : {avg_tot_corr:.3f}s")
    print(f"  • Added Overhead           : +{overhead:.3f}s ({(overhead/avg_base)*100:.1f}%)")
    print("=" * 85 + "\n")

if __name__ == "__main__":
    main()
