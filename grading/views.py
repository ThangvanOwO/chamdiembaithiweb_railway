from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse
from django.utils import timezone
from django.conf import settings
from .models import Exam, ExamVariant, Submission
from .forms import ExamForm, UploadForm
from .grader import grade_image, parse_answer_key, compute_weighted_score
import json
import logging
import os
import re

logger = logging.getLogger(__name__)


# =============================================================================
# EXAM TEMPLATES — Pre-built answer sheet formats
# =============================================================================

EXAM_TEMPLATES = [
    {
        'code': '24-06-00',
        'folder': '24-06-00---QM-2025---A4---Ky-kiem-tra',
        'label': '24 06 00 - QM 2025 - A4 - Ky kiem tra',
        'parts': [24, 6, 0],
        'total': 30,
        'desc': 'P1: 24 câu · P2: 6 câu',
        'pages': 1,
        'has_p2': False,
    },
    {
        'code': '26-02-00',
        'folder': '26-02-00---QM-2025---A4---Ky-kiem-tra---C',
        'label': '26 02 00 - QM 2025 - A4 - Ky kiem tra - C',
        'parts': [26, 2, 0],
        'total': 28,
        'desc': 'P1: 26 câu · P2: 2 câu',
        'pages': 1,
        'has_p2': False,
    },
    {
        'code': '26-02-06-TL',
        'folder': '26-02-06-TL-QM-2025---A4---Ky-kiem-tra',
        'label': '26 02 06 TL QM 2025 - A4 - Ky kiem tra',
        'parts': [26, 2, 6],
        'total': 34,
        'desc': 'P1: 26 câu · P2: 2 câu · P3: 6 câu TL',
        'pages': 1,
        'has_p2': False,
    },
    {
        'code': '28-00-00',
        'folder': '28-00-00---QM-2025---A4---Ky-kiem-tra',
        'label': '28 00 00 - QM 2025 - A4 - Ky kiem tra',
        'parts': [28, 0, 0],
        'total': 28,
        'desc': 'P1: 28 câu (chỉ trắc nghiệm)',
        'pages': 1,
        'has_p2': False,
    },
    {
        'code': '28-02-00',
        'folder': '28-02-00---QM-2025---A4---Ky-kiem-tra',
        'label': '28 02 00 - QM 2025 - A4 - Ky kiem tra',
        'parts': [28, 2, 0],
        'total': 30,
        'desc': 'P1: 28 câu · P2: 2 câu',
        'pages': 2,
        'has_p2': True,
    },
    {
        'code': '28-02-04',
        'folder': '28-02-04---QM-2025---A4---Ky-kiem-tra',
        'label': '28 02 04 - QM 2025 - A4 - Ky kiem tra',
        'parts': [28, 2, 4],
        'total': 34,
        'desc': 'P1: 28 câu · P2: 2 câu · P3: 4 câu',
        'pages': 2,
        'has_p2': True,
    },
    {
        'code': '28-03-00',
        'folder': '28-03-00---QM-2025---A4---Ky-kiem-tra',
        'label': '28 03 00 - QM 2025 - A4 - Ky kiem tra',
        'parts': [28, 3, 0],
        'total': 31,
        'desc': 'P1: 28 câu · P2: 3 câu',
        'pages': 2,
        'has_p2': True,
    },
    {
        'code': '28-04-00',
        'folder': '28-04-00---QM-2025---A4---Ky-kiem-tra',
        'label': '28 04 00 - QM 2025 - A4 - Ky kiem tra',
        'parts': [28, 4, 0],
        'total': 32,
        'desc': 'P1: 28 câu · P2: 4 câu',
        'pages': 2,
        'has_p2': True,
    },
    {
        'code': '28-08-00',
        'folder': '28-08-00---QM-2025---A4---Ky-kiem-tra',
        'label': '28 08 00 - QM 2025 - A4 - Ky kiem tra',
        'parts': [28, 8, 0],
        'total': 36,
        'desc': 'P1: 28 câu · P2: 8 câu',
        'pages': 2,
        'has_p2': True,
    },
    {
        'code': '30-04-06-TL',
        'folder': '30-04-06-TL-QM-2025---A4---Ky-kiem-tra',
        'label': '30 04 06 TL QM 2025 - A4 - Ky kiem tra',
        'parts': [30, 4, 6],
        'total': 40,
        'desc': 'P1: 30 câu · P2: 4 câu · P3: 6 câu TL',
        'pages': 1,
        'has_p2': False,
    },
    {
        'code': '32-02-00',
        'folder': '32-02-00---QM-2025---A4---Ky-kiem-tra---O-ghi-diem',
        'label': '32 02 00 - QM 2025 - A4 - Ky kiem tra - O ghi diem',
        'parts': [32, 2, 0],
        'total': 34,
        'desc': 'P1: 32 câu · P2: 2 câu · Ô ghi điểm',
        'pages': 1,
        'has_p2': False,
    },
    {
        'code': '32-04-00',
        'folder': '32-04-00---QM-2025---A4---Ky-kiem-tra',
        'label': '32 04 00 - QM 2025 - A4 - Ky kiem tra',
        'parts': [32, 4, 0],
        'total': 36,
        'desc': 'P1: 32 câu · P2: 4 câu',
        'pages': 1,
        'has_p2': False,
    },
    {
        'code': '40-08-06',
        'folder': 'QM-2025-A4',
        'label': '40 08 06 - QM 2025 - A4',
        'parts': [40, 8, 6],
        'total': 54,
        'desc': 'P1: 40 câu · P2: 8 câu · P3: 6 câu TL',
        'pages': 1,
        'has_p2': False,
    },
    {
        'code': '40-00-00',
        'folder': '40-00-00---QM-2025---A4--Ky-kiem-tra',
        'label': '40 00 00 - QM 2025 - A4 - Ky kiem tra',
        'parts': [40, 0, 0],
        'total': 40,
        'desc': 'P1: 40 câu (chỉ trắc nghiệm)',
        'pages': 2,
        'has_p2': True,
    },
    {
        'code': '40-04-00-TL',
        'folder': '40-04-00-TL---QM-2025---A4---Ky-kiem-tra',
        'label': '40 04 00 TL - QM 2025 - A4 - Ky kiem tra',
        'parts': [40, 4, 0],
        'total': 44,
        'desc': 'P1: 40 câu · P2: 4 câu TL',
        'pages': 1,
        'has_p2': False,
    },
]


