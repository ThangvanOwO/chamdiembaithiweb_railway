"""
Grading wrapper — giao diện giữa Django và engine chấm bài.

Cung cấp hàm grade_image() nhận path ảnh + đáp án → trả kết quả chấm.
Được gọi từ views.py khi giáo viên upload ảnh.
"""

import os
import sys
import json
import time
import logging
import io
from pathlib import Path
from django.conf import settings

logger = logging.getLogger(__name__)

# ── Import engine ──
ENGINE_DIR = Path(__file__).resolve().parent / 'engine'
TEMPLATES_DIR = ENGINE_DIR / 'templates'

sys.path.insert(0, str(ENGINE_DIR))
import hi as engine


def _template_json_path(template_code):
    """
    Tìm template JSON tương ứng với mã template.
    VD: '40-08-06' → template_default.json (vì default là 40-08-06)
         '30-04-06-TL' → template_30_04_06_TL.json
    """
    # Chuyển code thành tên file
    code_underscore = template_code.replace('-', '_')
    candidates = [
        TEMPLATES_DIR / f"template_{code_underscore}.json",
        TEMPLATES_DIR / "template_default.json",
    ]
    for p in candidates:
        if p.exists():
            return str(p)
    return str(TEMPLATES_DIR / "template_default.json")


def parse_answer_key(answer_key_str, template_code=''):
    """
    Parse đáp án từ nhiều format:

    1. JSON string (format engine): {"part1": {"1": "A", ...}, "part2": {...}, "part3": {...}}
    2. CSV string (legacy): A,B,C,D,A,B,... (chỉ Part I)

    Returns dict tương thích engine: {"part1": {1: "A", ...}, "part2": {...}, "part3": {...}}
    """
    if not answer_key_str or not answer_key_str.strip():
        return None

    # Thử parse JSON trước
    try:
        data = json.loads(answer_key_str)
        if isinstance(data, dict):
            correct = {"part1": {}, "part2": {}, "part3": {}}

            # Support both key formats: part1/part2/part3 AND p1/p2/p3
            key_map = {
                "part1": ["part1", "p1"],
                "part2": ["part2", "p2"],
                "part3": ["part3", "p3"],
            }

            for target, candidates in key_map.items():
                for src_key in candidates:
                    if src_key in data and data[src_key]:
                        for k, v in data[src_key].items():
                            # P3 values may be floats from Excel; convert to string
                            if target == "part3" and not isinstance(v, str):
                                v = str(v)
                            correct[target][int(k)] = v
                        break

            # Convert Part II values: web form uses Đ/S → engine expects Dung/Sai
            p2_value_map = {"Đ": "Dung", "S": "Sai", "D": "Dung",
                            "Dung": "Dung", "Sai": "Sai"}
            for q, sub_answers in correct["part2"].items():
                if isinstance(sub_answers, dict):
                    correct["part2"][q] = {
                        label: p2_value_map.get(val, val)
                        for label, val in sub_answers.items()
                    }

            return correct
    except (json.JSONDecodeError, ValueError):
        pass

    # Fallback: CSV format (chỉ Part I)
    answers = [a.strip().upper() for a in answer_key_str.split(',') if a.strip()]
    if answers:
        correct = {
            "part1": {i + 1: a for i, a in enumerate(answers) if a in "ABCD"},
            "part2": {},
            "part3": {},
        }
        return correct

    return None


# ── Thang điểm Phần II theo chuẩn Bộ GD&ĐT ──
# Mỗi câu P2 có 4 ý (a,b,c,d). Điểm KHÔNG chia đều.
P2_SCORE_TABLE = {
    0: 0.0,
    1: 0.1,
    2: 0.25,
    3: 0.5,
    4: 1.0,
}


_P2_NORM = {"Đ": "Dung", "S": "Sai", "D": "Dung", "Dung": "Dung", "Sai": "Sai"}


