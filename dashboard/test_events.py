from datetime import timedelta
from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.utils import timezone
from rest_framework.test import APIClient
from .models import Announcement
from .announcements import publish_announcement, visible_announcements


@override_settings(SECURE_SSL_REDIRECT=False)
class BulletinEventsTests(TestCase):
    def setUp(self):
        self.admin = get_user_model().objects.create_superuser(username='events_admin', email='events@example.test', password='testing-only')
        self.user = get_user_model().objects.create_user(username='events_user', password='testing-only')
        self.client = APIClient()
        self.client.force_authenticate(self.admin)
        self.start = timezone.now() + timedelta(days=1)
        self.end = self.start + timedelta(hours=1)
        self.payload = dict(title='Hướng dẫn quét phiếu', body='Nội dung sự kiện', kind='event', push_enabled=False,
                            event_starts_at=self.start.isoformat(), event_ends_at=self.end.isoformat())

    def test_create_publish_read_and_archive_event(self):
        response = self.client.post('/api/v1/admin/notifications/', self.payload, format='json')
        self.assertEqual(response.status_code, 201, response.data)
        pk = response.data['id']
        self.assertFalse(visible_announcements().filter(pk=pk).exists())
        response = self.client.post(f'/api/v1/admin/notifications/{pk}/publish/')
        self.assertEqual(response.status_code, 200)
        self.client.force_authenticate(self.user)
        data = self.client.get('/api/v1/notifications/').data
        self.assertEqual(data['unread_count'], 1)
        self.assertEqual(data['items'][0]['event_starts_at'], self.start)
        self.assertEqual(self.client.post(f'/api/v1/notifications/{pk}/read/').status_code, 200)
        self.assertEqual(self.client.get('/api/v1/notifications/').data['unread_count'], 0)
        self.client.force_authenticate(self.admin)
        self.client.delete(f'/api/v1/admin/notifications/{pk}/')
        self.assertFalse(visible_announcements().filter(pk=pk).exists())

    def test_invalid_missing_or_reversed_dates_rejected(self):
        for changes in [dict(event_starts_at=None), dict(event_ends_at=None), dict(event_ends_at=self.start.isoformat()), dict(expires_at=(self.start-timedelta(hours=1)).isoformat())]:
            with self.subTest(changes=changes):
                response = self.client.post('/api/v1/admin/notifications/', self.payload | changes, format='json')
                self.assertEqual(response.status_code, 400)
        self.assertEqual(Announcement.objects.count(), 0)

    def test_ended_events_hidden_and_cannot_publish(self):
        notice = Announcement.objects.create(title='Old', body='Old', kind='event', event_starts_at=timezone.now()-timedelta(hours=2), event_ends_at=timezone.now()-timedelta(hours=1), push_enabled=False)
        with self.assertRaises(ValueError):
            publish_announcement(notice.pk)
        notice.status = 'published'
        notice.save()
        self.assertFalse(visible_announcements().exists())

    def test_non_admin_cannot_create_event(self):
        self.client.force_authenticate(self.user)
        self.assertEqual(self.client.post('/api/v1/admin/notifications/', self.payload, format='json').status_code, 403)

    def test_legacy_notice_and_partial_event_edit(self):
        notice = Announcement.objects.create(**{**self.payload, 'event_starts_at': self.start, 'event_ends_at': self.end})
        response = self.client.patch(f'/api/v1/admin/notifications/{notice.pk}/', {'title': 'Đổi tiêu đề'}, format='json')
        self.assertEqual(response.status_code, 200)
        notice.refresh_from_db()
        self.assertEqual(notice.event_starts_at, self.start)
        response = self.client.patch(f'/api/v1/admin/notifications/{notice.pk}/', {'kind': 'info'}, format='json')
        self.assertEqual(response.status_code, 200)
        notice.refresh_from_db()
        self.assertIsNone(notice.event_starts_at)
        self.assertIsNone(notice.event_ends_at)
        response = self.client.post('/api/v1/admin/notifications/', {'title': 'Tin cũ', 'body': 'Hỗ trợ app cũ', 'kind': 'info', 'push_enabled': False}, format='json')
        self.assertEqual(response.status_code, 201)