def find_best_template(parts):
    """
    Find the best matching physical template for a parts configuration.

    Args:
        parts: [p1_count, p2_count, p3_count]

    Returns:
        (template_dict, is_exact_match) or (None, False) if no suitable match.
    """
    p1, p2, p3 = (parts + [0, 0, 0])[:3]

    # 1. Exact match
    for t in EXAM_TEMPLATES:
        tp = t['parts']
        if tp[0] == p1 and tp[1] == p2 and tp[2] == p3:
            return t, True

    # 2. Closest match (weighted: P1 matters most, then P2, then P3)
    best = None
    best_score = float('inf')
    for t in EXAM_TEMPLATES:
        tp = t['parts']
        # Template must have AT LEAST as many slots as requested
        if tp[0] < p1 or tp[1] < p2 or tp[2] < p3:
            continue
        score = abs(tp[0] - p1) * 3 + abs(tp[1] - p2) * 2 + abs(tp[2] - p3)
        if score < best_score:
            best_score = score
            best = t

    if best:
        return best, False

    # 3. Fallback: just find closest regardless of direction
    for t in EXAM_TEMPLATES:
        tp = t['parts']
        score = abs(tp[0] - p1) * 3 + abs(tp[1] - p2) * 2 + abs(tp[2] - p3)
        if score < best_score:
            best_score = score
            best = t

    return best, False


# =============================================================================
# VIEWS
# =============================================================================

