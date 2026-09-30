"""
Test Harness for Part III Analysis & Visualization in GradeFlow.
Saves JSON & CSV reports, and generates visual debug images for False Positives.
DO NOT MODIFY PRODUCTION FILES.
"""

import sys
import os
import json
import csv
import glob
import io
from pathlib import Path
import cv2
import numpy as np

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace', line_buffering=True)
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace', line_buffering=True)

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import safety_guard  # Enforces write safety boundaries

from grading.engine import hi as engine
from experimental_p3 import (
    extract_part3_exp_a,
    extract_part3_exp_b,
    extract_part3_exp_c,
    extract_part3_exp_combined,
)

OUTPUT_DIR = REPO_ROOT / "tests" / "part3"
REPORTS_DIR = OUTPUT_DIR / "reports"
VIS_DIR = OUTPUT_DIR / "visualizations"

REPORTS_DIR.mkdir(parents=True, exist_ok=True)
VIS_DIR.mkdir(parents=True, exist_ok=True)


def draw_false_positive_debug(image, q, ci, cx, y_offset, col_scores, top_d, top_s, ocr_res, save_path):
    """
    Draw visual debug overlay for a false positive column:
    Highlights all 10 bubbles, scores, margin, and handwriting box.
    """
    vis = image.copy()
    if len(vis.shape) == 2:
        vis = cv2.cvtColor(vis, cv2.COLOR_GRAY2BGR)

    # 1. Draw handwriting box & OCR area
    box_y = engine.PART3_SIGN_Y + y_offset + engine.P3_OCR_BOX_Y_OFFSET
    box = engine._find_p3_box_near(image if len(image.shape)==2 else cv2.cvtColor(image, cv2.COLOR_BGR2GRAY), cx, box_y)
    if box is None:
        box = engine._default_p3_box(image, cx, box_y)
    bx1, by1, bx2, by2 = box
    cv2.rectangle(vis, (bx1, by1), (bx2, by2), (255, 165, 0), 2)
    cv2.putText(vis, f"OCR: {ocr_res}", (bx1 - 10, by1 - 5), cv2.FONT_HERSHEY_SIMPLEX, 0.4, (255, 165, 0), 1)

    # 2. Draw 10 bubbles and their scores
    for d in range(10):
        cy = engine.PART3_DIGIT_START_Y + d * engine.PART3_DIGIT_STEP_Y + y_offset
        score = col_scores.get(str(d), 0.0)
        is_top = (d == top_d)
        
        color = (0, 0, 255) if is_top else (0, 255, 0)
        cv2.circle(vis, (int(cx), int(cy)), 12, color, 2 if is_top else 1)
        txt = f"{d}:{score:.2f}"
        cv2.putText(vis, txt, (int(cx) + 15, int(cy) + 4), cv2.FONT_HERSHEY_SIMPLEX, 0.35, color, 1)

    # Title header
    cv2.putText(vis, f"Q{q} Col{ci} FP: {top_d} (score={top_s:.2f})", (int(cx) - 30, int(engine.PART3_SIGN_Y + y_offset - 30)),
                cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 255), 2)

    cv2.imwrite(str(save_path), vis)


