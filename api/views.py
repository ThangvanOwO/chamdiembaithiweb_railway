"""
API v1 Views — REST endpoints cho Flutter mobile app.

Endpoints:
  POST /api/v1/auth/register/   — Đăng ký tài khoản
  POST /api/v1/auth/login/      — Đăng nhập, trả token
  POST /api/v1/auth/logout/     — Xóa token
  GET  /api/v1/auth/me/         — Thông tin user hiện tại
  GET  /api/v1/dashboard/       — Dashboard stats
  GET  /api/v1/exams/           — Danh sách đề thi
  GET  /api/v1/exams/{id}/      — Chi tiết đề thi
  POST /api/v1/grade/           — Chấm ảnh (multipart image + exam_id)
  GET  /api/v1/submissions/     — Danh sách bài nộp
  GET  /api/v1/submissions/{id}/ — Chi tiết bài nộp
"""
import os
import json
import base64
import logging
import tempfile

from django.conf import settings
from django.contrib.auth import authenticate
from django.utils import timezone
from django.db import models as db_models

from rest_framework import status
from rest_framework.decorators import api_view, permission_classes, parser_classes
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.authtoken.models import Token
from rest_framework.parsers import MultiPartParser, FormParser

from django.http import FileResponse

from grading.models import Exam, ExamVariant, Submission, UserSettings, TrainingSample
from grading.grader import grade_image, parse_answer_key, compute_weighted_score
from grading.views import EXAM_TEMPLATES
from accounts.scan_billing import bill_scans

logger = logging.getLogger(__name__)


# =============================================================================
# AUTH
# =============================================================================

@api_view(['POST'])
@permission_classes([AllowAny])
def register_api(request):
    """
    POST /api/v1/auth/register/
    Username mode: {"username": "...", "password": "...", "full_name": "...", "email": "optional contact"} -> 201 + token
    Body: {"email": "...", "password": "...", "first_name": "...", "last_name": "..."}
    """
    from accounts.forms import RegisterForm, UsernameRegisterForm
    from accounts.registration import start_signup, create_username_account
    from django.core.exceptions import ValidationError
    if not isinstance(request.data, dict):
        return Response({'error': 'Dữ liệu đăng ký không hợp lệ.'}, status=400)
    fields = ('username', 'full_name', 'email', 'password', 'first_name', 'last_name', 'turnstile_token')
    if any(not isinstance(request.data.get(field, ''), str) for field in fields):
        return Response({'error': 'Dữ liệu đăng ký không hợp lệ.'}, status=400)
    if 'username' in request.data:
        form = UsernameRegisterForm({
            'username': request.data.get('username', ''),
            'full_name': request.data.get('full_name', ''),
            'email': request.data.get('email', ''),
            'password': request.data.get('password', ''),
            'password_confirm': request.data.get('password', ''),
        })
        if not form.is_valid():
            return Response({'error': ' '.join(str(error) for errors in form.errors.values() for error in errors)}, status=400)
        try:
            user = create_username_account(form.cleaned_data)
        except ValidationError as exc:
            return Response({'error': ' '.join(exc.messages)}, status=400)
        token, _ = Token.objects.get_or_create(user=user)
        return Response({'token': token.key, 'user': {
            'id': user.id, 'username': user.username, 'email': user.email,
            'full_name': user.get_full_name(), 'first_name': user.first_name,
            'last_name': user.last_name, 'is_admin': False,
        }}, status=201)
    form = RegisterForm({'email': request.data.get('email', ''),
        'password': request.data.get('password', ''),
        'password_confirm': request.data.get('password', ''),
        'full_name': (' '.join([request.data.get('first_name', ''), request.data.get('last_name', '')])).strip() or 'Giáo viên'})
    if not form.is_valid():
        return Response({'error': ' '.join(str(error) for errors in form.errors.values() for error in errors)}, status=400)
    data = dict(form.cleaned_data, first_name=request.data.get('first_name', '')[:150],
                last_name=request.data.get('last_name', '')[:150])
    try:
        start_signup(request, data, request.data.get('turnstile_token', ''))
    except ValidationError as exc:
        return Response({'error': ' '.join(exc.messages)}, status=400)
    return Response({'requires_email_verification': True,
        'message': 'Nếu email có thể đăng ký, liên kết xác minh đã được gửi. Vui lòng kiểm tra hộp thư rồi đăng nhập.'}, status=202)


@api_view(['POST'])
@permission_classes([AllowAny])
def login_api(request):
    """
    POST /api/v1/auth/login/
    Body: {"email": "username or email", "password": "..."}
    Returns: {"token": "...", "user": {...}}
    """
    if not isinstance(request.data, dict) or any(not isinstance(request.data.get(key, ''), str) for key in ('email', 'password')):
        return Response({'error': 'Dữ liệu đăng nhập không hợp lệ.'}, status=400)
    email = request.data.get('email', '').strip()
    password = request.data.get('password', '')

    if not email or not password:
        return Response(
            {'error': 'Tên tài khoản/email và mật khẩu là bắt buộc'},
            status=status.HTTP_400_BAD_REQUEST
        )

    from accounts.registration import password_login_username
    username = password_login_username(email)

    user = authenticate(request, username=username, password=password)
    if user is None:
        return Response(
            {'error': 'Tên tài khoản/email hoặc mật khẩu không đúng'},
            status=status.HTTP_401_UNAUTHORIZED
        )

    token, _ = Token.objects.get_or_create(user=user)
    from accounts.risk import current_request
    risk_request = current_request.get()
    if risk_request is not None:
        risk_request.risk_users.add(user.pk)

    return Response({
        'token': token.key,
        'user': {
            'id': user.id,
            'username': user.username,
            'email': user.email,
            'full_name': user.get_full_name() or user.email or user.username,
            'first_name': user.first_name,
            'last_name': user.last_name,
            'is_admin': user.is_superuser,
        }
    })