@login_required
def upload_view(request):
    """Upload & grade page — main feature."""
    exams = Exam.objects.filter(teacher=request.user)
    recent_submissions = Submission.objects.filter(teacher=request.user)[:10]

    # Get explicitly selected template (if any)
    selected_template = request.GET.get('template', '') or request.POST.get('template_code', '')
    
    # Process exam connection
    exam_id = request.GET.get('exam_id') or request.POST.get('exam_id', '')
    selected_exam = None
    if exam_id:
        try:
            selected_exam = Exam.objects.get(id=exam_id, teacher=request.user)
        except Exam.DoesNotExist:
            pass

    # If an exam is selected but no template is explicitly provided, find the best physical template
    if selected_exam and not selected_template:
        if selected_exam.template_code:
            selected_template = selected_exam.template_code
        else:
            best_t, exact = find_best_template(selected_exam.parts_config)
            if best_t:
                selected_template = best_t['code']
                
    if request.method == 'POST' and selected_template:
        files = request.FILES.getlist('images')
        
        if files:
            scoring_config = None
            exam_config_str = ''
            exam_variants = []
            if selected_exam:
                exam_config_str = selected_exam.answer_key or ''
                exam_variants = list(selected_exam.variants.all())
                try:
                    exam_config = json.loads(exam_config_str)
                    if isinstance(exam_config, dict):
                        scoring_config = exam_config.get('scoring')
                except (json.JSONDecodeError, ValueError):
                    pass

            created_submissions = []
            graded_count = 0
            error_count = 0

            for f in files:
                sub = Submission.objects.create(
                    exam=selected_exam,
                    template_code=selected_template,
                    teacher=request.user,
                    image=f,
                    status='pending',
                )
                created_submissions.append(sub)

                # Chấm ngay (synchronous)
                try:
                    sub.status = 'processing'
                    sub.save(update_fields=['status'])

                    image_path = os.path.join(settings.MEDIA_ROOT, sub.image.name)

                    # First pass: scan image to detect answers (use first variant or exam key)
                    first_answer_key = ''
                    if exam_variants:
                        first_answer_key = exam_variants[0].answer_key_str
                    elif exam_config_str:
                        first_answer_key = exam_config_str

                    result = grade_image(image_path, first_answer_key, selected_template)

                    if result.get('success'):
                        sub.status = 'completed'
                        sub.student_id = result.get('sbd', '')
                        sub.template_code = selected_template

                        # If exam has variants, find the matching one by detected mã đề
                        matched_variant = None
                        detected_ma_de = result.get('made', '')
                        if exam_variants and detected_ma_de:
                            for v in exam_variants:
                                if v.variant_code == str(detected_ma_de):
                                    matched_variant = v
                                    break
                        if not matched_variant and exam_variants:
                            matched_variant = exam_variants[0]

                        # Build answer_key_str from matched variant
                        if matched_variant:
                            sub.variant = matched_variant
                            answer_key_str = matched_variant.answer_key_str
                            # Re-run grading with correct variant answers if different
                            if answer_key_str != first_answer_key:
                                result = grade_image(image_path, answer_key_str, selected_template)
                                if not result.get('success'):
                                    sub.status = 'error'
                                    sub.error_message = result.get('error', 'Re-grade failed')
                                    sub.save()
                                    error_count += 1
                                    continue
                        else:
                            answer_key_str = exam_config_str

                        # Calculate weighted score using scoring config + MOET P2 rules
                        correct_answers = parse_answer_key(answer_key_str)
                        weighted = compute_weighted_score(result, scoring_config, correct_answers)

                        # Build full detail for display
                        _exam_cfg = None
                        try:
                            _exam_cfg = json.loads(exam_config_str) if exam_config_str else None
                        except (json.JSONDecodeError, ValueError):
                            _exam_cfg = None
                        parts_counts = _exam_cfg.get('parts', []) if _exam_cfg else []
                        p1_count = parts_counts[0] if len(parts_counts) > 0 else 0
                        p2_count = parts_counts[1] if len(parts_counts) > 1 else 0
                        p3_count = parts_counts[2] if len(parts_counts) > 2 else 0
                        total_q = p1_count + p2_count + p3_count

                        if weighted:
                            sub.score = weighted['weighted_score']
                            sub.correct_count = (weighted['p1_correct'] +
                                                 weighted['p2_correct'] +
                                                 weighted['p3_correct'])
                            sub.total_questions = total_q or scoring_config.get('max', sub.score)
                        else:
                            # Fallback: raw engine score
                            raw_score = result.get('score')
                            sub.score = raw_score if raw_score is not None else 0
                            sub.correct_count = sub.score
                            sub.total_questions = total_q or result.get('max_score')

                        # Save ALL detected answers (P1 + P2 + P3)
                        sub.answers_detected = json.dumps({
                            'part1': result.get('part1', {}),
                            'part2': result.get('part2', {}),
                            'part3': result.get('part3', {}),
                        }, ensure_ascii=False)

                        # Save full detail with breakdown
                        engine_detail = result.get('detail_json', '{}')
                        try:
                            detail_obj = json.loads(engine_detail)
                        except (json.JSONDecodeError, ValueError):
                            detail_obj = {}
                        detail_obj['scoring'] = {
                            'weighted_score': weighted['weighted_score'] if weighted else sub.score,
                            'max_score': weighted['max_score'] if weighted else sub.total_questions,
                            'p1_correct': weighted['p1_correct'] if weighted else 0,
                            'p1_score': weighted['p1_score'] if weighted else 0,
                            'p2_score': weighted['p2_score'] if weighted else 0,
                            'p3_correct': weighted['p3_correct'] if weighted else 0,
                            'p3_score': weighted['p3_score'] if weighted else 0,
                            'p2_detail': weighted['p2_detail'] if weighted else {},
                            'p1_count': p1_count,
                            'p2_count': p2_count,
                            'p3_count': p3_count,
                            'score_p1_per_q': scoring_config.get('p1', 0.25) if scoring_config else 0.25,
                            'score_p3_per_q': scoring_config.get('p3', 0.5) if scoring_config else 0.5,
                        }
                        sub.detail_json = json.dumps(detail_obj, ensure_ascii=False, default=str)
                        sub.graded_at = timezone.now()
                        sub.processing_time = result.get('processing_time', 0)
                        sub.save()
                        graded_count += 1
                        logger.info(f"Graded: SBD={sub.student_id}, score={sub.score}/{sub.total_questions}")
                    else:
                        sub.status = 'error'
                        sub.error_message = result.get('error', 'Unknown error')
                        sub.save()
                        error_count += 1
                        logger.warning(f"Grade failed: {sub.error_message}")

                except Exception as e:
                    sub.status = 'error'
                    sub.error_message = str(e)
                    sub.save()
                    error_count += 1
                    logger.error(f"Grade exception: {e}", exc_info=True)

            msg = f'Đã chấm {graded_count}/{len(files)} bài.'
            if error_count:
                msg += f' ({error_count} lỗi)'
            messages.success(request, msg)
            
            if request.htmx:
                return render(request, 'grading/_upload_result.html', {
                    'submissions': created_submissions,
                })
            
            # Redirect to results page for the exam (shows per-student breakdown)
            if selected_exam:
                return redirect('grading:results', exam_id=selected_exam.id)
            return redirect('grading:upload')
    
    # Find matching template info
    template_info = None
    if selected_template:
        template_info = next((t for t in EXAM_TEMPLATES if t['code'] == selected_template), None)
    
    return render(request, 'grading/upload.html', {
        'exams': exams,
        'recent_submissions': recent_submissions,
        'templates': EXAM_TEMPLATES,
        'selected_template': selected_template,
        'template_info': template_info,
        'selected_exam': selected_exam,
    })


@login_required
def exams_view(request):
    """List all exams."""
    exams = Exam.objects.filter(teacher=request.user)
    return render(request, 'grading/exams.html', {'exams': exams})


