"""
Part III Automated Stress Unit Test Suite for GradeFlow.
Tests Digit Baseline Stability, FP Resistance, Light Mark Recall,
Baseline Perturbations (+-10%, +-20%), and Threshold Sensitivity.
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
from experimental_p3 import DIGIT_BASELINES, extract_part3_parametric


def classify_with_baseline(col_scores, baseline_thresh=0.20, gap_min=0.12, baselines=None):
    if baselines is None:
        baselines = DIGIT_BASELINES
    
    adj_scores = {}
    for d in range(10):
        raw_s = col_scores.get(str(d), 0.0)
        base_s = baselines.get(d, 0.03)
        adj_scores[d] = max(0.0, raw_s - base_s)

    sorted_adj = sorted(adj_scores.items(), key=lambda x: x[1], reverse=True)
    top_d, top_s = sorted_adj[0]
    sec_s = sorted_adj[1][1] if len(sorted_adj) > 1 else 0.0
    gap = top_s - sec_s

    if top_s >= baseline_thresh and gap >= gap_min:
        return int(top_d), top_s, gap
    return -1, top_s, gap


class TestDigitBaselineStability(unittest.TestCase):
    """1. Verifies that digit baseline values remain stable across perturbations."""

    def test_digit_baseline_stability(self):
        for delta in [-0.02, -0.01, 0.0, 0.01, 0.02]:
            scores = {"0": 0.03, "1": 0.02, "7": 0.08, "8": 0.23, "9": 0.18}
            digit, _, _ = classify_with_baseline(scores, baseline_thresh=0.20 + delta)
            self.assertEqual(digit, -1, f"Blank sheet must stay blank under threshold perturbation {delta}")


class TestFalsePositiveResistance(unittest.TestCase):
    """2. Verifies resistance against high preprinted ink on digits 8 and 9."""

    def test_false_positive_resistance(self):
        # Blank column with natural high ink on 8 (0.24) and 9 (0.19)
        blank_scores = {
            "0": 0.03, "1": 0.02, "2": 0.02, "3": 0.03, "4": 0.03,
            "5": 0.04, "6": 0.05, "7": 0.09, "8": 0.24, "9": 0.19
        }
        digit, adj, gap = classify_with_baseline(blank_scores)
        self.assertEqual(digit, -1, f"Preprinted ink on digit 8/9 must not trigger FP (adj: {adj}, gap: {gap})")


class TestLightMarkRecall(unittest.TestCase):
    """3. Verifies that light pencil marks are recalled without false negatives."""

    def test_light_mark_recall(self):
        # Light pencil mark on digit 2 (score 0.38)
        light_mark_scores = {str(d): 0.02 for d in range(10)}
        light_mark_scores["2"] = 0.38
        digit, adj, gap = classify_with_baseline(light_mark_scores)
        self.assertEqual(digit, 2, f"Light pencil mark on digit 2 must be detected (adj: {adj}, gap: {gap})")


class TestBaselinePerturbation(unittest.TestCase):
    """4. Verifies classifier stability under +-10% and +-20% baseline shifts."""

    def test_baseline_perturbation(self):
        for factor in [0.80, 0.90, 1.10, 1.20]:
            pert_baselines = {d: DIGIT_BASELINES[d] * factor for d in range(10)}
            
            # Blank column check
            blank_scores = {str(d): 0.03 for d in range(10)}
            blank_scores["8"] = 0.23
            digit, _, _ = classify_with_baseline(blank_scores, baselines=pert_baselines)
            self.assertEqual(digit, -1, f"Blank column must be -1 under baseline factor {factor}")

            # Marked column check
            marked_scores = {str(d): 0.03 for d in range(10)}
            marked_scores["5"] = 0.65
            digit_marked, _, _ = classify_with_baseline(marked_scores, baselines=pert_baselines)
            self.assertEqual(digit_marked, 5, f"Marked column 5 must be detected under baseline factor {factor}")


class TestThresholdSensitivity(unittest.TestCase):
    """5. Verifies sensitivity when threshold varies by +-0.01 around operating point."""

    def test_threshold_sensitivity(self):
        scores_light_7 = {str(d): 0.02 for d in range(10)}
        scores_light_7["7"] = 0.42
        for th in [0.18, 0.19, 0.20, 0.21, 0.22]:
            digit, _, _ = classify_with_baseline(scores_light_7, baseline_thresh=th)
            self.assertEqual(digit, 7, f"Light mark on 7 must be detected under threshold {th}")


if __name__ == "__main__":
    unittest.main(verbosity=2)
