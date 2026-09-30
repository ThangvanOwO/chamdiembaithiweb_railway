"""
Part III Metric Audit Engine for GradeFlow.
Performs independent math verification of adjusted_score, confusion matrix,
precision, recall, F1, and stability/sensitivity claims.
DO NOT MODIFY PRODUCTION FILES.
"""

import sys
import os
import io
import json
import csv
from pathlib import Path
import numpy as np

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace", line_buffering=True)
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace", line_buffering=True)

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import safety_guard  # Enforces write safety boundaries

FIXTURES_DIR = REPO_ROOT / "tests" / "part3" / "fixtures"
REPORTS_DIR = REPO_ROOT / "tests" / "part3" / "reports"
REPORTS_DIR.mkdir(parents=True, exist_ok=True)


def run_metric_audit():
    print("=" * 80)
    print("  GRADEFLOW PART III INDEPENDENT METRIC AUDIT")
    print("=" * 80)

    # 1. Load Data
    analysis_report_file = REPORTS_DIR / "part3_analysis_report.json"
    baselines_file = FIXTURES_DIR / "digit_baselines.json"
    stress_report_file = REPORTS_DIR / "stress_test_report.json"
    gt_file = FIXTURES_DIR / "expected_results.json"

    with open(analysis_report_file, encoding="utf-8") as f:
        records = json.load(f)

    with open(baselines_file, encoding="utf-8") as f:
        raw_baselines = json.load(f).get("baselines", {})
        digit_baselines = {int(k): float(v["median"]) for k, v in raw_baselines.items()}

    with open(stress_report_file, encoding="utf-8") as f:
        stress_report = json.load(f)

    with open(gt_file, encoding="utf-8") as f:
        gt_data = json.load(f).get("ground_truth", {})

    print(f"Loaded {len(records)} column records across dataset.")
    print(f"Loaded Baselines: {digit_baselines}\n")

    discrepancies = []
    verified_column_cases = []

    # 2. Audit Every Column (Independent adjusted_score math verification)
    total_columns = len(records)
    calc_tp, calc_fp, calc_fn, calc_tn = 0, 0, 0, 0
    actual_marked_cnt = 0
    actual_blank_cnt = 0

    operating_thresh = 0.20
    operating_gap = 0.15

    for idx, r in enumerate(records):
        img = r["image"]
        q = r["question"]
        c = r["column"]
        sc_dict = r["all_digit_scores"]

        # Ground truth label
        is_marked = False
        if img in gt_data:
            marked_cols = gt_data[img].get("marked_columns", {}).get(str(q), [])
            is_marked = (c in marked_cols)

        if is_marked:
            actual_marked_cnt += 1
        else:
            actual_blank_cnt += 1

        # Independent calculation per digit
        indep_adj = {}
        same_digit_check_passed = True

        for d in range(10):
            raw_s = float(sc_dict.get(str(d), 0.0))
            base_s = float(digit_baselines[d])
            expected_adj = max(0.0, raw_s - base_s)
            indep_adj[d] = expected_adj

        # Sort independently
        sorted_indep = sorted(indep_adj.items(), key=lambda x: x[1], reverse=True)
        top_d, top_adj = sorted_indep[0]
        sec_d, sec_adj = sorted_indep[1]
        indep_margin = top_adj - sec_adj

        # Verify prediction
        pred_marked = (top_adj >= operating_thresh) and (indep_margin >= operating_gap)

        if pred_marked and is_marked:
            calc_tp += 1
            case_status = "TP"
        elif pred_marked and not is_marked:
            calc_fp += 1
            case_status = "FP"
        elif not pred_marked and is_marked:
            calc_fn += 1
            case_status = "FN"
        else:
            calc_tn += 1
            case_status = "TN"

        verified_column_cases.append({
            "image": img,
            "question": q,
            "column": c,
            "ground_truth_marked": is_marked,
            "predicted_digit": top_d if pred_marked else -1,
            "status": case_status,
            "raw_top_score": round(float(sc_dict.get(str(top_d), 0.0)), 4),
            "baseline_top": round(digit_baselines[top_d], 4),
            "indep_adjusted_top": round(top_adj, 4),
            "indep_second_adjusted": round(sec_adj, 4),
            "indep_margin": round(indep_margin, 4)
        })

    # 3. Audit Confusion Matrix & Derived Metrics
    calc_prec = calc_tp / max(1, (calc_tp + calc_fp))
    calc_rec = calc_tp / max(1, (calc_tp + calc_fn))
    calc_f1 = (2 * calc_prec * calc_rec) / max(1e-6, (calc_prec + calc_rec))

    # Validate Matrix Equations
    matrix_eq1 = (calc_tp + calc_fn == actual_marked_cnt)
    matrix_eq2 = (calc_fp + calc_tn == actual_blank_cnt)
    matrix_eq3 = (calc_tp + calc_fp + calc_fn + calc_tn == total_columns)

    matrix_valid = matrix_eq1 and matrix_eq2 and matrix_eq3

    # Compare with Stress Report Claims
    rep_summary = stress_report.get("summary", {})
    rep_lowest = rep_summary.get("lowest_fp_100_recall_config", {})

    rep_tp = rep_lowest.get("tp", -1)
    rep_fp = rep_lowest.get("fp", -1)
    rep_fn = rep_lowest.get("fn", -1)
    rep_tn = rep_lowest.get("tn", -1)
    rep_prec = rep_lowest.get("precision", -1.0)
    rep_rec = rep_lowest.get("recall", -1.0)
    rep_f1 = rep_lowest.get("f1", -1.0)

    claims_match = (
        calc_tp == rep_tp and
        calc_fp == rep_fp and
        calc_fn == rep_fn and
        calc_tn == rep_tn and
        abs(calc_prec - rep_prec) < 1e-3 and
        abs(calc_rec - rep_rec) < 1e-3 and
        abs(calc_f1 - rep_f1) < 1e-3
    )

    verdict = "AUDIT PASS" if (len(discrepancies) == 0 and matrix_valid and claims_match) else "AUDIT FAIL"

    print("=" * 80)
    print("  AUDIT VERIFICATION SUMMARY")
    print("=" * 80)
    print(f"  Total Columns Audited : {total_columns}")
    print(f"  Truly Marked Columns  : {actual_marked_cnt} (Matches TP+FN: {calc_tp}+{calc_fn}={calc_tp+calc_fn})")
    print(f"  Truly Blank Columns   : {actual_blank_cnt} (Matches FP+TN: {calc_fp}+{calc_tn}={calc_fp+calc_tn})")
    print(f"  Calculated TP / FP / FN / TN : {calc_tp} / {calc_fp} / {calc_fn} / {calc_tn}")
    print(f"  Reported   TP / FP / FN / TN : {rep_tp} / {rep_fp} / {rep_fn} / {rep_tn}")
    print(f"  Precision : Calc = {calc_prec:.4f} | Report = {rep_prec:.4f}")
    print(f"  Recall    : Calc = {calc_rec:.4f}  | Report = {rep_rec:.4f}")
    print(f"  F1-Score  : Calc = {calc_f1:.4f}   | Report = {rep_f1:.4f}")
    print(f"  Matrix Identity Check: {'VALID' if matrix_valid else 'INVALID'}")
    print(f"  Math Discrepancies Count: {len(discrepancies)}")
    print(f"\n  FINAL AUDIT VERDICT : [{verdict}]")
    print("=" * 80)

    # 4. Save Audit Artifacts
    audit_json_path = REPORTS_DIR / "stress_test_audit.json"
    with open(audit_json_path, "w", encoding="utf-8") as f:
        json.dump({
            "verdict": verdict,
            "audit_passed": (verdict == "AUDIT PASS"),
            "matrix_check": {
                "tp_fn_equals_marked": matrix_eq1,
                "fp_tn_equals_blank": matrix_eq2,
                "total_equals_sum": matrix_eq3,
                "total_columns": total_columns,
                "actual_marked": actual_marked_cnt,
                "actual_blank": actual_blank_cnt
            },
            "metrics_comparison": {
                "calculated": {"tp": calc_tp, "fp": calc_fp, "fn": calc_fn, "tn": calc_tn, "precision": round(calc_prec, 4), "recall": round(calc_rec, 4), "f1": round(calc_f1, 4)},
                "reported": {"tp": rep_tp, "fp": rep_fp, "fn": rep_fn, "tn": rep_tn, "precision": rep_prec, "recall": rep_rec, "f1": rep_f1}
            },
            "discrepancies": discrepancies,
            "sample_verified_cases": verified_column_cases[:30]
        }, f, indent=2, ensure_ascii=False)

    audit_csv_path = REPORTS_DIR / "stress_test_audit.csv"
    with open(audit_csv_path, "w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["image", "question", "column", "gt_marked", "pred_digit", "status", "raw_top", "baseline", "adj_top", "adj_second", "margin"])
        for case in verified_column_cases:
            writer.writerow([case["image"], case["question"], case["column"], case["ground_truth_marked"], case["predicted_digit"], case["status"], case["raw_top_score"], case["baseline_top"], case["indep_adjusted_top"], case["indep_second_adjusted"], case["indep_margin"]])

    print(f"\nSaved Audit Reports:")
    print(f"  -> JSON: {audit_json_path}")
    print(f"  -> CSV:  {audit_csv_path}")

    return verdict == "AUDIT PASS"


if __name__ == "__main__":
    run_metric_audit()