@login_required
def exam_create_view(request):
    """Create a new exam (manual configurator)."""
    if request.method == 'POST':
        title = request.POST.get('title', '').strip()
        subject = request.POST.get('subject', '').strip()
        num_questions = int(request.POST.get('num_questions', 0))
        answer_key = request.POST.get('answer_key', '')
        config_json_str = request.POST.get('config_json', '')
        template_code = request.POST.get('template_code', '').strip()

        variants_json_str = request.POST.get('variants_json', '[]')

        if not title:
            messages.error(request, 'Vui lòng nhập tên đề thi')
        elif num_questions == 0:
            messages.error(request, 'Vui lòng cấu hình ít nhất 1 câu hỏi')
        else:
            exam = Exam.objects.create(
                teacher=request.user,
                title=title,
                subject=subject,
                num_questions=num_questions,
                answer_key=config_json_str or answer_key,
                template_code=template_code,
            )
            # Save variants
            try:
                variants_data = json.loads(variants_json_str)
                for v in variants_data:
                    code = v.get('code', '').strip()
                    if code:
                        ExamVariant.objects.create(
                            exam=exam,
                            variant_code=code,
                            answers_json=json.dumps({'p1': v.get('p1', {}), 'p2': v.get('p2', {}), 'p3': v.get('p3', {})})
                        )
            except (json.JSONDecodeError, TypeError):
                pass

            messages.success(request, f'Đã tạo đề thi: {exam.title} ({exam.variants.count()} mã đề)')
            return redirect('grading:exams')

    initial_data = json.dumps({
        'title': '',
        'subject': '',
        'templateCode': '',
        'part1Count': 24,
        'part2Count': 4,
        'part3Count': 0,
        'variants': [{'code': '', 'p1': {}, 'p2': {}, 'p3': {}}],
    })

    return render(request, 'grading/exam_form.html', {
        'initial_data': initial_data,
        'is_edit': False,
        'templates_json': json.dumps(EXAM_TEMPLATES),
    })


@login_required
def exam_edit_view(request, exam_id):
    """Edit an exam (manual configurator)."""
    exam = get_object_or_404(Exam, id=exam_id, teacher=request.user)

    if request.method == 'POST':
        title = request.POST.get('title', '').strip()
        subject = request.POST.get('subject', '').strip()
        num_questions = int(request.POST.get('num_questions', 0))
        answer_key = request.POST.get('answer_key', '')
        config_json_str = request.POST.get('config_json', '')
        template_code = request.POST.get('template_code', '').strip()
        variants_json_str = request.POST.get('variants_json', '[]')

        if not title:
            messages.error(request, 'Vui lòng nhập tên đề thi')
        elif num_questions == 0:
            messages.error(request, 'Vui lòng cấu hình ít nhất 1 câu hỏi')
        else:
            exam.title = title
            exam.subject = subject
            exam.num_questions = num_questions
            exam.answer_key = config_json_str or answer_key
            exam.template_code = template_code
            exam.save()

            # Replace variants
            exam.variants.all().delete()
            try:
                variants_data = json.loads(variants_json_str)
                for v in variants_data:
                    code = v.get('code', '').strip()
                    if code:
                        ExamVariant.objects.create(
                            exam=exam,
                            variant_code=code,
                            answers_json=json.dumps({'p1': v.get('p1', {}), 'p2': v.get('p2', {}), 'p3': v.get('p3', {})})
                        )
            except (json.JSONDecodeError, TypeError):
                pass

            messages.success(request, f'Đã cập nhật đề thi: {exam.title} ({exam.variants.count()} mã đề)')
            return redirect('grading:exams')

    # Parse existing exam data for pre-populating the configurator
    part1_count = exam.num_questions
    part2_count = 0
    part3_count = 0
    scoring = {}

    if exam.answer_key:
        try:
            config = json.loads(exam.answer_key)
            if isinstance(config, dict) and 'parts' in config:
                parts = config['parts']
                part1_count = parts[0] if len(parts) > 0 else 0
                part2_count = parts[1] if len(parts) > 1 else 0
                part3_count = parts[2] if len(parts) > 2 else 0
            if isinstance(config, dict) and 'scoring' in config:
                scoring = config['scoring']
        except (json.JSONDecodeError, ValueError, TypeError):
            pass

    # Build variants list from DB
    db_variants = list(exam.variants.all())
    if db_variants:
        variants_list = []
        for v in db_variants:
            ans = v.answers
            # Convert string keys to int keys for JS
            p1 = {int(k): val for k, val in ans.get('p1', {}).items()}
            p2 = {int(k): val for k, val in ans.get('p2', {}).items()}
            p3 = {int(k): val for k, val in ans.get('p3', {}).items()}
            variants_list.append({'code': v.variant_code, 'p1': p1, 'p2': p2, 'p3': p3})
    else:
        # Backward compat: load answers from answer_key JSON
        p1, p2, p3 = {}, {}, {}
        if exam.answer_key:
            try:
                config = json.loads(exam.answer_key)
                if isinstance(config, dict):
                    for k, val in config.get('p1', {}).items():
                        p1[int(k)] = val
                    for k, val in config.get('p2', {}).items():
                        p2[int(k)] = val
                    for k, val in config.get('p3', {}).items():
                        p3[int(k)] = val
            except (json.JSONDecodeError, ValueError, TypeError):
                for i, ans in enumerate(exam.answer_key.split(','), 1):
                    ans = ans.strip().upper()
                    if ans:
                        p1[i] = ans
        variants_list = [{'code': '', 'p1': p1, 'p2': p2, 'p3': p3}]

    initial_data = json.dumps({
        'title': exam.title,
        'subject': exam.subject,
        'templateCode': exam.template_code or '',
        'part1Count': part1_count,
        'part2Count': part2_count,
        'part3Count': part3_count,
        'scoring': scoring,
        'variants': variants_list,
    })

    return render(request, 'grading/exam_form.html', {
        'initial_data': initial_data,
        'exam': exam,
        'is_edit': True,
        'templates_json': json.dumps(EXAM_TEMPLATES),
    })


@login_required
def exam_delete_view(request, exam_id):
    """Delete an exam."""
    exam = get_object_or_404(Exam, id=exam_id, teacher=request.user)
    if request.method == 'POST':
        title = exam.title
        exam.delete()
        messages.success(request, f'Đã xóa bài thi: {title}')
    return redirect('grading:exams')


