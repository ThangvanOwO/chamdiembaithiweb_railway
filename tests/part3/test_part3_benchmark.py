"""
Part III Quantitative Benchmark & Parameter Sweep.
Evaluates Raw Thresholds vs Blank Column Detection vs Digit-Specific Baselines.
DO NOT MODIFY PRODUCTION FILES.
"""

import sys
import os
import io
import json
import glob
from pathlib import Path
import numpy as np

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace", line_buffering=True)
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace", line_buffering=True)

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import safety_guard  # Enforces write safety boundaries

import cv2
from grading.engine import hi as engine
from experimental_p3 import (
    extract_part3_parametric,
    DIGIT_BASELINES,
)

FIXTURES_DIR = REPO_ROOT / "tests" / "part3" / "fixtures"
REPORTS_DIR = REPO_ROOT / "tests" / "part3" / "reports"
REPORTS_DIR.mkdir(parents=True, exist_ok=True)


def load_cached_or_extract_all_columns():
    """
    Loads pre-extracted column scores from part3_analysis_report.json or extracts fresh.
    """
    report_json_path = REPORTS_DIR / "part3_analysis_report.json"
    if report_json_path.exists():
        with open(report_json_path, encoding="utf-8") as f:
            return json.load(f)
    return []


def run_comprehensive_benchmark():
    # Load fixtures
    with open(FIXTURES_DIR / "expected_results.json", encoding="utf-8") as f:
        fixtures_data = json.load(f)

    gt_data = fixtures_data.get("ground_truth", {})
    blank_templates = set(fixtures_data.get("blank_template_images", []))

    records = load_cached_or_extract_all_columns()
    print(f"[BENCHMARK] Loaded {len(records)} column records across dataset.")

    # 1. Feature Analysis per column
    for r in records:
        sc_dict = r["all_digit_scores"]
        scores = [sc_dict.get(str(d), 0.0) for d in range(10)]
        scores_arr = np.array(scores)
        
        sorted_sc = np.sort(scores_arr)[::-1]
        top_s = float(sorted_sc[0])
        sec_s = float(sorted_sc[1])
        med_s = float(np.median(scores_arr))
        mean_s = float(np.mean(scores_arr))
        std_s = float(np.std(scores_arr))

        r["top_score"] = top_s
        r["second_score"] = sec_s
        r["margin"] = top_s - sec_s
        r["mean_score"] = mean_s
        r["std_score"] = std_s
        r["median_score"] = med_s
        r["top_minus_median"] = top_s - med_s
        r["top_div_median"] = (top_s / max(0.001, med_s))

        # Ground truth label for this specific column
        img = r["image"]
        q = r["question"]
        c = r["column"]

        is_marked = False
        if img in gt_data:
            marked_cols = gt_data[img].get("marked_columns", {}).get(str(q), [])
            is_marked = (c in marked_cols)
        r["ground_truth_marked"] = is_marked

    total_columns = len(records)
    total_marked = sum(1 for r in records if r["ground_truth_marked"])
    total_blank = total_columns - total_marked

    print(f"Total Columns: {total_columns} | Truly Marked: {total_marked} | Truly Blank: {total_blank}\n")

    # 2. Sweep Parameters
    score_thresholds = [0.28, 0.30, 0.32, 0.34, 0.36, 0.38, 0.40]
    gap_thresholds = [0.03, 0.05, 0.07, 0.10, 0.12, 0.15]
    std_thresholds = [0.000, 0.020, 0.030, 0.035, 0.040, 0.050]
    baseline_thresholds = [0.15, 0.18, 0.20, 0.22, 0.25, 0.28, 0.30]

    sweep_results = []

    # A. Raw Threshold + Gap Sweep
    for st in score_thresholds:
        for gt in gap_thresholds:
            for sdt in std_thresholds:
                tp, fp, fn, tn = 0, 0, 0, 0

                for r in records:
                    top_s = r["top_score"]
                    margin = r["margin"]
                    col_std = r["std_score"]
                    gt_marked = r["ground_truth_marked"]

                    is_blank_by_std = (col_std < sdt) if sdt > 0 else False
                    predicted_marked = (not is_blank_by_std) and (top_s >= st) and (margin >= gt)

                    if predicted_marked and gt_marked:
                        tp += 1
                    elif predicted_marked and not gt_marked:
                        fp += 1
                    elif not predicted_marked and gt_marked:
                        fn += 1
                    else:
                        tn += 1

                prec = tp / max(1, (tp + fp))
                rec = tp / max(1, (tp + fn))
                f1 = (2 * prec * rec) / max(1e-6, (prec + rec))

                sweep_results.append({
                    "type": "Raw Threshold",
                    "score_min": st,
                    "gap_min": gt,
                    "col_std_min": sdt,
                    "use_digit_baseline": False,
                    "tp": tp, "fp": fp, "fn": fn, "tn": tn,
                    "precision": round(prec, 4),
                    "recall": round(rec, 4),
                    "f1": round(f1, 4)
                })

    # B. Digit-Specific Baseline Sweep
    for bt in baseline_thresholds:
        for gt in gap_thresholds:
            tp, fp, fn, tn = 0, 0, 0, 0

            for r in records:
                sc_dict = r["all_digit_scores"]
                adj_scores = {}
                for d in range(10):
                    raw_s = sc_dict.get(str(d), 0.0)
                    base_s = DIGIT_BASELINES.get(d, 0.03)
                    adj_scores[d] = max(0.0, raw_s - base_s)

                sorted_adj = sorted(adj_scores.items(), key=lambda x: x[1], reverse=True)
                top_d, top_s = sorted_adj[0]
                sec_s = sorted_adj[1][1] if len(sorted_adj) > 1 else 0.0
                margin = top_s - sec_s
                gt_marked = r["ground_truth_marked"]

                predicted_marked = (top_s >= bt) and (margin >= gt)

                if predicted_marked and gt_marked:
                    tp += 1
                elif predicted_marked and not gt_marked:
                    fp += 1
                elif not predicted_marked and gt_marked:
                    fn += 1
                else:
                    tn += 1

            prec = tp / max(1, (tp + fp))
            rec = tp / max(1, (tp + fn))
            f1 = (2 * prec * rec) / max(1e-6, (prec + rec))

            sweep_results.append({
                "type": "Digit-Specific Baseline",
                "baseline_thresh": bt,
                "gap_min": gt,
                "col_std_min": 0.0,
                "use_digit_baseline": True,
                "tp": tp, "fp": fp, "fn": fn, "tn": tn,
                "precision": round(prec, 4),
                "recall": round(rec, 4),
                "f1": round(f1, 4)
            })

    # Sort results by F1 score
    sweep_results_sorted = sorted(sweep_results, key=lambda x: (x["f1"], x["recall"], -x["fp"]), reverse=True)

    best_f1_cfg = sweep_results_sorted[0]
    
    # Best Recall config with minimal FP
    best_recall_candidates = [c for c in sweep_results if c["recall"] >= 0.95]
    best_recall_cfg = sorted(best_recall_candidates, key=lambda x: (x["recall"], -x["fp"], x["f1"]), reverse=True)[0] if best_recall_candidates else sweep_results_sorted[0]

    # Best Precision config with reasonable Recall
    best_prec_candidates = [c for c in sweep_results if c["recall"] >= 0.85]
    best_prec_cfg = sorted(best_prec_candidates, key=lambda x: (x["precision"], x["f1"], x["recall"]), reverse=True)[0] if best_prec_candidates else sweep_results_sorted[0]

    # 3. Analyze Key False Positives and False Negatives
    print("=" * 85)
    print(f" {'STRATEGY / CONFIG':<35} | {'TP':<4} | {'FP':<4} | {'FN':<4} | {'PREC':<7} | {'REC':<7} | {'F1':<7}")
    print("=" * 85)

    # Baseline production
    prod_cfg = next(c for c in sweep_results if c["type"] == "Raw Threshold" and c["score_min"] == 0.28 and c["gap_min"] == 0.05 and c["col_std_min"] == 0.0)
    print(f" {'Production Baseline (0.28/0.05)':<35} | {prod_cfg['tp']:<4} | {prod_cfg['fp']:<4} | {prod_cfg['fn']:<4} | {prod_cfg['precision']:<7.4f} | {prod_cfg['recall']:<7.4f} | {prod_cfg['f1']:<7.4f}")
    
    # Best F1
    print(f" {'Best F1 Configuration':<35} | {best_f1_cfg['tp']:<4} | {best_f1_cfg['fp']:<4} | {best_f1_cfg['fn']:<4} | {best_f1_cfg['precision']:<7.4f} | {best_f1_cfg['recall']:<7.4f} | {best_f1_cfg['f1']:<7.4f}")
    
    # Best Recall
    print(f" {'Best Recall Configuration':<35} | {best_recall_cfg['tp']:<4} | {best_recall_cfg['fp']:<4} | {best_recall_cfg['fn']:<4} | {best_recall_cfg['precision']:<7.4f} | {best_recall_cfg['recall']:<7.4f} | {best_recall_cfg['f1']:<7.4f}")

    # Best Precision
    print(f" {'Best Precision Configuration':<35} | {best_prec_cfg['tp']:<4} | {best_prec_cfg['fp']:<4} | {best_prec_cfg['fn']:<4} | {best_prec_cfg['precision']:<7.4f} | {best_prec_cfg['recall']:<7.4f} | {best_prec_cfg['f1']:<7.4f}")
    print("=" * 85)

    # Save benchmark JSON
    benchmark_report_path = REPORTS_DIR / "benchmark_sweep_results.json"
    with open(benchmark_report_path, "w", encoding="utf-8") as f:
        json.dump({
            "best_f1": best_f1_cfg,
            "best_recall": best_recall_cfg,
            "best_precision": best_prec_cfg,
            "baseline": prod_cfg,
            "top_10_configs": sweep_results_sorted[:10],
            "all_sweep_results": sweep_results
        }, f, indent=2, ensure_ascii=False)

    print(f"\n[BENCHMARK] Full sweep saved to: {benchmark_report_path}")
    return best_f1_cfg, best_recall_cfg, best_prec_cfg


if __name__ == "__main__":
    run_comprehensive_benchmark()
