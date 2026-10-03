import uuid
from datetime import timedelta
from unittest.mock import Mock
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from rest_framework.authtoken.models import Token
from rest_framework.test import APIClient
from dashboard.models import Announcement, AnnouncementRead, PushDelivery, PushDevice
from dashboard.announcements import digest, dispatch_pending, publish_announcement


class NotificationTests(TestCase):
    def setUp(self):
        self.admin = get_user_model().objects.create_superuser('notice_admin', 'admin@example.test', 'strong_password_123')
        self.user = get_user_model().objects.create_user('notice_teacher', password='strong_password_123')
        self.other = get_user_model().objects.create_user('notice_other', password='strong_password_123')
        self.client = APIClient(HTTP_X_FORWARDED_PROTO='https')
        self.token = Token.objects.create(user=self.user)
        self.installation = uuid.uuid4()

    def login(self, user):
        token, _ = Token.objects.get_or_create(user=user)
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {token.key}')

    def notice(self, **kwargs):
        return Announcement.objects.create(title='Nhắc nhở cập nhật', body='Chọn đề này. Đăng nhập và kiểm tra thông báo.', author=self.admin, **kwargs)

    def device(self):
        self.login(self.user)
        result = self.client.post('/api/v1/notifications/device/', {
            'installation_id': str(self.installation), 'token': 'fake_test_token_12345678901234567890'}, format='json')
        self.assertEqual(result.status_code, 200)
        return PushDevice.objects.get(installation_id=self.installation)

    def test_permissions(self):
        self.assertEqual(self.client.get('/api/v1/notifications/').status_code, 401)
        self.login(self.user)
        self.assertEqual(self.client.post('/api/v1/admin/notifications/', {'title':'X'}, format='json').status_code, 403)
        self.assertEqual(self.client.get('/api/v1/admin/notifications/').status_code, 403)

    def test_draft_validation_and_unicode(self):
        self.login(self.admin)
        bad = self.client.post('/api/v1/admin/notifications/', {'title':'   ', 'body':'X'}, format='json')
        self.assertEqual(bad.status_code, 400)
        good = self.client.post('/api/v1/admin/notifications/', {'title':'Chọn đề này', 'body':'Đăng nhập bằng tài khoản', 'push_enabled':False}, format='json')
        self.assertEqual(good.status_code, 201)
        self.assertEqual(good.data['title'], 'Chọn đề này')
        self.login(self.user)
        self.assertEqual(self.client.get('/api/v1/notifications/').data['items'], [])

    def test_publish_idempotent_and_read_isolation(self):
        self.device()
        notice = self.notice()
        self.login(self.admin)
        path = f'/api/v1/admin/notifications/{notice.pk}/publish/'
        self.assertEqual(self.client.post(path).status_code, 200)
        self.assertEqual(self.client.post(path).status_code, 200)
        self.assertEqual(PushDelivery.objects.count(), 1)
        self.login(self.user)
        self.assertEqual(self.client.get('/api/v1/notifications/').data['unread_count'], 1)
        read_path = f'/api/v1/notifications/{notice.pk}/read/'
        self.assertEqual(self.client.post(read_path).status_code, 200)
        self.client.post(read_path)
        self.assertEqual(AnnouncementRead.objects.count(), 1)
        self.assertEqual(self.client.get('/api/v1/notifications/').data['unread_count'], 0)
        self.login(self.other)
        self.assertEqual(self.client.get('/api/v1/notifications/').data['unread_count'], 1)

    def test_expired_hidden_and_cannot_publish(self):
        notice = self.notice(expires_at=timezone.now()-timedelta(seconds=1))
        with self.assertRaises(ValueError): publish_announcement(notice.pk)
        notice.status = 'published'
        notice.save()
        self.login(self.user)
        self.assertEqual(self.client.get('/api/v1/notifications/').data['items'], [])
        self.assertEqual(self.client.post(f'/api/v1/notifications/{notice.pk}/read/').status_code, 404)

    def test_archive_skips_pending_and_published_immutable(self):
        self.device()
        notice = publish_announcement(self.notice().pk)
        self.login(self.admin)
        path = f'/api/v1/admin/notifications/{notice.pk}/'
        self.assertEqual(self.client.patch(path, {'body':'changed'}, format='json').status_code, 409)
        self.assertEqual(self.client.delete(path).status_code, 200)
        sender = Mock(return_value='firebase/test')
        self.assertEqual(dispatch_pending(sender=sender), 0)
        sender.assert_not_called()

    def test_worker_acceptance_and_no_duplicate(self):
        self.device()
        publish_announcement(self.notice().pk)
        sender = Mock(return_value='projects/test/messages/123')
        self.assertEqual(dispatch_pending(sender=sender), 1)
        self.assertEqual(dispatch_pending(sender=sender), 0)
        sender.assert_called_once()
        self.assertEqual(PushDelivery.objects.get().state, 'sent')

    def test_logout_invalidated_session_skips_push(self):
        self.device()
        publish_announcement(self.notice().pk)
        self.token.delete()
        sender = Mock(return_value='no')
        self.assertEqual(dispatch_pending(sender=sender), 0)
        sender.assert_not_called()

    def test_account_handoff_does_not_deliver_old_queue(self):
        device = self.device()
        publish_announcement(self.notice().pk)
        self.login(self.other)
        response = self.client.post('/api/v1/notifications/device/', {
            'installation_id':str(self.installation), 'token':device.token}, format='json')
        self.assertEqual(response.status_code, 200)
        sender = Mock(return_value='no')
        self.assertEqual(dispatch_pending(sender=sender), 0)
        sender.assert_not_called()
        device.refresh_from_db()
        self.assertEqual(device.user, self.other)

    def test_retry_and_no_secret_error(self):
        self.device()
        publish_announcement(self.notice().pk)
        sender = Mock(side_effect=RuntimeError('secret-token-should-not-be-stored'))
        self.assertEqual(dispatch_pending(sender=sender), 0)
        row = PushDelivery.objects.get()
        self.assertEqual(row.state, 'pending')
        self.assertEqual(row.error_code, 'RuntimeError')
        self.assertGreater(row.next_attempt_at, timezone.now())
        self.assertEqual(dispatch_pending(sender=sender), 0)
        sender.assert_called_once()

    def test_foreign_user_cannot_disable_device(self):
        device = self.device()
        self.login(self.other)
        self.client.delete('/api/v1/notifications/device/', {'installation_id':str(self.installation)}, format='json')
        device.refresh_from_db()
        self.assertTrue(device.active)

    def test_bad_device_data(self):
        self.login(self.user)
        self.assertEqual(self.client.post('/api/v1/notifications/device/', {'installation_id':'bad'}, format='json').status_code, 400)

    def test_in_app_only_creates_no_push(self):
        self.device()
        publish_announcement(self.notice(push_enabled=False).pk)
        self.assertEqual(PushDelivery.objects.count(), 0)

    def test_mark_all_read_is_per_account_and_ignores_drafts(self):
        self.notice()  # Not published; cannot be marked read by the user.
        publish_announcement(self.notice(push_enabled=False).pk)
        self.login(self.user)
        self.assertEqual(self.client.post('/api/v1/notifications/').status_code, 200)
        self.assertEqual(AnnouncementRead.objects.filter(user=self.user).count(), 1)
        self.assertEqual(self.client.get('/api/v1/notifications/').data['unread_count'], 0)
        self.login(self.other)
        self.assertEqual(self.client.get('/api/v1/notifications/').data['unread_count'], 1)
