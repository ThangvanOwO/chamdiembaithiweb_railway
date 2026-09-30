"""
Experimental Part III Extraction Strategies for GradeFlow.
DO NOT IMPORT INTO PRODUCTION. FOR RESEARCH & TEST HARNESS ONLY.
"""

import sys
import json
from pathlib import Path
import numpy as np

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from grading.engine import hi as engine

# Load digit baselines computed on blank sheets
BASELINES_FILE = REPO_ROOT / "tests" / "part3" / "fixtures" / "digit_baselines.json"
DIGIT_BASELINES = {0: 0.027, 1: 0.021, 2: 0.024, 3: 0.030, 4: 0.032, 5: 0.043, 6: 0.053, 7: 0.088, 8: 0.211, 9: 0.166}

if BASELINES_FILE.exists():
    try:
        with open(BASELINES_FILE, encoding="utf-8") as f:
            _raw = json.load(f).get("baselines", {})
            for k, v in _raw.items():
                DIGIT_BASELINES[int(k)] = float(v.get("median", 0.0))
    except Exception:
        pass


def _extract_column_raw_data(cleaned_img, cols_x, y_offset):
    """
    Extract raw 10-digit scores and handwriting box OCR/ink data for columns.
    """
    digit_det = []
    digit_scores = []

    for ci, cx in enumerate(cols_x):
        col_ratios = {}
        col_scores = {}
        for d in range(10):
            cy = engine.PART3_DIGIT_START_Y + d * engine.PART3_DIGIT_STEP_Y + y_offset
            score, ratio, _ = engine._hybrid_score(cleaned_img, cx, cy, force_cnn=True)
            col_scores[str(d)] = round(float(score), 3)
            col_ratios[str(d)] = round(float(ratio), 3)
        digit_det.append(col_ratios)
        digit_scores.append(col_scores)

    return digit_det, digit_scores