@api_view(['POST'])
def logout_api(request):
    """POST /api/v1/auth/logout/ — Xóa token."""
    try:
        request.user.auth_token.delete()
    except Token.DoesNotExist:
        pass
    return Response({'message': 'Đã đăng xuất'})


@api_view(['GET'])
def me_api(request):
    """GET /api/v1/auth/me/ — Thông tin user hiện tại."""
    user = request.user
    return Response({
        'id': user.id,
        'username': user.username,
        'email': user.email,
        'full_name': user.get_full_name() or user.email or user.username,
        'first_name': user.first_name,
        'last_name': user.last_name,
        'is_admin': user.is_superuser,
    })


# =============================================================================
# DASHBOARD
# =============================================================================

@api_view(['GET'])
def dashboard_api(request):
    """GET /api/v1/dashboard/ — Dashboard stats."""
    user = request.user
    exams = Exam.objects.filter(teacher=user)
    submissions = Submission.objects.filter(teacher=user)
    completed = submissions.filter(status='completed')

    total_exams = exams.count()
    total_graded = completed.count()
    avg_score = None
    pass_rate = None

    if completed.exists():
        avg = completed.aggregate(db_models.Avg('score'))['score__avg']
        avg_score = round(avg, 1) if avg is not None else None

        passing = completed.filter(score__gte=5.0).count()
        pass_rate = round(passing / completed.count() * 100, 1)

    # Recent submissions
    recent = submissions.select_related('exam')[:10]
    recent_data = [{
        'id': s.id,
        'student_id': s.student_id,
        'student_name': s.student_name,
        'exam_title': s.exam.title if s.exam else '',
        'score': s.score_10,
        'status': s.status,
        'grade_label': s.grade_label,
        'grade_text': s.grade_text,
        'uploaded_at': s.uploaded_at.isoformat(),
    } for s in recent]

    return Response({
        'stats': {
            'total_exams': total_exams,
            'total_graded': total_graded,
            'avg_score': avg_score,
            'pass_rate': pass_rate,
        },
        'recent_submissions': recent_data,
    })


# =============================================================================
# EXAMS
# =============================================================================

@api_view(['GET', 'POST'])
def exams_list_api(request):
    """
    GET  /api/v1/exams/ — Danh sách đề thi.
    POST /api/v1/exams/ — Tạo đề thi mới.
    """
    if request.method == 'POST':
        return _create_exam(request)

    # GET
    exams = Exam.objects.filter(teacher=request.user)
    data = [{
        'id': e.id,
        'title': e.title,
        'subject': e.subject,
        'num_questions': e.num_questions,
        'template_code': e.template_code,
        'variant_codes': e.variant_codes,
        'submission_count': e.submission_count,
        'graded_count': e.graded_count,
        'average_score': e.average_score,
        'parts_config': e.parts_config,
        'created_at': e.created_at.isoformat(),
    } for e in exams]
    return Response({'exams': data})


@api_view(['GET'])
def exam_detail_api(request, exam_id):
    """GET /api/v1/exams/{id}/ — Chi tiết đề thi."""
    try:
        exam = Exam.objects.get(id=exam_id, teacher=request.user)
    except Exam.DoesNotExist:
        return Response({'error': 'Không tìm thấy đề thi'}, status=404)

    variants = [{
        'id': v.id,
        'variant_code': v.variant_code,
    } for v in exam.variants.all()]

    return Response({
        'id': exam.id,
        'title': exam.title,
        'subject': exam.subject,
        'num_questions': exam.num_questions,
        'template_code': exam.template_code,
        'variant_codes': exam.variant_codes,
        'parts_config': exam.parts_config,
        'scoring_config': exam.scoring_config,
        'variants': variants,
        'submission_count': exam.submission_count,
        'graded_count': exam.graded_count,
        'average_score': exam.average_score,
        'created_at': exam.created_at.isoformat(),
    })


def _create_exam(request):
    """Internal: create exam from POST data."""
    title = request.data.get('title', '').strip()
    subject = request.data.get('subject', '').strip()
    template_code = request.data.get('template_code', '').strip()
    parts = request.data.get('parts', [0, 0, 0])
    variants = request.data.get('variants', [])

    if not title:
        return Response({'error': 'Tên đề thi là bắt buộc'}, status=status.HTTP_400_BAD_REQUEST)

    if isinstance(parts, str):
        parts = json.loads(parts)
    p1 = int(parts[0]) if len(parts) > 0 else 0
    p2 = int(parts[1]) if len(parts) > 1 else 0
    p3 = int(parts[2]) if len(parts) > 2 else 0
    num_q = p1 + p2 + p3

    config = {'parts': [p1, p2, p3]}
    exam = Exam.objects.create(
        teacher=request.user,
        title=title,
        subject=subject,
        num_questions=num_q,
        answer_key=json.dumps(config, ensure_ascii=False),
        template_code=template_code,
    )

    if isinstance(variants, str):
        variants = json.loads(variants)
    for v in variants:
        code = v.get('code', '').strip()
        if code:
            ExamVariant.objects.create(
                exam=exam,
                variant_code=code,
                answers_json=json.dumps({
                    'p1': v.get('p1', {}),
                    'p2': v.get('p2', {}),
                    'p3': v.get('p3', {}),
                }, ensure_ascii=False),
            )

    return Response({
        'id': exam.id,
        'title': exam.title,
        'message': f'Đã tạo đề thi: {exam.title}',
    }, status=status.HTTP_201_CREATED)


# =============================================================================
# EXAM DELETE
# =============================================================================

@api_view(['DELETE'])
def exam_delete_api(request, exam_id):
    """DELETE /api/v1/exams/{id}/ — Xóa đề thi."""
    try:
        exam = Exam.objects.get(id=exam_id, teacher=request.user)
    except Exam.DoesNotExist:
        return Response({'error': 'Không tìm thấy đề thi'}, status=404)
    title = exam.title
    exam.delete()
    return Response({'message': f'Đã xóa: {title}'})


