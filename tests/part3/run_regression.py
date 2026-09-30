"""
Regression Test & Strategy Comparison Benchmark for Part III.
Compares Production hi.py vs Experimental Strategies (A, B, C, Combined).
DO NOT MODIFY PRODUCTION FILES.
"""

import sys
import os
import json
import glob
import io
from pathlib import Path
import cv2

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

REPORTS_DIR = REPO_ROOT / "tests" / "part3" / "reports"
REPORTS_DIR.mkdir(parents=True, exist_ok=True)


def run_benchmark():
    # Gather test images
    anh_dir = REPO_ROOT / "anh"
    cacmau_dir = REPO_ROOT / "cacmaubaithi"

    test_files = []
    if anh_dir.exists():
        test_files.extend(sorted(glob.glob(str(anh_dir / "*.jpg"))))
    if cacmau_dir.exists():
        test_files.extend(sorted(glob.glob(str(cacmau_dir / "**" / "*.jpg"), recursive=True)))

    valid_files = [
        f for f in test_files
        if not any(s in os.path.basename(f) for s in ["_result", "_overlay", "_name", "_thresh", "_gray", "_cleaned", "_detect"])
    ]

    print(f"=== PART III REGRESSION & STRATEGY BENCHMARK ===")
    print(f"Total test images found: {len(valid_files)}\n")

    # Define strategies to test
    strategies = {
        "Production Baseline": lambda img, offset: engine.extract_part3(img, y_offset=offset),
        "Strategy A (Abs Threshold 0.38)": lambda img, offset: extract_part3_exp_a(img, y_offset=offset, score_min=0.38),
        "Strategy B (Margin & Baseline)": lambda img, offset: extract_part3_exp_b(img, y_offset=offset),
        "Strategy C (Blank Column Detect)": lambda img, offset: extract_part3_exp_c(img, y_offset=offset),
        "Strategy Combined (Hybrid)": lambda img, offset: extract_part3_exp_combined(img, y_offset=offset),
    }

    # Ground truth answers for filled test images in anh/
    known_ground_truth = {
        "1.jpg": {1: "-1", 2: "2", 3: "0.75", 4: "-90", 5: "1.2", 6: "1925"},
        "1111.jpg": {1: "-1", 2: "2", 3: "0.75", 4: "-90", 5: "1.2", 6: "1925"},
        "2.jpg": {1: "1.25", 2: "-34", 3: "0.5", 4: "99", 5: "-1.5", 6: "2024"},
        "3.jpg": {1: "42", 2: "-0.5", 3: "100", 4: "3.14", 5: "-12", 6: "0.01"},
        "4.jpg": {1: "15", 2: "2.5", 3: "-40", 4: "10.8", 5: "999", 6: "-0.1"},
        "7.jpg": {1: "0.5", 2: "-25", 3: "1234", 4: "5.6", 5: "-88", 6: "7.8"},
    }

    results_summary = {name: {"fp_count": 0, "fn_count": 0, "correct_q_count": 0, "failed_images": []} for name in strategies}

    detailed_image_results = []

    for img_path in valid_files:
        img_name = os.path.basename(img_path)
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

            # Determine expected answers
            is_filled_sheet = img_name in known_ground_truth
            expected_ans = known_ground_truth.get(img_name, {q: "" for q in range(1, 7)})

            img_entry = {"image": img_name, "is_filled": is_filled_sheet, "strategies": {}}

            for s_name, s_fn in strategies.items():
                pred_ans, _ = s_fn(cleaned, y_offset)

                fp = 0
                fn = 0
                matched_q = 0

                for q in range(1, 7):
                    pred = pred_ans.get(q, "")
                    gt = expected_ans.get(q, "")

                    if not is_filled_sheet:
                        # Blank sheet: any non-empty prediction is a False Positive!
                        if pred != "":
                            fp += 1
                    else:
                        # Filled sheet: compare with GT
                        if pred == gt:
                            matched_q += 1
                        else:
                            if pred == "":
                                fn += 1

                results_summary[s_name]["fp_count"] += fp
                results_summary[s_name]["fn_count"] += fn
                results_summary[s_name]["correct_q_count"] += matched_q

                if fp > 0 or (is_filled_sheet and matched_q < 6):
                    results_summary[s_name]["failed_images"].append({
                        "image": img_name, "fp": fp, "fn": fn, "pred": pred_ans
                    })

                img_entry["strategies"][s_name] = {
                    "answers": pred_ans,
                    "fp": fp,
                    "fn": fn,
                    "matched_q": matched_q
                }

            detailed_image_results.append(img_entry)

        except Exception as e:
            print(f"[ERROR] Failed {img_name}: {e}")

    # Output Benchmark Summary
    print("=" * 90)
    print(f" {'STRATEGY':<34} | {'FALSE POSITIVES (Blank)':<24} | {'FALSE NEGATIVES (Filled)':<25}")
    print("=" * 90)

    baseline_fp = results_summary["Production Baseline"]["fp_count"]

    for s_name, stats in results_summary.items():
        fp = stats["fp_count"]
        fn = stats["fn_count"]
        reduction = ((baseline_fp - fp) / baseline_fp * 100.0) if baseline_fp > 0 else 0.0
        print(f" {s_name:<34} | {fp:4d} (FP Red: {reduction:5.1f}%)       | {fn:4d} FN")

    print("=" * 90)

    # Save summary report JSON
    report_json_path = REPORTS_DIR / "regression_results.json"
    with open(report_json_path, "w", encoding="utf-8") as f:
        json.dump({
            "summary": results_summary,
            "detailed": detailed_image_results
        }, f, indent=2, ensure_ascii=False)

    print(f"\n[REGRESSION] Full benchmark JSON saved to: {report_json_path}")


if __name__ == "__main__":
    run_benchmark()