def score_part2_moet(student_p2, correct_p2):
    """
    Chấm Phần II theo thang điểm Bộ GD&ĐT.

    Args:
        student_p2: {1: {'a': 'Dung', 'b': 'Sai', ...}, ...}  (int or str keys)
        correct_p2: {1: {'a': 'Dung', 'b': 'Sai', ...}, ...}  (int or str keys)

    Returns:
        (total_score, per_question_detail)
        per_question_detail: {1: {'correct_count': 3, 'score': 0.5, ...}, ...}
    """
    total = 0.0
    detail = {}

    for q, correct_answers in correct_p2.items():
        # Handle both int and string keys from JSON deserialization
        student_answers = student_p2.get(q, student_p2.get(str(q), {}))
        if isinstance(correct_answers, str):
            continue  # skip malformed entries
        n_correct = 0
        sub_detail = {}

        for label in ['a', 'b', 'c', 'd']:
            s_raw = student_answers.get(label, '')
            c_raw = correct_answers.get(label, '')
            # Normalize Đ/S → Dung/Sai for comparison
            s = _P2_NORM.get(s_raw, s_raw)
            c = _P2_NORM.get(c_raw, c_raw)
            ok = (s == c and s not in ('', 'X'))
            if ok:
                n_correct += 1
            sub_detail[label] = {'student': s, 'correct': c, 'ok': ok}

        q_score = P2_SCORE_TABLE.get(n_correct, 0.0)
        total += q_score
        detail[q] = {
            'correct_count': n_correct,
            'score': q_score,
            'max': 1.0,
            'subs': sub_detail,
        }

    return round(total, 2), detail


def compute_weighted_score(result, scoring_config, correct_answers=None):
    """
    Tính điểm theo thang điểm tùy chỉnh + Bộ GD&ĐT cho Phần II.

    Args:
        result: dict từ grade_image()
        scoring_config: dict {'p1': 0.25, 'p2': 1.0, 'p3': 0.5, 'max': 10}
        correct_answers: parsed answer key dict (for P2 MOET scoring)

    Returns:
        dict với weighted_score, max_score, chi tiết per part
    """
    if not result or not result.get('success'):
        return None

    # Default scoring config nếu chưa cấu hình
    if not scoring_config:
        scoring_config = {'p1': 0.25, 'p2_mode': 'moet', 'p3': 0.5}

    scores = result.get('scores', {})
    sp1 = scoring_config.get('p1', 0.25)
    sp3 = scoring_config.get('p3', 0.5)

    # Part I: đơn giản — số câu đúng × điểm/câu
    p1_correct = scores.get('part1', 0) or 0
    p1_score = round(p1_correct * sp1, 2)

    # Part II: thang Bộ GD&ĐT (mặc định) hoặc raw nếu override
    p2_score = 0.0
    p2_correct_total = 0
    p2_detail = {}
    p2_mode = scoring_config.get('p2_mode', 'moet')

    if p2_mode == 'moet' and correct_answers and correct_answers.get('part2'):
        student_p2 = result.get('part2', {})
        p2_score, p2_detail = score_part2_moet(student_p2, correct_answers['part2'])
        p2_correct_total = sum(d['correct_count'] for d in p2_detail.values())
    elif scores.get('part2') is not None:
        p2_raw = scores.get('part2', 0) or 0
        p2_score = round(p2_raw * scoring_config.get('p2', 1.0), 2)
        p2_correct_total = p2_raw

    # Part III: số câu đúng × điểm/câu
    p3_correct = scores.get('part3', 0) or 0
    p3_score = round(p3_correct * sp3, 2)

    raw_weighted = round(p1_score + p2_score + p3_score, 2)

    # Calculate max_score from parts if not explicitly set
    if 'max' in scoring_config and scoring_config['max']:
        max_score = scoring_config['max']
    else:
        # Infer from correct answers structure
        p1_total = len(correct_answers.get('part1', {})) if correct_answers else 0
        p2_total = len(correct_answers.get('part2', {})) if correct_answers else 0
        p3_total = len(correct_answers.get('part3', {})) if correct_answers else 0
        max_score = round(p1_total * sp1 + p2_total * 1.0 + p3_total * sp3, 2)
        if max_score == 0:
            max_score = raw_weighted  # Last fallback

    # Apply scale factor if configured (quy về thang 10)
    scale_factor = scoring_config.get('scale_factor', 1.0) or 1.0
    weighted = round(raw_weighted * scale_factor, 2)
    p1_score_scaled = round(p1_score * scale_factor, 2)
    p2_score_scaled = round(p2_score * scale_factor, 2)
    p3_score_scaled = round(p3_score * scale_factor, 2)

    return {
        'weighted_score': weighted,
        'max_score': round(max_score, 2),
        'p1_score': p1_score_scaled,
        'p2_score': p2_score_scaled,
        'p3_score': p3_score_scaled,
        'p1_score_raw': p1_score,
        'p2_score_raw': p2_score,
        'p3_score_raw': p3_score,
        'raw_weighted': raw_weighted,
        'scale_factor': scale_factor,
        'p1_correct': p1_correct,
        'p2_correct': p2_correct_total,
        'p3_correct': p3_correct,
        'p2_detail': p2_detail,
    }


