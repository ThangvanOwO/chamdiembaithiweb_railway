"""
Part III Unit & Edge Cases Test Suite for GradeFlow.
Tests Blank Columns, Marked Columns (Dark, Light, 2B, Uneven), Ambiguous Columns, and Digit Baselines.
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

from experimental_p3 import DIGIT_BASELINES


def classify_column_digit_baseline(col_scores, baseline_thresh=0.20, gap_min=0.10, col_std_min=0.0):
    """
    Experimental classifier helper for testing edge cases.
    Returns: (picked_digit, is_ambiguous, adjusted_scores, gap)
      picked_digit: 0-9 if marked, -1 if empty, -2 if ambiguous
    """
    scores_list = [col_scores.get(str(d), 0.0) for d in range(10)]
    col_std = float(np.std(scores_list))

    adj_scores = {}
    for d in range(10):
        raw_s = col_scores.get(str(d), 0.0)
        base_s = DIGIT_BASELINES.get(d, 0.03)
        adj_scores[d] = max(0.0, raw_s - base_s)

    sorted_adj = sorted(adj_scores.items(), key=lambda x: x[1], reverse=True)
    top_d, top_s = sorted_adj[0]
    sec_s = sorted_adj[1][1] if len(sorted_adj) > 1 else 0.0
    gap = top_s - sec_s

    is_blank_by_std = (col_std < col_std_min) if col_std_min > 0 else False

    if is_blank_by_std:
        return -1, False, adj_scores, gap

    if top_s >= baseline_thresh and gap >= gap_min:
        return int(top_d), False, adj_scores, gap
    elif top_s >= (baseline_thresh * 0.7) and gap < gap_min and top_s > 0.10:
        return -2, True, adj_scores, gap
    else:
        return -1, False, adj_scores, gap


class TestPart3BlankColumns(unittest.TestCase):
    """B. Tests that blank columns never generate hallucinated digits."""

    def test_completely_blank_column(self):
        """B1. All 10 bubbles completely blank."""
        scores = {str(d): 0.02 for d in range(10)}
        digit, is_ambig, _, _ = classify_column_digit_baseline(scores)
        self.assertEqual(digit, -1, "Completely blank column must return -1 (EMPTY)")
        self.assertFalse(is_ambig)

    def test_printed_ink_on_digits_8_and_9(self):
        """B2. Blank column with pre-printed ink on digits 8 & 9 (classic false positive trigger)."""
        scores = {
            "0": 0.03, "1": 0.02, "2": 0.02, "3": 0.03, "4": 0.03,
            "5": 0.04, "6": 0.05, "7": 0.09, "8": 0.23, "9": 0.18
        }
        digit, is_ambig, adj, _ = classify_column_digit_baseline(scores)
        self.assertEqual(digit, -1, f"Pre-printed ink must NOT trigger a digit (adj: {adj})")

    def test_uniform_lighting_noise(self):
        """B3. Column with uniform shadow or camera lighting noise."""
        scores = {str(d): 0.15 for d in range(10)}
        digit, _, _, _ = classify_column_digit_baseline(scores, col_std_min=0.02)
        self.assertEqual(digit, -1, "Uniform lighting noise must return -1 (EMPTY)")

    def test_slight_offset_shift_blank(self):
        """B4. Column with small offset shift on blank paper."""
        scores = {str(d): 0.04 + (d * 0.01) for d in range(10)}  # 0.04 to 0.13
        digit, _, _, _ = classify_column_digit_baseline(scores)
        self.assertEqual(digit, -1, "Shifted blank column must return -1")


class TestPart3MarkedColumns(unittest.TestCase):
    """C. Tests that genuinely marked columns are reliably detected (0% FN)."""

    def test_dark_solid_pencil_mark(self):
        """C1. Dark solid pencil mark on digit 3."""
        scores = {str(d): 0.03 for d in range(10)}
        scores["3"] = 0.95
        digit, is_ambig, _, _ = classify_column_digit_baseline(scores)
        self.assertEqual(digit, 3, "Dark mark on digit 3 must be detected")

    def test_light_pencil_mark(self):
        """C2. Light pencil mark on digit 7 (score ~0.42)."""
        scores = {str(d): 0.03 for d in range(10)}
        scores["7"] = 0.42
        digit, _, _, _ = classify_column_digit_baseline(scores)
        self.assertEqual(digit, 7, "Light pencil mark on digit 7 must be detected")

    def test_2b_pencil_mark_on_digit_8(self):
        """C3. 2B pencil mark on digit 8 (score 0.88 over 0.21 baseline)."""
        scores = {
            "0": 0.03, "1": 0.02, "2": 0.02, "3": 0.03, "4": 0.03,
            "5": 0.04, "6": 0.05, "7": 0.09, "8": 0.88, "9": 0.18
        }
        digit, _, _, _ = classify_column_digit_baseline(scores)
        self.assertEqual(digit, 8, "2B mark on digit 8 must be detected")

    def test_uneven_pencil_mark(self):
        """C4. Unevenly filled mark on digit 1."""
        scores = {str(d): 0.02 for d in range(10)}
        scores["1"] = 0.52
        digit, _, _, _ = classify_column_digit_baseline(scores)
        self.assertEqual(digit, 1, "Uneven mark on digit 1 must be detected")

    def test_slightly_off_center_mark(self):
        """C5. Slightly off-center mark on digit 5."""
        scores = {str(d): 0.04 for d in range(10)}
        scores["5"] = 0.48
        digit, _, _, _ = classify_column_digit_baseline(scores)
        self.assertEqual(digit, 5, "Off-center mark on digit 5 must be detected")


class TestPart3AmbiguousCases(unittest.TestCase):
    """D. Tests ambiguous cases return AMBIGUOUS status instead of forced errors."""

    def test_two_competing_bubbles(self):
        """D1. Two bubbles filled (e.g. erased mark + new mark with close scores)."""
        scores = {str(d): 0.02 for d in range(10)}
        scores["2"] = 0.55
        scores["4"] = 0.52
        digit, is_ambig, _, gap = classify_column_digit_baseline(scores, gap_min=0.10)
        self.assertEqual(digit, -2, "Competing bubbles must return AMBIGUOUS (-2)")
        self.assertTrue(is_ambig)

    def test_weak_ambiguous_peak(self):
        """D2. Weak peak below confident threshold with close runner up."""
        scores = {str(d): 0.05 for d in range(10)}
        scores["6"] = 0.22
        scores["9"] = 0.20
        digit, is_ambig, _, _ = classify_column_digit_baseline(scores, baseline_thresh=0.20, gap_min=0.10)
        self.assertTrue(digit in (-1, -2), "Weak ambiguous peak must not return a confident digit")


class TestPart3DigitBaselines(unittest.TestCase):
    """E. Tests Digit-specific baseline mechanics."""

    def test_baseline_values_loaded(self):
        """E1. Verify baselines for all 10 digits exist."""
        for d in range(10):
            self.assertIn(d, DIGIT_BASELINES)
            self.assertGreater(DIGIT_BASELINES[d], 0.0)

    def test_digit_8_and_9_baseline_higher(self):
        """E2. Verify digit 8 and 9 have appropriately higher baselines than digit 1."""
        self.assertGreater(DIGIT_BASELINES[8], DIGIT_BASELINES[1] * 4)
        self.assertGreater(DIGIT_BASELINES[9], DIGIT_BASELINES[1] * 4)


if __name__ == "__main__":
    unittest.main(verbosity=2)
