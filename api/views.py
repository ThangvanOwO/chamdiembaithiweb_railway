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

from grading.models import Exam, ExamVariant, Submission
from grading.grader import grade_image, parse_answer_key, compute_weighted_score

logger = logging.getLogger(__name__)


# =============================================================================
# AUTH
# =============================================================================

@api_view(['POST'])
@permission_classes([AllowAny])
def register_api(request):
    """
    POST /api/v1/auth/register/
    Body: {"email": "...", "password": "...", "first_name": "...", "last_name": "..."}
    """
    from django.contrib.auth.models import User

    email = request.data.get('email', '').strip()
    password = request.data.get('password', '')
    first_name = request.data.get('first_name', '').strip()
    last_name = request.data.get('last_name', '').strip()

    if not email or not password:
        return Response(
            {'error': 'Email và mật khẩu là bắt buộc'},
            status=status.HTTP_400_BAD_REQUEST
        )
    if len(password) < 6:
        return Response(
            {'error': 'Mật khẩu phải có ít nhất 6 ký tự'},
            status=status.HTTP_400_BAD_REQUEST
        )
    if User.objects.filter(email=email).exists():
        return Response(
            {'error': 'Email đã được sử dụng'},
            status=status.HTTP_400_BAD_REQUEST
        )

    user = User.objects.create_user(
        username=email,
        email=email,
        password=password,
        first_name=first_name,
        last_name=last_name,
    )
    token, _ = Token.objects.get_or_create(user=user)

    return Response({
        'token': token.key,
        'user': {
            'id': user.id,
            'email': user.email,
            'full_name': user.get_full_name() or user.email,
            'first_name': user.first_name,
            'last_name': user.last_name,
        }
    }, status=status.HTTP_201_CREATED)


@api_view(['POST'])
@permission_classes([AllowAny])
def login_api(request):
    """
    POST /api/v1/auth/login/
    Body: {"email": "...", "password": "..."}
    Returns: {"token": "...", "user": {...}}
    """
    email = request.data.get('email', '').strip()
    password = request.data.get('password', '')

    if not email or not password:
        return Response(
            {'error': 'Email và mật khẩu là bắt buộc'},
            status=status.HTTP_400_BAD_REQUEST
        )

    # Django allauth uses email as username
    from django.contrib.auth.models import User
    try:
        user_obj = User.objects.get(email=email)
        username = user_obj.username
    except User.DoesNotExist:
        username = email

    user = authenticate(request, username=username, password=password)
    if user is None:
        return Response(
            {'error': 'Email hoặc mật khẩu không đúng'},
            status=status.HTTP_401_UNAUTHORIZED
        )

    token, _ = Token.objects.get_or_create(user=user)

    return Response({
        'token': token.key,
        'user': {
            'id': user.id,
            'email': user.email,
            'full_name': user.get_full_name() or user.email,
            'first_name': user.first_name,
            'last_name': user.last_name,
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
        'email': user.email,
        'full_name': user.get_full_name() or user.email,
        'first_name': user.first_name,
        'last_name': user.last_name,
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
        import tempfile as _tempfile
        suffix = os.path.splitext(f.name)[1]
        with _tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
            for chunk in f.chunks():
                tmp.write(chunk)
            tmp_path = tmp.name

        from grading.engine import hi as engine
        result = engine.process_sheet(tmp_path, correct_answers=None, debug=False)

        # Cleanup
        base_tmp = os.path.splitext(tmp_path)[0]
        for sfx in ['', '_result.jpg', '_overlay.jpg', '_name.jpg',
                     '_calibration.jpg', '_gray.jpg', '_thresh.jpg',
                     '_cleaned.jpg', '_detect.jpg']:
            try:
                p = tmp_path if sfx == '' else f"{base_tmp}{sfx}"
                if os.path.exists(p):
                    os.unlink(p)
            except OSError:
                pass

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

        variant_code = made if made and '?' not in str(made) else '001'

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

        result = grade_image(tmp_path, first_answer_key, template_code)

        if not result or not result.get('success'):
            return Response({
                'success': False,
                'error': (result or {}).get('error', 'Không nhận diện được phiếu thi'),
                'processing_time': (result or {}).get('processing_time', 0),
            })

        # Match variant by detected mã đề
        matched_variant = None
        detected_ma_de = result.get('made', '')
        if exam_variants and detected_ma_de:
            for v in exam_variants:
                if v.variant_code == str(detected_ma_de):
                    matched_variant = v
                    break
        if not matched_variant and exam_variants:
            matched_variant = exam_variants[0]

        # Re-grade with correct variant if different
        if matched_variant:
            answer_key_str = matched_variant.answer_key_str
            if answer_key_str != first_answer_key:
                result = grade_image(tmp_path, answer_key_str, template_code)
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
        if os.path.exists(overlay_path):
            try:
                with open(overlay_path, 'rb') as f:
                    overlay_image_b64 = base64.b64encode(f.read()).decode('utf-8')
            except Exception:
                pass

        # Build correct answers map for comparison
        correct_map = {}
        if correct_answers:
            for k, v in correct_answers.items():
                correct_map[str(k)] = v

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
            'processing_time': result.get('processing_time', 0),
            'result_image': result_image_b64,
            'overlay_image': overlay_image_b64,
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
    exam_id = request.query_params.get('exam_id', '')
    limit = int(request.query_params.get('limit', '20'))

    qs = Submission.objects.filter(teacher=request.user).select_related('exam')
    if exam_id:
        qs = qs.filter(exam_id=exam_id)

    submissions = qs[:limit]
    data = [{
        'id': s.id,
        'student_id': s.student_id,
        'student_name': s.student_name,
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

    return Response({'submissions': data})


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
