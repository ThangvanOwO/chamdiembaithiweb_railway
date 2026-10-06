from django.conf import settings
from django.db import models


class Classroom(models.Model):
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    name = models.CharField('Tên lớp', max_length=100)
    school_year = models.CharField('Năm học', max_length=30, blank=True)
    archived = models.BooleanField('Đã lưu trữ', default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['name', 'id']
        verbose_name = 'Lớp học'
        verbose_name_plural = 'Lớp học'

    def __str__(self):
        return f'{self.name} · {self.school_year}'


class Student(models.Model):
    classroom = models.ForeignKey(Classroom, on_delete=models.CASCADE, related_name='students')
    name = models.CharField('Họ tên', max_length=200)
    student_id = models.CharField('Số báo danh', max_length=50)
    archived = models.BooleanField('Đã lưu trữ', default=False)

    class Meta:
        ordering = ['student_id', 'id']
        constraints = [models.UniqueConstraint(fields=['classroom', 'student_id'], name='toolbox_class_sbd')]
        verbose_name = 'Học sinh'
        verbose_name_plural = 'Học sinh'

    def __str__(self):
        return f'{self.student_id} · {self.name}'


class ExamRosterEntry(models.Model):
    """Immutable identity snapshot; live class edits never rewrite exam records."""
    exam = models.ForeignKey('grading.Exam', on_delete=models.CASCADE, related_name='roster_entries')
    source_student = models.ForeignKey(Student, null=True, on_delete=models.SET_NULL)
    classroom = models.ForeignKey(Classroom, null=True, on_delete=models.SET_NULL)
    student_id = models.CharField(max_length=50)
    student_name = models.CharField(max_length=200)
    class_name = models.CharField(max_length=100)
    active = models.BooleanField(default=True)

    class Meta:
        ordering = ['class_name', 'student_id', 'id']
        constraints = [models.UniqueConstraint(fields=['exam', 'student_id'], name='toolbox_exam_sbd')]


class SubmissionReview(models.Model):
    submission = models.OneToOneField('grading.Submission', on_delete=models.CASCADE, related_name='toolbox_review')
    roster_entry = models.ForeignKey(ExamRosterEntry, null=True, blank=True, on_delete=models.SET_NULL)
    reviewed_at = models.DateTimeField(null=True, blank=True)
    representative = models.BooleanField(default=False)


class SupportTicket(models.Model):
    STATUS_CHOICES = [('new', 'Mới'), ('working', 'Đang xử lý'), ('resolved', 'Đã xử lý')]
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    message = models.TextField('Nội dung')
    technical = models.JSONField('Thông tin kỹ thuật', default=dict)
    image = models.ImageField('Ảnh đính kèm', upload_to='support/%Y/%m/', blank=True)
    status = models.CharField('Trạng thái', max_length=12, choices=STATUS_CHOICES, default='new')
    admin_note = models.TextField('Phản hồi', blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at', '-id']
        verbose_name = 'Báo lỗi'
        verbose_name_plural = 'Báo lỗi'