# =============================================================================
# EXAM IMPORT — Create exam from Excel answer key file
# =============================================================================

def _parse_excel_answer_key(file_obj):
    """
    Parse the standard Excel answer key format.
    Returns dict with variants, part counts, and answers.
    """
    import openpyxl
    wb = openpyxl.load_workbook(file_obj, read_only=True, data_only=True)
    ws = wb.active

    rows = list(ws.iter_rows(values_only=True))
    if len(rows) < 2:
        return None, 'File không có dữ liệu (cần ít nhất 2 dòng: header + đáp án)'

    header = rows[0]

    # Parse header to identify column ranges
    p1_cols = []  # indices of P1 columns (numeric headers 1-40)
    p2_cols = []  # indices of P2 columns (headers like '1a','1b',...'8d')
    p3_cols = []  # indices of P3 columns after P2

    p2_pattern = re.compile(r'^(\d+)([abcd])$', re.IGNORECASE)
    found_p2 = False
    p2_end_idx = 0

    for i, h in enumerate(header):
        if i == 0:
            continue  # skip "Mã Đề \ Câu"
        h_str = str(h).strip() if h is not None else ''

        m = p2_pattern.match(h_str)
        if m:
            found_p2 = True
            p2_cols.append((i, int(m.group(1)), m.group(2).lower()))
            p2_end_idx = i
        elif not found_p2:
            # Before P2 → P1
            try:
                num = int(float(h)) if h is not None else None
                if num is not None and 1 <= num <= 60:
                    p1_cols.append(i)
            except (ValueError, TypeError):
                pass
        else:
            # After P2 → P3
            try:
                num = int(float(h)) if h is not None else None
                if num is not None:
                    p3_cols.append(i)
            except (ValueError, TypeError):
                pass

    # Determine P2 question count from columns
    p2_questions = set()
    for _, qnum, _ in p2_cols:
        p2_questions.add(qnum)
    p2_question_count = len(p2_questions)

    # Parse data rows (each = one variant)
    variants = []
    for row_idx, row in enumerate(rows[1:], start=2):
        if row[0] is None:
            continue

        variant_code = str(int(row[0])) if isinstance(row[0], (int, float)) else str(row[0]).strip()

        # P1 answers
        p1 = {}
        p1_count = 0
        for col_idx in p1_cols:
            val = row[col_idx] if col_idx < len(row) else None
            q_num = p1_cols.index(col_idx) + 1
            if val is not None and str(val).strip():
                p1[str(q_num)] = str(val).strip().upper()
                p1_count += 1

        # P2 answers
        p2 = {}
        for col_idx, qnum, opt in p2_cols:
            val = row[col_idx] if col_idx < len(row) else None
            if val is not None and str(val).strip():
                qkey = str(qnum)
                if qkey not in p2:
                    p2[qkey] = {}
                raw = str(val).strip()
                # Normalize: D→Đ, S→S
                if raw.upper() in ('D', 'Đ', 'ĐÚNG', 'DUNG'):
                    p2[qkey][opt] = 'Đ'
                elif raw.upper() in ('S', 'SAI'):
                    p2[qkey][opt] = 'S'
                else:
                    p2[qkey][opt] = raw

        p2_actual_count = len(p2)

        # P3 answers
        p3 = {}
        p3_count = 0
        for idx, col_idx in enumerate(p3_cols):
            val = row[col_idx] if col_idx < len(row) else None
            if val is not None:
                p3[str(idx + 1)] = val if isinstance(val, (int, float)) else str(val).strip()
                p3_count += 1

        variants.append({
            'code': variant_code,
            'p1': p1,
            'p2': p2,
            'p3': p3,
            'p1_count': p1_count,
            'p2_count': p2_actual_count,
            'p3_count': p3_count,
        })

    wb.close()

    if not variants:
        return None, 'Không tìm thấy dữ liệu đáp án trong file'

    # Use first variant to determine part counts
    first = variants[0]
    # Use max of actual P2 data across all variants (some may have more/less)
    actual_p2 = max(v['p2_count'] for v in variants) if variants else 0
    result = {
        'variants': variants,
        'part1Count': first['p1_count'],
        'part2Count': actual_p2,
        'part3Count': first['p3_count'],
        'totalQuestions': first['p1_count'] + actual_p2 + first['p3_count'],
        'variantCount': len(variants),
    }
    return result, None


@login_required
def parse_excel_api(request):
    """AJAX API: parse uploaded Excel file and return JSON with answers."""
    if request.method != 'POST':
        return JsonResponse({'error': 'Method not allowed'}, status=405)

    f = request.FILES.get('file')
    if not f:
        return JsonResponse({'error': 'Không có file nào được upload'}, status=400)

    if not f.name.endswith(('.xlsx', '.xls')):
        return JsonResponse({'error': 'Chỉ hỗ trợ file Excel (.xlsx, .xls)'}, status=400)

    try:
        result, error = _parse_excel_answer_key(f)
        if error:
            return JsonResponse({'error': error}, status=400)
        return JsonResponse({'success': True, 'data': result})
    except Exception as e:
        logger.exception('Error parsing Excel file')
        return JsonResponse({'error': f'Lỗi đọc file: {str(e)}'}, status=400)


