from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.db.models import Avg, Count, Q
from django.utils import timezone
from datetime import timedelta
from grading.models import Exam, Submission


@login_required
def dashboard_view(request):
    """Main dashboard with stats and charts."""
    user = request.user
    today = timezone.now().date()
    
    # Submissions stats
    total_submissions = Submission.objects.filter(teacher=user)
    completed = total_submissions.filter(status='completed')
    
    stats = {
        'total_exams': Exam.objects.filter(teacher=user).count(),
        'total_graded': completed.count(),
        'today_graded': completed.filter(graded_at__date=today).count(),
        'avg_score': None,
        'pass_rate': None,
    }
    
    if completed.exists():
        avg = completed.aggregate(Avg('score'))['score__avg']
        stats['avg_score'] = round(avg, 1) if avg else 0
        
        # Pass rate (score >= 5.0)
        passed = completed.filter(score__gte=5.0).count()
        stats['pass_rate'] = round((passed / completed.count()) * 100) if completed.count() > 0 else 0
    
    # Recent exams
    recent_exams = Exam.objects.filter(teacher=user)[:5]
    
    # Recent submissions  
    recent_submissions = total_submissions[:8]
    
    # Score distribution for chart (JSON)
    import json
    distribution = {
        'Giỏi (8-10)': completed.filter(score__gte=8).count(),
        'Khá (6.5-8)': completed.filter(score__gte=6.5, score__lt=8).count(),
        'TB (5-6.5)': completed.filter(score__gte=5, score__lt=6.5).count(),
        'Yếu (<5)': completed.filter(score__lt=5).count(),
    }
    
    return render(request, 'dashboard/index.html', {
        'stats': stats,
        'recent_exams': recent_exams,
        'recent_submissions': recent_submissions,
        'distribution_json': json.dumps(distribution),
    })


@login_required
def history_view(request):
    """Grading history page."""
    submissions = Submission.objects.filter(teacher=request.user).select_related('exam')
    
    # Filters
    status_filter = request.GET.get('status', '')
    exam_filter = request.GET.get('exam', '')
    search = request.GET.get('q', '')
    
    if status_filter:
        submissions = submissions.filter(status=status_filter)
    if exam_filter:
        submissions = submissions.filter(exam_id=exam_filter)
    if search:
        submissions = submissions.filter(
            Q(student_name__icontains=search) | 
            Q(student_id__icontains=search)
        )
    
    exams = Exam.objects.filter(teacher=request.user)
    
    context = {
        'submissions': submissions[:50],
        'exams': exams,
        'current_status': status_filter,
        'current_exam': exam_filter,
        'search_query': search,
    }
    
    if request.htmx:
        return render(request, 'dashboard/_history_table.html', context)
    
    return render(request, 'dashboard/history.html', context)