# =============================================================================
# PARSE EXCEL / IMAGE — For exam import on mobile
# =============================================================================

@api_view(['POST'])
@parser_classes([MultiPartParser, FormParser])
def parse_excel_api(request):
    """
    POST /api/v1/parse-excel/
    Multipart: file (Excel .xlsx)
    Returns parsed answer data for review.
    """
    f = request.FILES.get('file')
    if not f:
        return Response({'error': 'Không có file nào được upload'}, status=400)

    if not f.name.endswith(('.xlsx', '.xls')):
        return Response({'error': 'Chỉ hỗ trợ file Excel (.xlsx, .xls)'}, status=400)

    try:
        from grading.views import _parse_excel_answer_key
        result, error = _parse_excel_answer_key(f)
        if error:
            return Response({'error': error}, status=400)
        return Response({'success': True, 'data': result})
    except Exception as e:
        logger.exception('Error parsing Excel file')
        return Response({'error': f'Lỗi đọc file: {str(e)}'}, status=400)


@api_view(['POST'])
@parser_classes([MultiPartParser, FormParser])
def parse_image_api(request):
    """
    POST /api/v1/parse-image/
    Multipart: file (image .jpg/.png)
    Returns parsed answer data from answer sheet image.
    """
    f = request.FILES.get('file')
    if not f:
        return Response({'error': 'Không có file nào được upload'}, status=400)

    allowed_ext = ('.jpg', '.jpeg', '.png', '.bmp', '.webp')
    if not f.name.lower().endswith(allowed_ext):
        return Response({'error': f'Chỉ hỗ trợ ảnh: {", ".join(allowed_ext)}'}, status=400)

    try:
        from .answer_image_import import parse_answer_image, capture_options
        result = parse_answer_image(f, capture_options(request.data))

        if not result:
            return Response({'error': 'Không thể đọc phiếu. Hãy chụp rõ hơn.'}, status=400)

        p1_ans = result.get('part1', {})
        p2_ans = result.get('part2', {})
        p3_ans = result.get('part3', {})
        made = result.get('made', '')

        p1 = {}
        for q, a in p1_ans.items():
            if a and a not in ('', 'X'):
                p1[str(q)] = a.upper()

        p2 = {}
        for q, opts in p2_ans.items():
            if isinstance(opts, dict):
                q_data = {}
                for opt_key in ('a', 'b', 'c', 'd'):
                    val = opts.get(opt_key, '')
                    if val in ('Dung', 'Đ', 'ĐÚNG'):
                        q_data[opt_key] = 'Đ'
                    elif val in ('Sai', 'S', 'SAI'):
                        q_data[opt_key] = 'S'
                    elif val:
                        q_data[opt_key] = val
                if q_data:
                    p2[str(q)] = q_data

        p3 = {}
        for q, a in p3_ans.items():
            if a and str(a).strip():
                p3[str(q)] = a

        variant_code = made if made and '?' not in str(made) else ''

        data = {
            'variants': [{
                'code': str(variant_code),
                'p1': p1, 'p2': p2, 'p3': p3,
                'p1_count': len(p1), 'p2_count': len(p2), 'p3_count': len(p3),
            }],
            'part1Count': len(p1_ans),
            'part2Count': len(p2_ans),
            'part3Count': len(p3_ans),
            'totalQuestions': len(p1_ans) + len(p2_ans) + len(p3_ans),
            'variantCount': 1,
            'source': 'image',
            'recognition_pipeline': 'exam_import_v2',
            'detect_method': result.get('detect_method'),
            'warnings': result.get('validation_warnings') or [],
        }
        return Response({'success': True, 'data': data})

    except Exception as e:
        logger.exception('Error parsing answer image')
        return Response({'error': f'Lỗi xử lý ảnh: {str(e)}'}, status=400)


# =============================================================================
# GRADING — Core endpoint for mobile app
# =============================================================================