@login_required
def exam_import_view(request):
    """Create exam by importing answer key from Excel file."""
    if request.method == 'POST':
        # Same save logic as exam_create_view
        title = request.POST.get('title', '').strip()
        subject = request.POST.get('subject', '').strip()
        num_questions = int(request.POST.get('num_questions', 0))
        config_json_str = request.POST.get('config_json', '')
        template_code = request.POST.get('template_code', '').strip()
        variants_json_str = request.POST.get('variants_json', '[]')

        if not title:
            messages.error(request, 'Vui lòng nhập tên đề thi')
        elif num_questions == 0:
            messages.error(request, 'Vui lòng cấu hình ít nhất 1 câu hỏi')
        else:
            exam = Exam.objects.create(
                teacher=request.user,
                title=title,
                subject=subject,
                num_questions=num_questions,
                answer_key=config_json_str,
                template_code=template_code,
            )
            try:
                variants_data = json.loads(variants_json_str)
                for v in variants_data:
                    code = v.get('code', '').strip()
                    if code:
                        ExamVariant.objects.create(
                            exam=exam,
                            variant_code=code,
                            answers_json=json.dumps({
                                'p1': v.get('p1', {}),
                                'p2': v.get('p2', {}),
                                'p3': v.get('p3', {}),
                            })
                        )
            except (json.JSONDecodeError, TypeError):
                pass

            messages.success(request, f'Đã tạo đề thi: {exam.title} ({exam.variants.count()} mã đề)')
            return redirect(f'/grading/upload/?exam_id={exam.id}')

    return render(request, 'grading/exam_import.html', {
        'templates_json': json.dumps(EXAM_TEMPLATES),
    })


@login_required
def results_view(request, exam_id):
    """View grading results for an exam."""
    exam = get_object_or_404(Exam, id=exam_id, teacher=request.user)
    submissions = exam.submissions.all()
    
    # Statistics
    completed = submissions.filter(status='completed')
    stats = {
        'total': submissions.count(),
        'completed': completed.count(),
        'pending': submissions.filter(status='pending').count(),
        'processing': submissions.filter(status='processing').count(),
        'errors': submissions.filter(status='error').count(),
    }
    
    if completed.exists():
        from django.db.models import Avg, Max, Min
        score_stats = completed.aggregate(
            avg=Avg('score'),
            max_score=Max('score'),
            min_score=Min('score'),
        )
        stats.update({
            'avg_score': round(score_stats['avg'] or 0, 1),
            'max_score': round(score_stats['max_score'] or 0, 1),
            'min_score': round(score_stats['min_score'] or 0, 1),
        })
    
    return render(request, 'grading/results.html', {
        'exam': exam,
        'submissions': submissions,
        'stats': stats,
    })