def analyze_images():
    # Gather test images from anh/ and cacmaubaithi/
    test_files = []
    
    anh_dir = REPO_ROOT / "anh"
    if anh_dir.exists():
        test_files.extend(sorted(glob.glob(str(anh_dir / "*.jpg"))))
        
    cacmau_dir = REPO_ROOT / "cacmaubaithi"
    if cacmau_dir.exists():
        test_files.extend(sorted(glob.glob(str(cacmau_dir / "**" / "*.jpg"), recursive=True)))

    # Filter out generated result/overlay files
    valid_files = [
        f for f in test_files
        if not any(s in os.path.basename(f) for s in ["_result", "_overlay", "_name", "_thresh", "_gray", "_cleaned", "_detect"])
    ]

    print(f"[HARNESS] Found {len(valid_files)} test images for Part III inspection.")

    report_entries = []
    csv_rows = []

    for img_path in valid_files:
        img_name = os.path.basename(img_path)
        print(f" -> Inspecting: {img_name}")

        try:
            image = cv2.imread(img_path)
            if image is None:
                continue
            detect_result = engine.detect_paper_and_warp(image, debug=False)
            warped = detect_result["warped"]
            if warped is None:
                continue

            cleaned = cv2.cvtColor(warped, cv2.COLOR_BGR2GRAY) if len(warped.shape) == 3 else warped.copy()
            y_offset = engine.detect_part3_offset_from_digits(cleaned) or 0

            # Run production extraction
            prod_ans, prod_det = engine.extract_part3(cleaned, y_offset=y_offset)

            # Run experimental extractions
            exp_a_ans, _ = extract_part3_exp_a(cleaned, y_offset=y_offset)
            exp_b_ans, _ = extract_part3_exp_b(cleaned, y_offset=y_offset)
            exp_c_ans, _ = extract_part3_exp_c(cleaned, y_offset=y_offset)
            exp_comb_ans, _ = extract_part3_exp_combined(cleaned, y_offset=y_offset)

            # Record detailed metrics per question and per column
            for blk in engine.PART3_BLOCKS:
                q = blk["q"]
                q_det = prod_det.get(q, {})
                cols_x = blk["cols_x"]
                digit_scores = q_det.get("digits_score", [])
                picked_digits = q_det.get("picked", {}).get("digits", [])
                ocr_digits = q_det.get("ocr_digits", [])
                ocr_ink = q_det.get("ocr_ink", [])

                for ci, cx in enumerate(cols_x):
                    col_sc = digit_scores[ci] if ci < len(digit_scores) else {}
                    scores_list = list(col_sc.values())
                    sorted_items = sorted(col_sc.items(), key=lambda x: x[1], reverse=True) if col_sc else [("-1", 0)]
                    top_d, top_s = sorted_items[0]
                    second_s = sorted_items[1][1] if len(sorted_items) > 1 else 0.0
                    margin = round(top_s - second_s, 3)
                    
                    ink_val = ocr_ink[ci] if ci < len(ocr_ink) else 0.0
                    ocr_val = ocr_digits[ci] if ci < len(ocr_digits) else -1
                    picked_d = picked_digits[ci] if ci < len(picked_digits) else -1

                    entry = {
                        "image": img_name,
                        "question": q,
                        "column": ci,
                        "cx": cx,
                        "y_offset": y_offset,
                        "all_digit_scores": col_sc,
                        "best_digit": int(top_d),
                        "best_score": round(top_s, 3),
                        "second_score": round(second_s, 3),
                        "margin": margin,
                        "mean_score": round(float(np.mean(scores_list)), 3) if scores_list else 0,
                        "std_score": round(float(np.std(scores_list)), 3) if scores_list else 0,
                        "ink_ratio": ink_val,
                        "ocr_fallback": ocr_val,
                        "prod_picked_digit": picked_d,
                        "prod_answer": prod_ans.get(q, ""),
                        "exp_a_answer": exp_a_ans.get(q, ""),
                        "exp_b_answer": exp_b_ans.get(q, ""),
                        "exp_c_answer": exp_c_ans.get(q, ""),
                        "exp_comb_answer": exp_comb_ans.get(q, ""),
                    }
                    report_entries.append(entry)

                    csv_rows.append([
                        img_name, q, ci, y_offset, top_d, round(top_s, 3), round(second_s, 3), margin,
                        ink_val, ocr_val, picked_d, prod_ans.get(q, ""), exp_comb_ans.get(q, "")
                    ])

                    # If this column resulted in a False Positive on an unfilled/blank test sheet
                    # (or when score is suspicious < 0.45 but picked a digit), draw visualization
                    is_suspicious_fp = (picked_d >= 0 and top_s < 0.45)
                    if is_suspicious_fp:
                        vis_path = VIS_DIR / f"FP_{Path(img_name).stem}_Q{q}_Col{ci}.png"
                        draw_false_positive_debug(cleaned, q, ci, cx, y_offset, col_sc, int(top_d), top_s, ocr_val, vis_path)

        except Exception as e:
            print(f" [ERROR] Processing {img_name}: {e}")

    # Write JSON report
    json_report_path = REPORTS_DIR / "part3_analysis_report.json"
    with open(json_report_path, "w", encoding="utf-8") as f:
        json.dump(report_entries, f, indent=2, ensure_ascii=False)

    # Write CSV report
    csv_report_path = REPORTS_DIR / "part3_analysis_report.csv"
    with open(csv_report_path, "w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f)
        writer.writerow([
            "image", "question", "column", "y_offset", "best_digit", "best_score", "second_score", "margin",
            "ink_ratio", "ocr_fallback", "prod_picked_digit", "prod_answer", "exp_comb_answer"
        ])
        writer.writerows(csv_rows)

    print(f"\n[HARNESS] Completed inspection.")
    print(f" -> JSON Report: {json_report_path}")
    print(f" -> CSV Report:  {csv_report_path}")
    print(f" -> Visual Debug Images: {VIS_DIR}")


if __name__ == "__main__":
    analyze_images()