@api_view(['POST'])
@parser_classes([MultiPartParser, FormParser])
@bill_scans()
def grade_api(request):
    """
    POST /api/v1/grade/
    Multipart form:
      - image: File ảnh phiếu thi (JPEG/PNG)
      - exam_id: ID đề thi (optional)
      - template_code: Mã template (optional, auto-detected from exam)
      - save: "true" để lưu vào DB (default: true)

    Returns JSON kết quả chấm.
    """
    image_file = request.FILES.get('image')
    if not image_file:
        return Response(
            {'error': 'Chưa gửi ảnh. Vui lòng chụp hoặc chọn ảnh phiếu thi.'},
            status=status.HTTP_400_BAD_REQUEST
        )

    exam_id = request.data.get('exam_id', '')
    template_code = request.data.get('template_code', '')
    save_to_db = request.data.get('save', 'true').lower() == 'true'
    fast_param = request.data.get('fast', '0')
    fast_mode = (str(fast_param).lower() in ['1', 'true', 'yes'])
    # Explicit Live protocol opt-in; Upload also uses fast=1, so fast is NOT a source flag.
    live_bubble_mode = request.data.get('capture_pipeline') == 'live_capture_v3'
    # Mobile Live never displays the duplicate diagnostic overlay. Keep the
    # full legacy response unless the client explicitly opts out.
    include_overlay = str(request.data.get('include_overlay', 'true')).lower() != 'false'

    # Parse corners from client (if live camera detected them)
    provided_corners = None
    corners_str = request.data.get('corners', '')
    if corners_str:
        try:
            provided_corners = json.loads(corners_str)
            if not isinstance(provided_corners, list) or len(provided_corners) != 4:
                provided_corners = None
            else:
                logger.info(f"Using client-provided corners: {provided_corners}")
        except (json.JSONDecodeError, ValueError):
            provided_corners = None

    # A separate debug build opts in. A client header alone never enables a
    # different scoring algorithm for ordinary accounts or Upload requests.
    live_background_trial = (
        live_bubble_mode and fast_mode and provided_corners is not None
        and getattr(request.user, 'is_staff', False)
        and request.headers.get('X-GradeFlow-Background-Trial') == 'box5'
        and os.environ.get('LIVE_FAST_BACKGROUND') == '1'
    )

    # Resolve exam
    selected_exam = None
    if exam_id:
        try:
            selected_exam = Exam.objects.get(id=exam_id, teacher=request.user)
            if not template_code:
                template_code = selected_exam.template_code or ''
        except Exam.DoesNotExist:
            return Response({'error': 'Không tìm thấy đề thi'}, status=404)

    # Save temp file
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix='.jpg')
    for chunk in image_file.chunks():
        tmp.write(chunk)
    tmp.close()
    tmp_path = tmp.name

    try:
        # Build answer key
        answer_key_str = ''
        exam_config_str = ''
        exam_variants = []
        scoring_config = None

        if selected_exam:
            exam_config_str = selected_exam.answer_key or ''
            exam_variants = list(selected_exam.variants.all())
            try:
                exam_config = json.loads(exam_config_str)
                if isinstance(exam_config, dict):
                    scoring_config = exam_config.get('scoring')
            except (json.JSONDecodeError, ValueError):
                pass

        # First pass with first variant or exam config
        first_answer_key = ''
        if exam_variants:
            first_answer_key = exam_variants[0].answer_key_str
        elif exam_config_str:
            first_answer_key = exam_config_str

        # Per-request Live optimization. Upload keeps its existing invocation.
        live_options = {}
        key_selection = None
        from django.conf import settings as latency_settings
        if live_bubble_mode:
            live_options['live_validation'] = True
            if live_background_trial:
                live_options['fast_background_trial'] = True
            if not selected_exam or not exam_variants:
                return Response({'success': False,
                    'error': 'Hãy chọn đề thi có mã đề và bảng đáp án đã khai báo trước khi quét.'})
            from grading.live_latency import LiveAnswerKeySelection
            key_selection = LiveAnswerKeySelection(first_answer_key,
                [(v.variant_code, v.answer_key_str) for v in exam_variants], parse_answer_key,
                strict=True, choose_early=getattr(latency_settings, 'LIVE_SINGLE_PASS_GRADING', False))
            live_options['live_answer_key_resolver'] = key_selection.resolve
        result = grade_image(tmp_path, first_answer_key, template_code, corners=provided_corners,
                             fast_mode=fast_mode, live_bubble_mode=live_bubble_mode, **live_options)

        if not result or not result.get('success'):
            return Response({
                'success': False,
                'error': (result or {}).get('error', 'Không nhận diện được phiếu thi'),
                'processing_time': (result or {}).get('processing_time', 0),
            })

        # Match variant by detected mã đề
        matched_variant = None
        detected_ma_de = result.get('made', '')
        if live_bubble_mode:
            try:
                key_selection.validate(detected_ma_de)
            except ValueError as exc:
                return Response({'success': False, 'error': str(exc)})
        if exam_variants and detected_ma_de:
            for v in exam_variants:
                if v.variant_code == str(detected_ma_de):
                    matched_variant = v
                    break
        if not matched_variant and exam_variants:
            if live_bubble_mode:
                return Response({'success': False, 'error': 'Không tìm thấy mã đề khớp. Không chấm bài.'})
            matched_variant = exam_variants[0]

        # Re-grade with correct variant if different
        if matched_variant:
            answer_key_str = matched_variant.answer_key_str
            used_answer_key = key_selection.used_key if key_selection else first_answer_key
            if answer_key_str != used_answer_key:
                retry_options = {}
                if live_bubble_mode:
                    retry_options = {'live_validation': True, 'live_answer_key_resolver':
                        LiveAnswerKeySelection(answer_key_str,
                            [(matched_variant.variant_code, answer_key_str)], parse_answer_key, strict=True).resolve}
                    if live_options.get('fast_background_trial'):
                        retry_options['fast_background_trial'] = True
                result = grade_image(tmp_path, answer_key_str, template_code, corners=provided_corners,
                                     fast_mode=fast_mode, live_bubble_mode=live_bubble_mode, **retry_options)
                if not result or not result.get('success'):
                    return Response({
                        'success': False,
                        'error': (result or {}).get('error', 'Chấm lại thất bại'),
                    })
        else:
            answer_key_str = exam_config_str

        # Calculate weighted score
        correct_answers = parse_answer_key(answer_key_str)
        weighted = compute_weighted_score(result, scoring_config, correct_answers)

        # Parts counts
        parts_counts = []
        try:
            ec = json.loads(exam_config_str) if exam_config_str else None
            parts_counts = ec.get('parts', []) if ec else []
        except (json.JSONDecodeError, ValueError):
            pass
        p1_count = parts_counts[0] if len(parts_counts) > 0 else 0
        p2_count = parts_counts[1] if len(parts_counts) > 1 else 0
        p3_count = parts_counts[2] if len(parts_counts) > 2 else 0
        total_q = p1_count + p2_count + p3_count

        # Build response
        if weighted:
            final_score = weighted['weighted_score']
            correct_count = weighted['p1_correct'] + weighted['p2_correct'] + weighted['p3_correct']
            total_questions = total_q or scoring_config.get('max', final_score) if scoring_config else total_q
        else:
            raw_score = result.get('score')
            final_score = raw_score if raw_score is not None else 0
            correct_count = final_score
            total_questions = total_q or result.get('max_score')

        # Save to DB if requested
        submission_id = None
        if save_to_db and selected_exam:
            sub = Submission.objects.create(
                exam=selected_exam,
                variant=matched_variant,
                template_code=template_code,
                teacher=request.user,
                image=image_file,
                status='completed',
                student_id=result.get('sbd', ''),
                score=final_score,
                correct_count=correct_count,
                total_questions=total_questions,
                answers_detected=json.dumps({
                    'part1': result.get('part1', {}),
                    'part2': result.get('part2', {}),
                    'part3': result.get('part3', {}),
                }, ensure_ascii=False, default=str),
                detail_json=result.get('detail_json', '{}'),
                graded_at=timezone.now(),
                processing_time=result.get('processing_time', 0),
            )
            submission_id = sub.id

        request.billable_scans = 1

        # Determine grade
        score_10 = round(final_score, 2) if final_score is not None else None
        if score_10 is not None:
            if score_10 >= 8:
                grade_label, grade_text = 'excellent', 'Giỏi'
            elif score_10 >= 6.5:
                grade_label, grade_text = 'good', 'Khá'
            elif score_10 >= 5:
                grade_label, grade_text = 'average', 'Trung bình'
            else:
                grade_label, grade_text = 'poor', 'Yếu'
        else:
            grade_label, grade_text = 'pending', 'Chờ chấm'

        # Encode result image as base64 for mobile display
        result_image_b64 = ''
        result_img_path = result.get('result_image_path', '')
        if result_img_path and os.path.exists(result_img_path):
            try:
                with open(result_img_path, 'rb') as f:
                    result_image_b64 = base64.b64encode(f.read()).decode('utf-8')
            except Exception:
                pass

        # Also encode overlay image
        overlay_image_b64 = ''
        base_path = os.path.splitext(tmp_path)[0]
        overlay_path = f"{base_path}_overlay.jpg"
        if include_overlay and os.path.exists(overlay_path):
            try:
                with open(overlay_path, 'rb') as f:
                    overlay_image_b64 = base64.b64encode(f.read()).decode('utf-8')
            except Exception:
                pass

        # Tự động lưu ảnh kết quả vào tests/ketqua khi app quét xong
        try:
            from django.conf import settings
            from pathlib import Path
            import shutil
            ketqua_dir = Path(settings.BASE_DIR) / 'tests' / 'ketqua'
            ketqua_dir.mkdir(parents=True, exist_ok=True)
            ts = timezone.now().strftime("%Y%m%d_%H%M%S")
            sbd_safe = str(result.get('sbd', '')).replace('?', '_') or 'nosbd'
            md_safe = str(result.get('made', '')).replace('?', '_') or 'nomd'
            orig_name = Path(image_file.name).stem if hasattr(image_file, 'name') and image_file.name else 'mobile_scan'

            if result_img_path and os.path.exists(result_img_path):
                dst_res = ketqua_dir / f"{ts}_{orig_name}_sbd_{sbd_safe}_md_{md_safe}_result.jpg"
                shutil.copy2(result_img_path, dst_res)
                logger.info(f"Saved result image to {dst_res}")

            if overlay_path and os.path.exists(overlay_path):
                dst_ov = ketqua_dir / f"{ts}_{orig_name}_sbd_{sbd_safe}_md_{md_safe}_overlay.jpg"
                shutil.copy2(overlay_path, dst_ov)
                logger.info(f"Saved overlay image to {dst_ov}")
        except Exception as e_kq:
            logger.warning(f"Could not copy to tests/ketqua: {e_kq}")

        if live_background_trial and result_img_path and os.path.isfile(result_img_path):
            try:
                from pathlib import Path
                import shutil
                from uuid import uuid4

                capture_dir = Path(settings.BASE_DIR) / 'tests' / 'test_ketqua' / 'camera_captures'
                capture_dir.mkdir(parents=True, exist_ok=True)
                prefix = f"{timezone.now():%Y%m%d_%H%M%S_%f}_{uuid4().hex[:8]}"
                shutil.copy2(tmp_path, capture_dir / f'{prefix}_input.jpg')
                if result_img_path and os.path.isfile(result_img_path):
                    shutil.copy2(result_img_path, capture_dir / f'{prefix}_result.jpg')
                if os.path.isfile(overlay_path):
                    shutil.copy2(overlay_path, capture_dir / f'{prefix}_overlay.jpg')
                metadata = {key: result.get(key) for key in (
                    'success', 'sbd', 'made', 'score', 'max_score', 'processing_time',
                    'part1', 'part2', 'part3', 'offsets', 'scan_quality',
                    'validation_warnings', 'preprocess_mode',
                )}
                (capture_dir / f'{prefix}_result.json').write_text(
                    json.dumps(metadata, ensure_ascii=False, indent=2, default=str),
                    encoding='utf-8',
                )
            except Exception:
                logger.exception('Could not save Live background trial evidence')

        # Encode name crop image
        name_image_b64 = ''
        name_img_path = result.get('name_image_path', '')
        if name_img_path and os.path.exists(name_img_path):
            try:
                with open(name_img_path, 'rb') as f:
                    name_image_b64 = base64.b64encode(f.read()).decode('utf-8')
            except Exception:
                pass

        # Build correct answers map for comparison
        correct_map = {}
        if correct_answers:
            for k, v in correct_answers.items():
                correct_map[str(k)] = v

        # [IMPROVE] Image quality scoring — cảnh báo ảnh xấu cho mobile app
        scan_quality = result.get('scan_quality', 'OK')
        quality_warning = ''
        if scan_quality == 'REJECT_SCAN':
            quality_warning = 'Ảnh quá mờ hoặc không rõ. Vui lòng chụp lại với ánh sáng tốt hơn.'
        elif scan_quality == 'LOW_QUALITY':
            quality_warning = 'Ảnh chất lượng thấp. Kết quả có thể chưa chính xác.'

        return Response({
            'success': True,
            'submission_id': submission_id,
            'sbd': result.get('sbd', ''),
            'made': result.get('made', ''),
            'score': score_10,
            'correct_count': correct_count,
            'total_questions': total_questions,
            'grade_label': grade_label,
            'grade_text': grade_text,
            'scores': result.get('scores', {}),
            'part1': {str(k): v for k, v in result.get('part1', {}).items()},
            'part2': {str(k): v for k, v in result.get('part2', {}).items()},
            'part3': {str(k): v for k, v in result.get('part3', {}).items()},
            'correct_answers': correct_map,
            'weighted': {
                'p1_score': weighted['p1_score'] if weighted else 0,
                'p2_score': weighted['p2_score'] if weighted else 0,
                'p3_score': weighted['p3_score'] if weighted else 0,
                'p1_correct': weighted['p1_correct'] if weighted else 0,
                'p2_correct': weighted['p2_correct'] if weighted else 0,
                'p3_correct': weighted['p3_correct'] if weighted else 0,
            } if weighted else None,
            'detect_method': result.get('detect_method', ''),
            'scan_quality': scan_quality,
            'quality_warning': quality_warning,
            'processing_time': result.get('processing_time', 0),
            'result_image': result_image_b64,
            'overlay_image': overlay_image_b64,
            'name_image': name_image_b64,
            'debug_log': result.get('debug_log', ''),
            'avg_confidence': result.get('avg_confidence', 0),
            'preprocess_mode': result.get('preprocess_mode', ''),
            'offsets': result.get('offsets', {}),
            'validation_warnings': result.get('validation_warnings', []),
        })

    except Exception as e:
        logger.error(f"grade_api error: {e}", exc_info=True)
        return Response({
            'success': False,
            'error': str(e),
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    finally:
        if os.path.exists(tmp_path):
            try:
                os.unlink(tmp_path)
            except Exception:
                pass


# =============================================================================
# SUBMISSIONS
# =============================================================================

@api_view(['GET'])
def submissions_list_api(request):
    """
    GET /api/v1/submissions/?exam_id=X&limit=20
    """
    from toolbox.views import positive_int
    exam_id = positive_int(request.query_params.get('exam_id'), 'exam_id')
    limit = min(positive_int(request.query_params.get('limit'), 'limit', 20), 200)
    page = positive_int(request.query_params.get('page'), 'page', 1)

    qs = Submission.objects.filter(teacher=request.user).select_related('exam', 'toolbox_review__roster_entry')
    if exam_id:
        qs = qs.filter(exam_id=exam_id)
    query = request.query_params.get('q', '').strip()[:200]
    from django.db.models import Exists, OuterRef, Q
    from toolbox.models import ExamRosterEntry
    from toolbox.views import owned_class
    classroom_id = positive_int(request.query_params.get('classroom_id'), 'classroom_id')
    if classroom_id:
        owned_class(request, classroom_id)
        entries = ExamRosterEntry.objects.filter(exam_id=OuterRef('exam_id'), student_id=OuterRef('student_id'),
                                                 classroom_id=classroom_id, active=True)
        qs = qs.annotate(_in_roster_class=Exists(entries)).filter(Q(_in_roster_class=True, toolbox_review__roster_entry__isnull=True) |
             Q(toolbox_review__roster_entry__classroom_id=classroom_id, toolbox_review__roster_entry__active=True))
    if query:
        named_entries = ExamRosterEntry.objects.filter(exam_id=OuterRef('exam_id'), student_id=OuterRef('student_id'),
                                                       student_name__icontains=query, active=True)
        qs = qs.annotate(_roster_name_match=Exists(named_entries)).filter(Q(student_id__icontains=query) |
             Q(student_name__icontains=query) | Q(exam__title__icontains=query) |
             Q(_roster_name_match=True, toolbox_review__roster_entry__isnull=True) |
             Q(toolbox_review__roster_entry__student_name__icontains=query, toolbox_review__roster_entry__active=True))
    state = request.query_params.get('status', '')
    if state in ('completed', 'pending', 'processing', 'error'):
        qs = qs.filter(status=state)
    elif state == 'unfinished':
        qs = qs.exclude(status='completed')
    qs = qs.order_by('-uploaded_at', '-id')
    count = qs.count()
    start = (page - 1) * limit
    submissions = list(qs[start:start + limit])
    entries = {(r.exam_id, r.student_id): r for r in ExamRosterEntry.objects.filter(active=True,
        exam__teacher=request.user, exam_id__in={s.exam_id for s in submissions},
        student_id__in={s.student_id.strip() for s in submissions})}
    from toolbox.reports import review_of
    def roster_entry(sub):
        review = review_of(sub)
        if review and review.roster_entry_id:
            return review.roster_entry if review.roster_entry.active else None
        return entries.get((sub.exam_id, sub.student_id.strip()))
    names = {s.pk: roster_entry(s) for s in submissions}
    data = [{
        'id': s.id,
        'student_id': s.student_id,
        'student_name': s.student_name or (names[s.pk].student_name if names[s.pk] else ''),
        'class_name': names[s.pk].class_name if names[s.pk] else '',
        'exam_id': s.exam_id,
        'exam_title': s.exam.title if s.exam else '',
        'status': s.status,
        'score': s.score_10,
        'correct_count': s.correct_count,
        'total_questions': s.total_questions,
        'grade_label': s.grade_label,
        'grade_text': s.grade_text,
        'uploaded_at': s.uploaded_at.isoformat(),
        'processing_time': s.processing_time,
    } for s in submissions]

    return Response({'submissions': data, 'count': count, 'page': page, 'has_more': start + limit < count})


@api_view(['GET'])
def submission_detail_api(request, submission_id):
    """GET /api/v1/submissions/{id}/ — Chi tiết bài nộp."""
    try:
        sub = Submission.objects.select_related('exam', 'variant').get(
            id=submission_id, teacher=request.user
        )
    except Submission.DoesNotExist:
        return Response({'error': 'Không tìm thấy bài nộp'}, status=404)

    # Parse detected answers
    answers = {}
    if sub.answers_detected:
        try:
            answers = json.loads(sub.answers_detected)
        except (json.JSONDecodeError, ValueError):
            pass

    # Parse detail
    detail = {}
    if sub.detail_json:
        try:
            detail = json.loads(sub.detail_json)
        except (json.JSONDecodeError, ValueError):
            pass

    return Response({
        'id': sub.id,
        'image_url': sub.image.url if sub.image else '',
        'student_id': sub.student_id,
        'student_name': sub.student_name,
        'exam_id': sub.exam_id,
        'exam_title': sub.exam.title if sub.exam else '',
        'variant_code': sub.variant.variant_code if sub.variant else '',
        'template_code': sub.template_code,
        'status': sub.status,
        'score': sub.score_10,
        'correct_count': sub.correct_count,
        'total_questions': sub.total_questions,
        'grade_label': sub.grade_label,
        'grade_text': sub.grade_text,
        'answers_detected': answers,
        'detail': detail,
        'error_message': sub.error_message,
        'uploaded_at': sub.uploaded_at.isoformat(),
        'graded_at': sub.graded_at.isoformat() if sub.graded_at else None,
        'processing_time': sub.processing_time,
    })


# =============================================================================
# TEMPLATES — List available answer sheet templates with preview images
# =============================================================================

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def templates_list_api(request):
    """
    GET /api/v1/templates/
    Returns list of available answer sheet templates with metadata + preview image URLs.
    """
    base_url = request.build_absolute_uri('/api/v1/templates/')
    result = []
    for t in EXAM_TEMPLATES:
        code = t['code']
        folder = t.get('folder', '')
        # Find preview images
        template_dir = os.path.join(settings.BASE_DIR, 'cacmaubaithi', folder)
        image_urls = []
        if os.path.isdir(template_dir):
            files = sorted(os.listdir(template_dir))
            for f in files:
                if f.lower().endswith(('.jpg', '.jpeg', '.png')):
                    image_urls.append(f'{base_url}{code}/image/{f}')

        result.append({
            'code': code,
            'label': t.get('label', code),
            'parts': t.get('parts', [0, 0, 0]),
            'total': t.get('total', 0),
            'desc': t.get('desc', ''),
            'pages': t.get('pages', 1),
            'images': image_urls,
        })

    return Response({'templates': result})


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def template_image_api(request, code, filename):
    """
    GET /api/v1/templates/<code>/image/<filename>
    Serve a template preview image.
    """
    # Find template by code
    template = next((t for t in EXAM_TEMPLATES if t['code'] == code), None)
    if not template:
        return Response({'error': 'Template not found'}, status=404)

    folder = template.get('folder', '')
    image_path = os.path.join(settings.BASE_DIR, 'cacmaubaithi', folder, filename)

    if not os.path.isfile(image_path):
        return Response({'error': 'Image not found'}, status=404)

    return FileResponse(open(image_path, 'rb'), content_type='image/jpeg')


# =============================================================================
# USER SETTINGS
# =============================================================================

@api_view(['GET', 'PUT', 'PATCH'])
@permission_classes([IsAuthenticated])
def user_settings_api(request):
    """
    GET  /api/v1/settings/          — Lấy settings hiện tại
    PUT  /api/v1/settings/          — Cập nhật
    Body: { "temp_retention_days": 30 }
    """
    settings_obj, _created = UserSettings.objects.get_or_create(user=request.user)

    if request.method == 'GET':
        return Response({
            'temp_retention_days': settings_obj.temp_retention_days,
            'contribute_training_data': settings_obj.contribute_training_data,
            'retention_choices': [
                {'value': v, 'label': lbl}
                for v, lbl in UserSettings.RETENTION_CHOICES
            ],
        })

    # PUT / PATCH
    days = request.data.get('temp_retention_days')
    if days is not None:
        try:
            days = int(days)
        except (TypeError, ValueError):
            return Response({'error': 'temp_retention_days phải là số'}, status=400)
        valid = {v for v, _ in UserSettings.RETENTION_CHOICES}
        if days not in valid:
            return Response({'error': f'Giá trị không hợp lệ. Chỉ chấp nhận: {sorted(valid)}'}, status=400)
        settings_obj.temp_retention_days = days

    contrib = request.data.get('contribute_training_data')
    if contrib is not None:
        settings_obj.contribute_training_data = bool(contrib)

    settings_obj.save()

    return Response({
        'success': True,
        'temp_retention_days': settings_obj.temp_retention_days,
        'contribute_training_data': settings_obj.contribute_training_data,
    })


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def cleanup_now_api(request):
    """
    POST /api/v1/settings/cleanup-now/
    Xóa ngay tất cả ảnh đã chấm của user hiện tại (ngoài DB row).
    Dùng khi user bấm 'Xóa ngay' ở Settings.
    """
    user = request.user
    total_files = 0
    total_size = 0

    subs = Submission.objects.filter(teacher=user).exclude(image='')
    for sub in subs:
        if not sub.image:
            continue
        try:
            image_path = sub.image.path
        except Exception:
            continue
        if not image_path or not os.path.exists(image_path):
            continue

        base = os.path.splitext(image_path)[0]
        related = [
            image_path,
            f"{base}_result.jpg",
            f"{base}_overlay.jpg",
            f"{base}_name.jpg",
        ]
        for p in related:
            if os.path.exists(p):
                try:
                    total_size += os.path.getsize(p)
                    os.remove(p)
                    total_files += 1
                except OSError:
                    pass

        sub.image = ''
        sub.save(update_fields=['image'])

    return Response({
        'success': True,
        'files_deleted': total_files,
        'bytes_freed': total_size,
        'mb_freed': round(total_size / (1024 * 1024), 2),
    })


# =============================================================================
# TRAINING DATA COLLECTION (Active Learning)
# =============================================================================

_MAX_TRAINING_FILE_BYTES = 10 * 1024 * 1024   # 10 MB


@api_view(['POST'])
@permission_classes([IsAuthenticated])
@parser_classes([MultiPartParser, FormParser])
def training_upload_api(request):
    """
    POST /api/v1/training/upload/
    Multipart:
      image: JPEG file
      made, sbd, template_code, answers_json, confidence (form fields)
      submission_id (optional)

    Chỉ accept nếu user đã bật opt-in `contribute_training_data`.
    """
    user = request.user
    settings_obj, _ = UserSettings.objects.get_or_create(user=user)

    if not settings_obj.contribute_training_data:
        return Response(
            {'error': 'Bạn chưa bật tùy chọn đóng góp ảnh trong Cài đặt.'},
            status=403,
        )

    img = request.FILES.get('image')
    if not img:
        return Response({'error': 'Thiếu file ảnh.'}, status=400)
    if img.size > _MAX_TRAINING_FILE_BYTES:
        return Response({'error': 'Ảnh vượt quá 10MB.'}, status=400)

    made = (request.data.get('made') or '').strip()
    sbd = (request.data.get('sbd') or '').strip()
    template_code = (request.data.get('template_code') or '').strip()
    answers_json = request.data.get('answers_json') or ''
    try:
        confidence = float(request.data.get('confidence') or 1.0)
    except (TypeError, ValueError):
        confidence = 1.0

    submission = None
    sub_id = request.data.get('submission_id')
    if sub_id:
        try:
            submission = Submission.objects.filter(id=int(sub_id), teacher=user).first()
        except (TypeError, ValueError):
            submission = None

    sample = TrainingSample.objects.create(
        teacher=user,
        submission=submission,
        image=img,
        made=made,
        sbd=sbd,
        template_code=template_code,
        answers_json=answers_json,
        confidence=confidence,
    )

    return Response({
        'success': True,
        'id': sample.id,
        'size': img.size,
    }, status=201)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def training_stats_api(request):
    """
    GET /api/v1/training/stats/
    Admin-only. Trả về số lượng + tổng dung lượng training samples.
    """
    if not request.user.is_superuser:
        return Response({'error': 'Chỉ admin mới xem được.'}, status=403)

    samples = TrainingSample.objects.all()
    count = samples.count()
    total_bytes = 0
    last_uploaded = None
    for s in samples.only('image', 'uploaded_at'):
        try:
            if s.image and os.path.exists(s.image.path):
                total_bytes += os.path.getsize(s.image.path)
        except Exception:
            pass
        if last_uploaded is None or (s.uploaded_at and s.uploaded_at > last_uploaded):
            last_uploaded = s.uploaded_at

    return Response({
        'count': count,
        'total_bytes': total_bytes,
        'total_mb': round(total_bytes / (1024 * 1024), 2),
        'last_uploaded': last_uploaded.isoformat() if last_uploaded else None,
        'contributors': TrainingSample.objects.values_list('teacher', flat=True).distinct().count(),
    })


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def training_download_api(request):
    """
    GET /api/v1/training/download/
    Admin-only. Stream ZIP chứa images/*.jpg + labels.json.
    """
    if not request.user.is_superuser:
        return Response({'error': 'Chỉ admin mới tải được.'}, status=403)

    import zipfile
    import io
    import json as _json
    from django.http import HttpResponse
    from datetime import datetime

    buf = io.BytesIO()
    labels = []
    with zipfile.ZipFile(buf, 'w', zipfile.ZIP_DEFLATED) as zf:
        for sample in TrainingSample.objects.select_related('teacher').all():
            if not sample.image:
                continue
            try:
                path = sample.image.path
                if not os.path.exists(path):
                    continue
                arcname = f"images/sample_{sample.id:06d}.jpg"
                zf.write(path, arcname)
                labels.append({
                    'id': sample.id,
                    'file': arcname,
                    'teacher': sample.teacher.username,
                    'made': sample.made,
                    'sbd': sample.sbd,
                    'template_code': sample.template_code,
                    'confidence': sample.confidence,
                    'uploaded_at': sample.uploaded_at.isoformat(),
                    'answers': _safe_json_loads(sample.answers_json),
                })
            except Exception as e:
                logger.warning(f"Training download skip sample {sample.id}: {e}")

        zf.writestr('labels.json', _json.dumps(labels, ensure_ascii=False, indent=2))
        zf.writestr('README.txt',
                    f"GradeFlow Training Samples\n"
                    f"Exported: {datetime.now().isoformat()}\n"
                    f"Total samples: {len(labels)}\n")

    buf.seek(0)
    resp = HttpResponse(buf.getvalue(), content_type='application/zip')
    fname = f"training_samples_{datetime.now().strftime('%Y%m%d_%H%M%S')}.zip"
    resp['Content-Disposition'] = f'attachment; filename="{fname}"'
    return resp


def _safe_json_loads(s):
    try:
        import json as _j
        return _j.loads(s) if s else None
    except Exception:
        return None


# =============================================================================
# ADMIN — Users management
# =============================================================================

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def admin_users_api(request):
    """
    GET /api/v1/admin/users/
    Admin-only. Danh sách tất cả user + số đề thi mỗi người tạo.
    """
    if not request.user.is_superuser:
        return Response({'error': 'Chỉ admin mới xem được.'}, status=403)

    from django.contrib.auth.models import User

    users = User.objects.all().order_by('-date_joined')
    result = []
    for u in users:
        exam_count = Exam.objects.filter(teacher=u).count()
        submission_count = Submission.objects.filter(teacher=u).count()
        result.append({
            'id': u.id,
            'username': u.username,
            'email': u.email,
            'full_name': f"{u.first_name} {u.last_name}".strip() or u.username,
            'is_admin': u.is_superuser,
            'is_active': u.is_active,
            'date_joined': u.date_joined.isoformat(),
            'last_login': u.last_login.isoformat() if u.last_login else None,
            'exam_count': exam_count,
            'submission_count': submission_count,
        })

    return Response({
        'total': len(result),
        'users': result,
    })