@login_required
def submission_detail_view(request, submission_id):
    """Xem chi tiết 1 bài nộp: ảnh gốc, ảnh kết quả, ảnh calibration."""
    sub = get_object_or_404(Submission, id=submission_id, teacher=request.user)

    # ── Ảnh debug ──
    image_path = os.path.join(settings.MEDIA_ROOT, sub.image.name)
    base = os.path.splitext(image_path)[0]

    debug_images = {}
    suffixes = {
        'original': sub.image.name,
        'result': '_result.jpg',
        'name': '_name.jpg',
        'calibration': '_calibration.jpg',
        'gray': '_gray.jpg',
        'thresh': '_thresh.jpg',
        'detect': '_detect.jpg',
    }
    for key, suffix in suffixes.items():
        if key == 'original':
            debug_images[key] = settings.MEDIA_URL + sub.image.name
        else:
            full_path = f"{base}{suffix}"
            if os.path.exists(full_path):
                rel_path = os.path.relpath(full_path, settings.MEDIA_ROOT).replace('\\', '/')
                debug_images[key] = settings.MEDIA_URL + rel_path

    # Auto-generate _name.jpg from warped (gray) image if missing
    name_path = f"{base}_name.jpg"
    gray_path = f"{base}_gray.jpg"
    if 'name' not in debug_images and os.path.exists(gray_path):
        try:
            import cv2
            from grading.engine.hi import NAME_REGION
            warped = cv2.imread(gray_path)
            if warped is not None:
                nx, ny, nw, nh = NAME_REGION
                h_img, w_img = warped.shape[:2]
                y1, y2 = max(0, ny), min(h_img, ny + nh)
                x1, x2 = max(0, nx), min(w_img, nx + nw)
                if y2 > y1 and x2 > x1:
                    cv2.imwrite(name_path, warped[y1:y2, x1:x2])
                    rel_path = os.path.relpath(name_path, settings.MEDIA_ROOT).replace('\\', '/')
                    debug_images['name'] = settings.MEDIA_URL + rel_path
        except Exception:
            pass

    # ── Parse stored data ──
    detail_data = {}
    if sub.detail_json:
        try:
            detail_data = json.loads(sub.detail_json)
        except json.JSONDecodeError:
            pass

    detected = {}
    if sub.answers_detected:
        try:
            detected = json.loads(sub.answers_detected)
        except json.JSONDecodeError:
            pass

    # ── Build scoring breakdown ──
    scoring = detail_data.get('scoring', {})

    # If no scoring breakdown saved (old submission), recalculate from exam
    if not scoring and sub.exam and sub.exam.answer_key:
        try:
            exam_config = json.loads(sub.exam.answer_key)
            scoring_config = exam_config.get('scoring')  # May be None — OK, defaults used
            parts = exam_config.get('parts', [])
            p1_count = parts[0] if len(parts) > 0 else 0
            p2_count = parts[1] if len(parts) > 1 else 0
            p3_count = parts[2] if len(parts) > 2 else 0

            if True:  # Always recalculate — compute_weighted_score handles None config
                # Use variant answers if available (has full P2/P3 data)
                if sub.variant:
                    correct_answers = parse_answer_key(sub.variant.answer_key_str)
                else:
                    correct_answers = parse_answer_key(sub.exam.answer_key)

                # Build a fake result dict from detected answers
                fake_result = {
                    'success': True,
                    'part1': detected.get('part1', detected) if isinstance(detected, dict) else {},
                    'part2': detected.get('part2', {}),
                    'part3': detected.get('part3', {}),
                    'scores': {},
                }
                # Count P1 correct
                if correct_answers and correct_answers.get('part1'):
                    p1_correct = 0
                    student_p1 = fake_result['part1']
                    for q, c in correct_answers['part1'].items():
                        s = student_p1.get(str(q), student_p1.get(q, ''))
                        if s == c and s not in ('', 'X'):
                            p1_correct += 1
                    fake_result['scores']['part1'] = p1_correct
                # Count P3 correct
                if correct_answers and correct_answers.get('part3'):
                    p3_correct = 0
                    student_p3 = fake_result['part3']
                    for q, c in correct_answers['part3'].items():
                        s = student_p3.get(str(q), student_p3.get(q, ''))
                        if str(s) == str(c) and s not in ('', 'X'):
                            p3_correct += 1
                    fake_result['scores']['part3'] = p3_correct

                weighted = compute_weighted_score(fake_result, scoring_config, correct_answers)
                if weighted:
                    scoring = {
                        'weighted_score': weighted['weighted_score'],
                        'max_score': weighted['max_score'],
                        'p1_correct': weighted['p1_correct'],
                        'p1_score': weighted['p1_score'],
                        'p2_score': weighted['p2_score'],
                        'p3_correct': weighted['p3_correct'],
                        'p3_score': weighted['p3_score'],
                        'p2_detail': weighted['p2_detail'],
                        'p1_count': p1_count,
                        'p2_count': p2_count,
                        'p3_count': p3_count,
                        'score_p1_per_q': scoring_config.get('p1', 0.25) if scoring_config else 0.25,
                        'score_p3_per_q': scoring_config.get('p3', 0.5) if scoring_config else 0.5,
                    }
                    # Update submission with recalculated values
                    sub.score = weighted['weighted_score']
                    sub.correct_count = (weighted['p1_correct'] +
                                         weighted.get('p2_correct', 0) +
                                         weighted['p3_correct'])
                    sub.total_questions = p1_count + p2_count + p3_count
                    detail_data['scoring'] = scoring
                    sub.detail_json = json.dumps(detail_data, ensure_ascii=False, default=str)
                    sub.save(update_fields=['score', 'correct_count', 'total_questions', 'detail_json'])
        except (json.JSONDecodeError, ValueError, TypeError) as e:
            logger.warning(f"Recalc scoring failed for sub {sub.id}: {e}")

    # Build P2 breakdown for template (list of dicts)
    p2_breakdown = []
    p2_detail = scoring.get('p2_detail', {})
    if p2_detail:
        for q_num in sorted(p2_detail.keys(), key=lambda x: int(x)):
            qd = p2_detail[q_num]
            p2_breakdown.append({
                'num': q_num,
                'correct_count': qd.get('correct_count', 0),
                'score': qd.get('score', 0),
                'subs': qd.get('subs', {}),
            })

    # Build correct answers + parts config for answer comparison panel
    correct_answers = {}
    parts_config = [0, 0, 0]
    if sub.exam and sub.exam.answer_key:
        try:
            _cfg = json.loads(sub.exam.answer_key)
            if isinstance(_cfg, dict):
                parts_config = _cfg.get('parts', [0, 0, 0])
        except (json.JSONDecodeError, ValueError):
            pass

        # If exam has variants and submission has a variant, use variant answers
        if sub.variant:
            correct_answers = sub.variant.answers  # {'p1': {...}, 'p2': {...}, 'p3': {...}}
        else:
            correct_answers = parse_answer_key(sub.exam.answer_key)
            # Normalize to p1/p2/p3 format
            if correct_answers and 'part1' in correct_answers:
                correct_answers = {
                    'p1': correct_answers.get('part1', {}),
                    'p2': correct_answers.get('part2', {}),
                    'p3': correct_answers.get('part3', {}),
                }

    # Normalize detected answers to p1/p2/p3 format
    detected_norm = {
        'p1': detected.get('part1', {}),
        'p2': detected.get('part2', {}),
        'p3': detected.get('part3', {}),
    }

    # Build per-question comparison list for Part 1
    p1_comparison = []
    for i in range(1, (parts_config[0] if len(parts_config) > 0 else 0) + 1):
        si = str(i)
        student_ans = detected_norm['p1'].get(si, detected_norm['p1'].get(i, ''))
        correct_ans = correct_answers.get('p1', {}).get(si, correct_answers.get('p1', {}).get(i, ''))
        is_correct = (student_ans == correct_ans and student_ans not in ('', 'X', None))
        p1_comparison.append({
            'num': i,
            'student': student_ans or '—',
            'correct': correct_ans or '—',
            'ok': is_correct,
        })

    # Build per-question comparison for Part 3
    p3_comparison = []
    for i in range(1, (parts_config[2] if len(parts_config) > 2 else 0) + 1):
        si = str(i)
        student_ans = detected_norm['p3'].get(si, detected_norm['p3'].get(i, ''))
        correct_ans = correct_answers.get('p3', {}).get(si, correct_answers.get('p3', {}).get(i, ''))
        # Convert to string for comparison (P3 values can be floats from Excel)
        s_str = str(student_ans) if student_ans not in ('', None) else ''
        c_str = str(correct_ans) if correct_ans not in ('', None) else ''
        is_correct = (s_str == c_str and s_str not in ('', 'X', 'None'))
        p3_comparison.append({
            'num': i,
            'student': s_str if s_str and s_str != 'None' else '—',
            'correct': c_str if c_str and c_str != 'None' else '—',
            'ok': is_correct,
        })

    return render(request, 'grading/submission_detail.html', {
        'sub': sub,
        'images': debug_images,
        'detail_data': detail_data,
        'detected_answers': detected,
        'scoring': scoring,
        'p2_breakdown': p2_breakdown,
        'p1_comparison': p1_comparison,
        'p3_comparison': p3_comparison,
        'parts_config': parts_config,
    })