def grade_image(image_path, answer_key_str='', template_code='', corners=None):
    """
    Chấm 1 ảnh phiếu thi.

    Args:
        image_path: Đường dẫn tuyệt đối tới ảnh
        answer_key_str: Đáp án (JSON string hoặc CSV)
        template_code: Mã template phiếu (VD: '30-04-06-TL')
        corners: Tọa độ 4 góc từ client truyền lên (nếu có)

    Returns:
        dict {
            'success': True/False,
            'sbd': '001234',
            'made': '002',
            'score': 42,
            'max_score': 54,
            'scores': {'part1': 36, 'part2': 4, 'part3': 2},
            'part1': {1: 'A', 2: 'B', ...},
            'part2': {1: {'a': 'Dung', ...}, ...},
            'part3': {1: '1234', ...},
            'detail_json': '...',           # JSON chi tiết
            'result_image_path': '...',     # Ảnh kết quả (nếu có)
            'processing_time': 2.3,
            'error': '',
        }
    """
    start_time = time.time()

    # Load template
    tpl_path = _template_json_path(template_code)
    try:
        engine.load_template(tpl_path)
        logger.info(f"Loaded template: {tpl_path}")
    except Exception as e:
        logger.warning(f"Template load failed: {e}, using defaults")

    # Parse đáp án
    correct = parse_answer_key(answer_key_str)

    # Chấm — redirect stdout/stderr to avoid Windows cp1252 encoding crash
    # (engine prints Vietnamese text which Windows console can't handle)
    old_stdout, old_stderr = sys.stdout, sys.stderr
    try:
        sys.stdout = io.TextIOWrapper(io.BytesIO(), encoding='utf-8', errors='replace')
        sys.stderr = io.TextIOWrapper(io.BytesIO(), encoding='utf-8', errors='replace')

        result = engine.process_sheet(
            str(image_path),
            correct_answers=correct,
            debug=True,
            provided_corners=corners,
        )
    except Exception as e:
        logger.error(f"Grading failed: {e}", exc_info=True)
        return {
            'success': False,
            'error': str(e),
            'processing_time': round(time.time() - start_time, 2),
        }
    finally:
        sys.stdout = old_stdout
        sys.stderr = old_stderr

    if not result:
        return {
            'success': False,
            'error': 'Không nhận diện được phiếu thi (ảnh mờ, nghiêng, hoặc sai format)',
            'processing_time': round(time.time() - start_time, 2),
        }

    processing_time = round(time.time() - start_time, 2)

    # Log detection method + offsets (engine now returns these)
    detect_method = result.get('detect_method', 'unknown')
    offsets = result.get('offsets', {})
    logger.info(f"Detection: method={detect_method}, offsets={offsets}")

    # Tìm ảnh kết quả (engine tạo file _result.jpg cạnh ảnh gốc)
    base = os.path.splitext(image_path)[0]
    result_img = f"{base}_result.jpg"

    # Build detail JSON — engine returns "details" with sub-keys sbd/part1/part2/part3
    engine_details = result.get('details', {})
    detail = {
        'sbd_detail': engine_details.get('sbd', {}),
        'part1_detail': engine_details.get('part1', {}),
        'part2_detail': engine_details.get('part2', {}),
        'part3_detail': engine_details.get('part3', {}),
    }

    # Handle case where no answer key → score is None
    score = result.get('score')
    max_score = result.get('max_score')
    scores = result.get('scores', {})

    return {
        'success': True,
        'sbd': result.get('sbd', ''),
        'made': result.get('made', ''),
        'score': score if score is not None else 0,
        'max_score': max_score,
        'scores': scores,
        'part1': result.get('part1', {}),
        'part2': result.get('part2', {}),
        'part3': result.get('part3', {}),
        'detail_json': json.dumps(detail, ensure_ascii=False),
        'result_image_path': result_img if os.path.exists(result_img) else '',
        'processing_time': processing_time,
        'detect_method': detect_method,
        'error': '',
    }
