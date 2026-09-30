from django.db import models
from django.contrib.auth.models import User
import json


class UserSettings(models.Model):
    """Per-user preferences (auto-delete, notifications, ...)."""
    RETENTION_CHOICES = [
        (0,   'Không tự xóa'),
        (7,   'Sau 7 ngày'),
        (30,  'Sau 30 ngày'),
        (90,  'Sau 90 ngày'),
        (180, 'Sau 6 tháng'),
    ]

    user = models.OneToOneField(
        User, on_delete=models.CASCADE, related_name='settings'
    )
    temp_retention_days = models.PositiveIntegerField(
        'Tự động xóa ảnh cũ (ngày)',
        default=30,
        choices=RETENTION_CHOICES,
        help_text='Tự động xóa ảnh phiếu đã chấm sau N ngày. 0 = không xóa.',
    )
    contribute_training_data = models.BooleanField(
        'Góp ảnh để cải thiện AI',
        default=False,
        help_text='Cho phép ứng dụng gửi ảnh phiếu đã chấm (sạch, 100% nhận diện) '
                  'lên server để cải thiện mô hình nhận dạng.',
    )
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Cài đặt người dùng'
        verbose_name_plural = 'Cài đặt người dùng'

    def __str__(self):
        return f"Settings({self.user.username})"


class Exam(models.Model):
    """A test/exam with answer key."""
    
    teacher = models.ForeignKey(User, on_delete=models.CASCADE, related_name='exams')
    title = models.CharField('Tên bài thi', max_length=200)
    subject = models.CharField('Môn', max_length=100, blank=True, default='')
    num_questions = models.PositiveIntegerField('Số câu hỏi', default=40)
    template_code = models.CharField(
        'Mã đề phiếu', max_length=30, blank=True, default='',
        help_text='Mã template phiếu thi vật lý (VD: 28-02-00)'
    )
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
    def parts_config(self):
        """Returns [p1_count, p2_count, p3_count] from config JSON, or [num_questions, 0, 0]."""
        if self.answer_key:
            try:
                data = json.loads(self.answer_key)
                if isinstance(data, dict) and 'parts' in data:
                    return data['parts']
            except (json.JSONDecodeError, ValueError):
                pass
        return [self.num_questions, 0, 0]
    
    @property
    def scoring_config(self):
        """Returns scoring config dict from answer_key JSON, or None."""
        if self.answer_key:
            try:
                data = json.loads(self.answer_key)
                if isinstance(data, dict) and 'scoring' in data:
                    return data['scoring']
            except (json.JSONDecodeError, ValueError):
                pass
        return None

    @property
    def variant_codes(self):
        """Returns list of variant codes for this exam."""
        return list(self.variants.values_list('variant_code', flat=True))

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


