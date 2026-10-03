from django.db import models
from django.conf import settings
from django.utils import timezone
from django.core.exceptions import ValidationError


class Announcement(models.Model):
    title = models.CharField('Tiêu đề', max_length=120)
    body = models.TextField('Nội dung', max_length=4000)
    kind = models.CharField('Loại', max_length=12, default='info', choices=[
        ('info', 'Thông tin'), ('reminder', 'Nhắc nhở'), ('update', 'Cập nhật'), ('event', 'Sự kiện')])
    event_starts_at = models.DateTimeField('Bắt đầu sự kiện', null=True, blank=True)
    event_ends_at = models.DateTimeField('Kết thúc sự kiện', null=True, blank=True)
    status = models.CharField('Trạng thái', max_length=12, default='draft', choices=[
        ('draft', 'Bản nháp'), ('published', 'Đã gửi'), ('archived', 'Đã thu hồi')])
    push_enabled = models.BooleanField('Gửi lên điện thoại', default=True)
    expires_at = models.DateTimeField('Hết hạn', null=True, blank=True)
    published_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    author = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True)

    class Meta:
        ordering = ['-published_at', '-id']
        verbose_name = 'Thông báo'
        verbose_name_plural = 'Quản lý thông báo'

    def __str__(self):
        return self.title

    def clean(self):
        super().clean()
        if self.kind != 'event':
            self.event_starts_at = self.event_ends_at = None
            return
        errors = {}
        if not self.event_starts_at:
            errors['event_starts_at'] = 'Chọn ngày giờ bắt đầu sự kiện.'
        if not self.event_ends_at:
            errors['event_ends_at'] = 'Chọn ngày giờ kết thúc sự kiện.'
        if self.event_starts_at and self.event_ends_at and self.event_ends_at <= self.event_starts_at:
            errors['event_ends_at'] = 'Giờ kết thúc phải sau giờ bắt đầu.'
        if self.expires_at and self.event_starts_at and self.expires_at <= self.event_starts_at:
            errors['expires_at'] = 'Ngày hết hạn phải sau giờ bắt đầu sự kiện.'
        if errors:
            raise ValidationError(errors)


class AnnouncementRead(models.Model):
    announcement = models.ForeignKey(Announcement, on_delete=models.CASCADE)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    read_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=['announcement', 'user'], name='unique_announcement_read')]


class PushDevice(models.Model):
    installation_id = models.UUIDField(unique=True)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    token = models.CharField(max_length=4096, unique=True)
    session_hash = models.CharField(max_length=64)
    active = models.BooleanField(default=True)
    updated_at = models.DateTimeField(auto_now=True)


class PushDelivery(models.Model):
    announcement = models.ForeignKey(Announcement, on_delete=models.CASCADE)
    device = models.ForeignKey(PushDevice, on_delete=models.CASCADE)
    # Freeze the destination/session; do not deliver an old user's queue after device handoff.
    destination_hash = models.CharField(max_length=64)
    session_hash = models.CharField(max_length=64)
    state = models.CharField(max_length=12, default='pending')
    attempts = models.PositiveSmallIntegerField(default=0)
    next_attempt_at = models.DateTimeField(default=timezone.now)
    claimed_at = models.DateTimeField(null=True)
    provider_id = models.CharField(max_length=250, blank=True)
    error_code = models.CharField(max_length=80, blank=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=['announcement', 'device'], name='unique_announcement_push')]
        indexes = [models.Index(fields=['state', 'next_attempt_at'])]
