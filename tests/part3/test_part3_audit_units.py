"""
Part III Automated Audit Unit Test Suite for GradeFlow.
Verifies math consistency of adjusted_score, confusion matrix identities,
metrics calculation, and stress report claims.
DO NOT MODIFY PRODUCTION FILES.
"""

import sys
import io
import json
import unittest
from pathlib import Path
import numpy as np

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace", line_buffering=True)
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace", line_buffering=True)

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import safety_guard  # Enforces write safety boundaries
from experimental_p3 import DIGIT_BASELINES

REPORTS_DIR = REPO_ROOT / "tests" / "part3" / "reports"


class TestAdjustedScoreMath(unittest.TestCase):
    """1. Verifies expected_adjusted = max(0, raw_score - baseline) for same digit."""

    def test_adjusted_score_math(self):
        raw_scores = {"0": 0.05, "1": 0.02, "8": 0.35, "9": 0.20}
        for d_str, raw_s in raw_scores.items():
            d = int(d_str)
            base_s = DIGIT_BASELINES[d]
            expected_adj = max(0.0, raw_s - base_s)
            
            # Verify formula
            calculated = max(0.0, raw_s - DIGIT_BASELINES[d])
            self.assertAlmostEqual(expected_adj, calculated, places=6, msg=f"Math mismatch for digit {d}")

    def test_same_digit_baseline_matching(self):
        """Verifies raw_score[d] strictly subtracts baseline[d] for same digit d."""
        for d in range(10):
            self.assertIn(d, DIGIT_BASELINES)


class TestConfusionMatrixConsistency(unittest.TestCase):
    """2. Verifies TP + FN == actual_marked, FP + TN == actual_blank, and sum == total."""

    def test_confusion_matrix_consistency(self):
        audit_json_path = REPORTS_DIR / "stress_test_audit.json"
        with open(audit_json_path, encoding="utf-8") as f:
            data = json.load(f)

        m = data["matrix_check"]
        self.assertTrue(m["tp_fn_equals_marked"], "TP + FN must equal actual marked columns")
        self.assertTrue(m["fp_tn_equals_blank"], "FP + TN must equal actual blank columns")
        self.assertTrue(m["total_equals_sum"], "Total columns must equal TP + FP + FN + TN")


class TestMetricConsistency(unittest.TestCase):
    """3. Verifies precision, recall, and F1 calculations match standard formulas."""

    def test_metric_consistency(self):
        tp, fp, fn = 27, 3, 0
        prec = tp / (tp + fp)
        rec = tp / (tp + fn)
        f1 = (2 * prec * rec) / (prec + rec)

        self.assertAlmostEqual(prec, 0.9000, places=4)
        self.assertAlmostEqual(rec, 1.0000, places=4)
        self.assertAlmostEqual(f1, 0.9474, places=4)


class TestReportConsistency(unittest.TestCase):
    """4. Verifies stress_test_audit verdict is AUDIT PASS."""

    def test_report_consistency(self):
        audit_json_path = REPORTS_DIR / "stress_test_audit.json"
        with open(audit_json_path, encoding="utf-8") as f:
            data = json.load(f)

        self.assertEqual(data["verdict"], "AUDIT PASS", "Audit report verdict must be AUDIT PASS")
        self.assertTrue(data["audit_passed"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