class ExamVariant(models.Model):
    """A specific exam code (mã đề) with its own answer key, belonging to an Exam."""

    exam = models.ForeignKey(Exam, on_delete=models.CASCADE, related_name='variants')
    variant_code = models.CharField('Mã đề', max_length=20)
    answers_json = models.TextField(
        'Đáp án (JSON)',
        blank=True, default='',
        help_text='JSON: {"p1": {"1":"A","2":"B",...}, "p2": {...}, "p3": {...}}'
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Mã đề'
        verbose_name_plural = 'Mã đề'
        unique_together = ('exam', 'variant_code')
        ordering = ['variant_code']

    def __str__(self):
        return f"Mã {self.variant_code} — {self.exam.title}"

    @property
    def answers(self):
        """Parse answers_json to dict."""
        if self.answers_json:
            try:
                return json.loads(self.answers_json)
            except (json.JSONDecodeError, ValueError):
                pass
        return {}

    @property
    def answer_key_str(self):
        """Build answer key JSON string for grading engine (all parts: P1, P2, P3)."""
        data = self.answers
        if not data:
            return ''
        # Return full JSON — parse_answer_key() supports p1/p2/p3 keys
        # and converts Đ/S → Dung/Sai automatically
        return json.dumps(data, ensure_ascii=False)


class Submission(models.Model):
    """A student's exam submission (uploaded image + grading result)."""
    
    STATUS_CHOICES = [
        ('pending', 'Chờ xử lý'),
        ('processing', 'Đang chấm'),
        ('completed', 'Đã chấm'),
        ('error', 'Lỗi'),
    ]
    
    exam = models.ForeignKey(Exam, on_delete=models.CASCADE, related_name='submissions', null=True, blank=True)
    variant = models.ForeignKey(ExamVariant, on_delete=models.SET_NULL, related_name='submissions', null=True, blank=True)
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
        """Điểm hiển thị. Nếu score đã là weighted (≤ tổng điểm tối đa) thì dùng trực tiếp."""
        if self.score is not None:
            return round(self.score, 2)
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
    def name_image_url(self):
        """URL to the cropped student name image (if available)."""
        if self.image:
            import os
            from django.conf import settings
            base = os.path.splitext(self.image.name)[0]
            name_rel = f"{base}_name.jpg"
            full_path = os.path.join(settings.MEDIA_ROOT, name_rel)
            if os.path.exists(full_path):
                return settings.MEDIA_URL + name_rel.replace('\\', '/')
        return ''

    @property
    def detected_answers_list(self):
        if self.answers_detected:
            try:
                return json.loads(self.answers_detected)
            except json.JSONDecodeError:
                return []
        return []


class TrainingSample(models.Model):
    """Ảnh phiếu 'sạch' do giáo viên đóng góp tự nguyện để train CNN."""
    teacher = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name='training_samples'
    )
    submission = models.ForeignKey(
        Submission,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='training_samples',
    )
    image = models.ImageField('Ảnh phiếu', upload_to='training/%Y/%m/')
    made = models.CharField('Mã đề', max_length=10, blank=True, default='')
    sbd = models.CharField('Số báo danh', max_length=20, blank=True, default='')
    template_code = models.CharField('Mã phiếu', max_length=30, blank=True, default='')
    answers_json = models.TextField(
        'Labels (JSON)',
        blank=True, default='',
        help_text='JSON: {"part1": [...], "part2": {...}, "part3": [...]}',
    )
    confidence = models.FloatField('Độ tự tin', default=1.0)
    uploaded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Mẫu training'
        verbose_name_plural = 'Mẫu training'
        ordering = ['-uploaded_at']

    def __str__(self):
        return f"Sample#{self.id} by {self.teacher.username} ({self.made}/{self.sbd})"


class TrainingCorrection(models.Model):
    """Human-labelled question crops; automatic predictions are never ground truth."""
    teacher = models.ForeignKey(User, on_delete=models.CASCADE, related_name='training_corrections')
    image = models.ImageField(upload_to='training_corrections/%Y/%m/')
    source_hash = models.CharField(max_length=64, db_index=True)
    template_code = models.CharField(max_length=30)
    part = models.PositiveSmallIntegerField()
    question = models.PositiveSmallIntegerField()
    subquestion = models.CharField(max_length=1, blank=True)
    detected = models.CharField(max_length=40, blank=True)
    answer = models.CharField(max_length=40, blank=True)
    cells = models.JSONField(default=list)
    labels = models.JSONField(default=dict)
    geometry = models.JSONField(default=dict)
    status = models.CharField(max_length=10, default='pending', choices=[
        ('pending', 'Chờ duyệt'), ('approved', 'Đã duyệt'), ('rejected', 'Loại')])
    reviewed_by = models.ForeignKey(User, null=True, blank=True, on_delete=models.SET_NULL,
                                   related_name='reviewed_training_corrections')
    reviewed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        constraints = [models.UniqueConstraint(
            fields=['teacher', 'source_hash', 'template_code', 'part', 'question', 'subquestion'],
            name='unique_training_question_source')]
        verbose_name = 'Câu huấn luyện đã gán nhãn'
        verbose_name_plural = 'Dữ liệu huấn luyện theo câu'

    def __str__(self):
        return f'Phần {self.part} · Câu {self.question}{self.subquestion} · {self.get_status_display()}'
