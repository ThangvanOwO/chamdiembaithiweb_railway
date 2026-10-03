"""Announcements and a persistent FCM outbox, independent of the grading pipeline."""
import hashlib
import json
import os
from datetime import timedelta
from pathlib import Path

from django.db import transaction
from django.db.models import Q
from django.utils import timezone
from rest_framework.authtoken.models import Token

from .models import Announcement, PushDevice, PushDelivery


def digest(value):
    return hashlib.sha256(value.encode()).hexdigest()


def visible_announcements():
    return Announcement.objects.filter(status='published').filter(
        Q(expires_at__isnull=True) | Q(expires_at__gt=timezone.now())).filter(
        ~Q(kind='event') | Q(event_ends_at__gt=timezone.now()))


def firebase_status():
    path = os.environ.get('GOOGLE_APPLICATION_CREDENTIALS', '')
    try:
        data = json.loads(Path(path).read_text()) if path else {}
        expected = os.environ.get('FIREBASE_PROJECT_ID', 'gradeflow-19d58')
        return bool(data.get('type') == 'service_account' and data.get('private_key')
                    and data.get('project_id') == expected)
    except (OSError, ValueError):
        return False


@transaction.atomic
def publish_announcement(pk):
    notice = Announcement.objects.select_for_update().get(pk=pk)
    if notice.status == 'published':
        return notice
    if notice.status != 'draft':
        raise ValueError('Thông báo đã thu hồi. Hãy tạo bản nháp mới.')
    if notice.expires_at and notice.expires_at <= timezone.now():
        raise ValueError('Ngày hết hạn phải ở trong tương lai.')
    if notice.kind == 'event':
        if not notice.event_starts_at or not notice.event_ends_at or notice.event_ends_at <= notice.event_starts_at:
            raise ValueError('Sự kiện cần có ngày giờ bắt đầu và kết thúc hợp lệ.')
        if notice.event_ends_at <= timezone.now():
            raise ValueError('Sự kiện đã kết thúc. Hãy cập nhật ngày giờ trước khi gửi.')
    notice.status = 'published'
    notice.published_at = timezone.now()
    notice.save(update_fields=['status', 'published_at'])
    if notice.push_enabled:
        PushDelivery.objects.bulk_create([
            PushDelivery(announcement=notice, device=device,
                         destination_hash=digest(device.token), session_hash=device.session_hash)
            for device in PushDevice.objects.filter(active=True, user__is_active=True).iterator()
        ], ignore_conflicts=True)
    return notice


def send_fcm(notice, device):
    # Import lazily: no Firebase startup/network request during grading or Django startup.
    import firebase_admin
    from firebase_admin import credentials, messaging
    try:
        app = firebase_admin.get_app('gradeflow_notifications')
    except ValueError:
        app = firebase_admin.initialize_app(
            credentials.Certificate(os.environ['GOOGLE_APPLICATION_CREDENTIALS']),
            {'projectId': os.environ.get('FIREBASE_PROJECT_ID', 'gradeflow-19d58'),
             'httpTimeout': 20}, name='gradeflow_notifications')
    ttl = min(timedelta(days=7), notice.expires_at - timezone.now()) if notice.expires_at else timedelta(days=7)
    if notice.kind == 'event' and notice.event_ends_at:
        ttl = min(ttl, notice.event_ends_at - timezone.now())
    return messaging.send(messaging.Message(
        token=device.token,
        notification=messaging.Notification(title=notice.title, body=notice.body[:500]),
        data={'announcement_id': str(notice.pk), 'kind': notice.kind},
        android=messaging.AndroidConfig(priority='high', ttl=max(ttl, timedelta(seconds=1)),
            collapse_key=f'notice_{notice.pk}',
            notification=messaging.AndroidNotification(
                channel_id='gradeflow_announcements', tag=f'notice_{notice.pk}'))), app=app)


def dispatch_pending(limit=50, sender=None):
    """Claim individual deliveries atomically; retry transient failures with bounded backoff."""
    if sender is None and not firebase_status():
        return 0
    sender = sender or send_fcm
    now = timezone.now()
    PushDelivery.objects.filter(state='sending', claimed_at__lt=now-timedelta(minutes=10)).update(state='pending')
    pending = list(PushDelivery.objects.filter(state='pending', next_attempt_at__lte=now)
                   .order_by('id').values_list('id', flat=True)[:limit])
    sent = 0
    for pk in pending:
        if not PushDelivery.objects.filter(pk=pk, state='pending').update(state='sending', claimed_at=now):
            continue
        row = PushDelivery.objects.select_related('announcement', 'device__user').get(pk=pk)
        notice, device = row.announcement, row.device
        token = Token.objects.filter(user_id=device.user_id).values_list('key', flat=True).first()
        valid = (notice.status == 'published' and (not notice.expires_at or notice.expires_at > timezone.now())
                 and (notice.kind != 'event' or (notice.event_ends_at and notice.event_ends_at > timezone.now()))
                 and device.active and device.user.is_active and token and digest(token) == row.session_hash
                 and device.session_hash == row.session_hash and digest(device.token) == row.destination_hash)
        if not valid:
            row.state = 'skipped'
            row.error_code = 'inactive_or_changed_destination'
        else:
            row.attempts += 1
            try:
                row.provider_id = sender(notice, device)[:250]
                row.state = 'sent'
                row.error_code = ''
                sent += 1
            except Exception as exc:
                # Store only the exception class, never tokens or credential material.
                row.error_code = type(exc).__name__[:80]
                if row.error_code in ('UnregisteredError', 'SenderIdMismatchError'):
                    PushDevice.objects.filter(pk=device.pk, token=device.token).update(active=False)
                    row.state = 'failed'
                elif row.attempts >= 5:
                    row.state = 'failed'
                else:
                    row.state = 'pending'
                    row.next_attempt_at = timezone.now() + timedelta(seconds=30 * 2 ** row.attempts)
        row.save(update_fields=['state', 'attempts', 'provider_id', 'error_code', 'next_attempt_at'])
    return sent
