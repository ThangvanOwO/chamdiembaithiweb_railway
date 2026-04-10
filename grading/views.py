from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse
from django.utils import timezone
from .models import Exam, Submission
from .forms import ExamForm, UploadForm
import json


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


# =============================================================================
# VIEWS
# =============================================================================

@login_required
def upload_view(request):
    """Upload & grade page — main feature."""
    exams = Exam.objects.filter(teacher=request.user)
    recent_submissions = Submission.objects.filter(teacher=request.user)[:10]
    
    # Get selected template (from step 1 or form POST)
    selected_template = request.GET.get('template', '') or request.POST.get('template_code', '')
    
    if request.method == 'POST' and selected_template:
        files = request.FILES.getlist('images')
        
        if files:
            created_submissions = []
            for f in files:
                sub = Submission.objects.create(
                    template_code=selected_template,
                    teacher=request.user,
                    image=f,
                    status='pending',
                )
                created_submissions.append(sub)
            
            # TODO: Trigger Celery task for grading
            # from .tasks import grade_submission
            # for sub in created_submissions:
            #     grade_submission.delay(sub.id)
            
            messages.success(request, f'Đã tải lên {len(files)} bài với mã đề {selected_template}. Đang xử lý chấm điểm...')
            
            if request.htmx:
                return render(request, 'grading/_upload_result.html', {
                    'submissions': created_submissions,
                })
            
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
    })


@login_required
def exams_view(request):
    """List all exams."""
    exams = Exam.objects.filter(teacher=request.user)
    return render(request, 'grading/exams.html', {'exams': exams})


@login_required
def exam_create_view(request):
    """Create a new exam (manual)."""
    if request.method == 'POST':
        form = ExamForm(request.POST)
        if form.is_valid():
            exam = form.save(commit=False)
            exam.teacher = request.user
            exam.save()
            messages.success(request, f'Đã tạo bài thi: {exam.title}')
            return redirect('grading:exams')
    else:
        form = ExamForm()
    
    return render(request, 'grading/exam_form.html', {
        'form': form,
        'is_edit': False,
    })


@login_required
def exam_edit_view(request, exam_id):
    """Edit an exam."""
    exam = get_object_or_404(Exam, id=exam_id, teacher=request.user)
    
    if request.method == 'POST':
        form = ExamForm(request.POST, instance=exam)
        if form.is_valid():
            form.save()
            messages.success(request, f'Đã cập nhật bài thi: {exam.title}')
            return redirect('grading:exams')
    else:
        form = ExamForm(instance=exam)
    
    return render(request, 'grading/exam_form.html', {
        'form': form,
        'exam': exam,
        'is_edit': True,
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
