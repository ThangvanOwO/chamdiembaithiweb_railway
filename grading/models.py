from django.db import models
from django.contrib.auth.models import User
import json


class Exam(models.Model):
    """A test/exam with answer key."""
    
    teacher = models.ForeignKey(User, on_delete=models.CASCADE, related_name='exams')
    title = models.CharField('Tên bài thi', max_length=200)
    subject = models.CharField('Môn', max_length=100, blank=True, default='')
    num_questions = models.PositiveIntegerField('Số câu hỏi', default=40)
    answer_key = models.TextField(
        'Đáp án đúng',
        help_text='Nhập đáp án theo thứ tự, phân cách bởi dấu phẩy. VD: A,B,C,D,A,B,...',
        blank=True,
        default=''
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Bài thi'
        verbose_name_plural = 'Bài thi'
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.title} ({self.num_questions} câu)"
    
    @property
    def answer_list(self):
        """Returns answer key as a list."""
        if self.answer_key:
            return [a.strip().upper() for a in self.answer_key.split(',') if a.strip()]
        return []
    
    @property
    def submission_count(self):
        return self.submissions.count()
    
    @property
    def graded_count(self):
        return self.submissions.filter(status='completed').count()
    
    @property
    def average_score(self):
        completed = self.submissions.filter(status='completed')
        if completed.exists():
            return round(completed.aggregate(models.Avg('score'))['score__avg'], 1)
        return None


class Submission(models.Model):
    """A student's exam submission (uploaded image + grading result)."""
    
    STATUS_CHOICES = [
        ('pending', 'Chờ xử lý'),
        ('processing', 'Đang chấm'),
        ('completed', 'Đã chấm'),
        ('error', 'Lỗi'),
    ]
    
    exam = models.ForeignKey(Exam, on_delete=models.CASCADE, related_name='submissions', null=True, blank=True)
    teacher = models.ForeignKey(User, on_delete=models.CASCADE, related_name='submissions')
    template_code = models.CharField('Mã đề', max_length=30, blank=True, default='')
    student_name = models.CharField('Tên học sinh', max_length=200, blank=True, default='')
    student_id = models.CharField('Mã học sinh', max_length=50, blank=True, default='')
    
    # Upload
    image = models.ImageField('Ảnh bài làm', upload_to='submissions/%Y/%m/')
    uploaded_at = models.DateTimeField(auto_now_add=True)
    
    # Grading results
    status = models.CharField('Trạng thái', max_length=20, choices=STATUS_CHOICES, default='pending')
    score = models.FloatField('Điểm', null=True, blank=True)
    correct_count = models.PositiveIntegerField('Số câu đúng', null=True, blank=True)
    total_questions = models.PositiveIntegerField('Tổng câu', null=True, blank=True)
    answers_detected = models.TextField(
        'Đáp án phát hiện',
        blank=True,
        default='',
        help_text='JSON list of detected answers'
    )
    detail_json = models.TextField(
        'Chi tiết kết quả',
        blank=True,
        default='',
        help_text='JSON detail of per-question results'
    )
    error_message = models.TextField('Thông báo lỗi', blank=True, default='')
    graded_at = models.DateTimeField('Thời gian chấm', null=True, blank=True)
    processing_time = models.FloatField('Thời gian xử lý (giây)', null=True, blank=True)

    class Meta:
        verbose_name = 'Bài nộp'
        verbose_name_plural = 'Bài nộp'
        ordering = ['-uploaded_at']

    def __str__(self):
        return f"{self.student_name or 'N/A'} — {self.exam.title} — {self.get_status_display()}"
    
    @property
    def score_10(self):
        """Score on 10-point scale."""
        if self.correct_count is not None and self.total_questions:
            return round((self.correct_count / self.total_questions) * 10, 1)
        return None
    
    @property
    def grade_label(self):
        """Returns label: Giỏi/Khá/TB/Yếu."""
        if self.score_10 is None:
            return 'pending'
        if self.score_10 >= 8:
            return 'excellent'
        elif self.score_10 >= 6.5:
            return 'good'
        elif self.score_10 >= 5:
            return 'average'
        else:
            return 'poor'
    
    @property
    def grade_text(self):
        labels = {
            'excellent': 'Giỏi',
            'good': 'Khá',
            'average': 'Trung bình',
            'poor': 'Yếu',
            'pending': 'Chờ chấm',
        }
        return labels.get(self.grade_label, 'N/A')
    
    @property
    def detected_answers_list(self):
        if self.answers_detected:
            try:
                return json.loads(self.answers_detected)
            except json.JSONDecodeError:
                return []
        return []