@login_required
def submission_regrade_view(request, submission_id):
    """Chấm lại 1 bài nộp từ ảnh gốc với scoring config hiện tại."""
    sub = get_object_or_404(Submission, id=submission_id, teacher=request.user)

    if request.method != 'POST':
        return redirect('grading:submission_detail', submission_id=sub.id)

    if not sub.exam:
        messages.error(request, 'Bài nộp không thuộc đề thi nào.')
        return redirect('grading:submission_detail', submission_id=sub.id)

    exam_config_str = sub.exam.answer_key or ''
    template_code = sub.template_code or ''

    # Extract scoring config from exam's shared config
    scoring_config = None
    try:
        exam_config = json.loads(exam_config_str)
        if isinstance(exam_config, dict):
            scoring_config = exam_config.get('scoring')
    except (json.JSONDecodeError, ValueError):
        pass

    # Build answer key: prefer variant, fallback to exam config
    if sub.variant:
        answer_key_str = sub.variant.answer_key_str
    else:
        answer_key_str = exam_config_str

    # Re-grade from original image
    image_path = os.path.join(settings.MEDIA_ROOT, sub.image.name)
    result = grade_image(image_path, answer_key_str, template_code)

    if result.get('success'):
        correct_answers = parse_answer_key(answer_key_str)
        weighted = compute_weighted_score(result, scoring_config, correct_answers)

        # Parse parts counts
        parts_counts = []
        try:
            ec = json.loads(exam_config_str)
            parts_counts = ec.get('parts', [])
        except (json.JSONDecodeError, ValueError):
            pass
        p1_count = parts_counts[0] if len(parts_counts) > 0 else 0
        p2_count = parts_counts[1] if len(parts_counts) > 1 else 0
        p3_count = parts_counts[2] if len(parts_counts) > 2 else 0
        total_q = p1_count + p2_count + p3_count

        sub.status = 'completed'
        sub.student_id = result.get('sbd', '')

        if weighted:
            sub.score = weighted['weighted_score']
            sub.correct_count = (weighted['p1_correct'] +
                                 weighted['p2_correct'] +
                                 weighted['p3_correct'])
            sub.total_questions = total_q or scoring_config.get('max', sub.score)
        else:
            raw_score = result.get('score')
            sub.score = raw_score if raw_score is not None else 0
            sub.correct_count = sub.score
            sub.total_questions = total_q or result.get('max_score')

        # Save all detected answers
        sub.answers_detected = json.dumps({
            'part1': result.get('part1', {}),
            'part2': result.get('part2', {}),
            'part3': result.get('part3', {}),
        }, ensure_ascii=False)

        # Build detail with scoring breakdown
        engine_detail = result.get('detail_json', '{}')
        try:
            detail_obj = json.loads(engine_detail)
        except (json.JSONDecodeError, ValueError):
            detail_obj = {}
        detail_obj['scoring'] = {
            'weighted_score': weighted['weighted_score'] if weighted else sub.score,
            'max_score': weighted['max_score'] if weighted else sub.total_questions,
            'p1_correct': weighted['p1_correct'] if weighted else 0,
            'p1_score': weighted['p1_score'] if weighted else 0,
            'p2_score': weighted['p2_score'] if weighted else 0,
            'p3_correct': weighted['p3_correct'] if weighted else 0,
            'p3_score': weighted['p3_score'] if weighted else 0,
            'p2_detail': weighted['p2_detail'] if weighted else {},
            'p1_count': p1_count,
            'p2_count': p2_count,
            'p3_count': p3_count,
            'score_p1_per_q': scoring_config.get('p1', 0.25) if scoring_config else 0.25,
            'score_p3_per_q': scoring_config.get('p3', 0.5) if scoring_config else 0.5,
        }
        sub.detail_json = json.dumps(detail_obj, ensure_ascii=False, default=str)
        sub.graded_at = timezone.now()
        sub.processing_time = result.get('processing_time', 0)
        sub.error_message = ''
        sub.save()
        messages.success(request, f'Đã chấm lại! Điểm: {sub.score}')
    else:
        sub.status = 'error'
        sub.error_message = result.get('error', 'Unknown error')
        sub.save()
        messages.error(request, f'Chấm lại thất bại: {sub.error_message}')

    return redirect('grading:submission_detail', submission_id=sub.id)


@login_required
def submission_status_api(request, submission_id):
    """HTMX endpoint: check submission grading status."""
    sub = get_object_or_404(Submission, id=submission_id, teacher=request.user)
    
    if request.htmx:
        return render(request, 'grading/_submission_row.html', {'sub': sub})
    
    return JsonResponse({
        'id': sub.id,
        'status': sub.status,
        'score': sub.score_10,
        'grade': sub.grade_text,
    })