def extract_part3_parametric(
    cleaned_img,
    y_offset=0,
    num_questions=None,
    score_min=0.28,
    gap_min=0.05,
    col_std_min=0.0,
    use_digit_baseline=False,
    baseline_offset_threshold=0.22,
    ocr_min_ink=0.08,
    enable_ocr=False,
    return_ambiguous_state=False
):
    """
    Parametric Part III Extractor for rigorous parameter sweeps and experimental testing.
    """
    answers = {}
    details = {}

    for blk in engine.PART3_BLOCKS:
        q = blk["q"]
        if num_questions is not None and q > num_questions:
            break
        cols_x = blk["cols_x"]
        q_det = {}

        # 1. Sign
        sign_score, r_neg, _ = engine._hybrid_score(
            cleaned_img, blk["sign_x"], engine.PART3_SIGN_Y + y_offset, force_cnn=True
        )
        is_neg = bool(sign_score >= engine.P3_SIGN_SCORE_MIN)
        q_det["sign"] = round(r_neg, 3)

        # 2. Comma
        comma_col = -1
        comma_scores = []
        comma_ratios = []
        for ci, cx in enumerate(cols_x):
            score, ratio, _ = engine._hybrid_score(
                cleaned_img, cx, engine.PART3_COMMA_Y + y_offset,
                threshold=0.22, force_cnn=True
            )
            comma_scores.append(score)
            comma_ratios.append(round(ratio, 3))
        q_det["comma"] = comma_ratios
        if comma_scores:
            order = sorted(range(len(comma_scores)), key=lambda i: comma_scores[i], reverse=True)
            top_i = order[0]
            top_s = comma_scores[top_i]
            second_s = comma_scores[order[1]] if len(order) > 1 else 0.0
            if top_s >= engine.P3_COMMA_SCORE_MIN and (top_s - second_s) >= engine.P3_COMMA_GAP_MIN:
                comma_col = top_i

        # 3. Digits
        digit_det, digit_scores = _extract_column_raw_data(cleaned_img, cols_x, y_offset)
        digits = []
        ambiguous_flags = []

        for ci in range(len(cols_x)):
            col_sc = digit_scores[ci]
            scores_list = list(col_sc.values())
            col_std = float(np.std(scores_list))

            if use_digit_baseline:
                # Calculate adjusted scores: score[d] - baseline[d]
                adj_scores = {}
                for d_int in range(10):
                    raw_s = col_sc.get(str(d_int), 0.0)
                    base_s = DIGIT_BASELINES.get(d_int, 0.03)
                    adj_scores[d_int] = max(0.0, raw_s - base_s)

                sorted_items = sorted(adj_scores.items(), key=lambda x: x[1], reverse=True)
                top_d, top_s = sorted_items[0]
                second_s = sorted_items[1][1] if len(sorted_items) > 1 else 0.0
                gap = top_s - second_s

                # Check blank column std filter
                is_blank = (col_std < col_std_min) if col_std_min > 0 else False

                # Adjusted score thresholding
                if not is_blank and top_s >= baseline_offset_threshold and gap >= gap_min:
                    digits.append(int(top_d))
                    ambiguous_flags.append(False)
                elif not is_blank and top_s >= (baseline_offset_threshold * 0.75) and gap < gap_min:
                    # Ambiguous case: elevated score but narrow gap
                    digits.append(-2 if return_ambiguous_state else -1)
                    ambiguous_flags.append(True)
                else:
                    digits.append(-1)
                    ambiguous_flags.append(False)
            else:
                sorted_items = sorted(col_sc.items(), key=lambda x: x[1], reverse=True)
                top_d_str, top_s = sorted_items[0]
                top_d = int(top_d_str)
                second_s = sorted_items[1][1] if len(sorted_items) > 1 else 0.0
                gap = top_s - second_s

                is_blank = (col_std < col_std_min) if col_std_min > 0 else False

                if not is_blank and top_s >= score_min and gap >= gap_min:
                    digits.append(top_d)
                    ambiguous_flags.append(False)
                elif not is_blank and top_s >= score_min and gap < gap_min:
                    digits.append(-2 if return_ambiguous_state else -1)
                    ambiguous_flags.append(True)
                else:
                    digits.append(-1)
                    ambiguous_flags.append(False)

        # 4. OCR Fallback (Strict ink ratio filtering)
        ocr_digits = []
        ocr_boxes = []
        ocr_ink = []
        digit_count = sum(1 for d in digits if d >= 0)

        if enable_ocr and digit_count == 0:
            ocr_digits = [-1] * len(cols_x)
            box_y = engine.PART3_SIGN_Y + y_offset + engine.P3_OCR_BOX_Y_OFFSET
            for ci, cx in enumerate(cols_x):
                box = engine._find_p3_box_near(cleaned_img, cx, box_y)
                if box is None:
                    box = engine._default_p3_box(cleaned_img, cx, box_y)
                ocr_boxes.append(box)
                digit, ink_ratio = engine._ocr_digit_from_box(cleaned_img, box)
                ocr_ink.append(round(ink_ratio, 3))

                if ink_ratio >= ocr_min_ink and digit >= 0:
                    ocr_digits[ci] = digit
                    digits[ci] = digit

        q_det["digits"] = digit_det
        q_det["digits_score"] = digit_scores
        q_det["picked"] = {
            "sign": is_neg,
            "comma_col": comma_col,
            "digits": digits,
            "ambiguous": ambiguous_flags
        }
        details[q] = q_det

        # Build final number string
        num_str = ""
        for i, d in enumerate(digits):
            if i == comma_col and num_str:
                if any(dd >= 0 for dd in digits[i:]):
                    num_str += "."
            if d >= 0:
                num_str += str(d)
        if is_neg and num_str:
            num_str = "-" + num_str

        answers[q] = num_str

    return answers, details


# Wrappers for testing standard strategies
def extract_part3_exp_a(cleaned_img, y_offset=0, num_questions=None, score_min=0.38):
    return extract_part3_parametric(cleaned_img, y_offset, num_questions, score_min=score_min, gap_min=0.05, enable_ocr=False)


def extract_part3_exp_b(cleaned_img, y_offset=0, num_questions=None, min_margin=0.08):
    return extract_part3_parametric(cleaned_img, y_offset, num_questions, score_min=0.30, gap_min=min_margin, enable_ocr=False)


def extract_part3_exp_c(cleaned_img, y_offset=0, num_questions=None, max_blank_std=0.038):
    return extract_part3_parametric(cleaned_img, y_offset, num_questions, score_min=0.28, gap_min=0.05, col_std_min=max_blank_std, enable_ocr=False)


def extract_part3_digit_baseline(cleaned_img, y_offset=0, num_questions=None, threshold=0.22, gap=0.05):
    return extract_part3_parametric(cleaned_img, y_offset, num_questions, use_digit_baseline=True, baseline_offset_threshold=threshold, gap_min=gap, enable_ocr=False)
