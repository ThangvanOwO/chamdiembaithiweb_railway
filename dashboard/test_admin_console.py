import uuid

from django.contrib.auth.models import Permission, User
from django.test import TestCase, override_settings
from django.urls import reverse

from .models import PushDevice


@override_settings(SECURE_SSL_REDIRECT=False)
class AdminConsoleTests(TestCase):
    def setUp(self):
        self.owner = User.objects.create_superuser('console_owner', 'owner@example.com', 'test-only-password')
        self.teacher = User.objects.create_user('teacher_console', 'teacher@example.com')
        self.staff = User.objects.create_user('console_staff', is_staff=True)
        self.device = PushDevice.objects.create(
            user=self.teacher, installation_id=uuid.uuid4(),
            token='SECRET_FCM_TOKEN_MUST_NOT_APPEAR', session_hash='SECRET_SESSION_DIGEST')
        self.list_url = reverse('admin:dashboard_pushdevice_changelist')
        self.detail_url = reverse('admin:dashboard_pushdevice_change', args=[self.device.pk])

    def test_owner_overview_has_workflows_and_accurate_registration_counts(self):
        inactive_user = User.objects.create_user('inactive_console', is_active=False)
        PushDevice.objects.create(user=inactive_user, installation_id=uuid.uuid4(), token='inactive-token', session_hash='digest')
        PushDevice.objects.create(user=self.teacher, installation_id=uuid.uuid4(), token='disabled-token', session_hash='digest', active=False)
        self.client.force_login(self.owner)
        response = self.client.get(reverse('admin:index'))
        self.assertContains(response, 'Tổng quan hệ thống')
        self.assertContains(response, 'Thông báo & sự kiện')
        self.assertContains(response, 'Thiết bị nhận thông báo')
        self.assertContains(response, 'Gắn với 1 tài khoản đang mở')
        self.assertNotContains(response, 'SECRET_FCM_TOKEN')

    def test_staff_catalog_keeps_permission_boundaries(self):
        self.staff.user_permissions.add(Permission.objects.get(codename='view_creditwallet'))
        self.client.force_login(self.staff)
        response = self.client.get(reverse('admin:index'))
        self.assertContains(response, 'Ví tín dụng')
        self.assertNotContains(response, 'Thiết bị nhận thông báo')
        self.assertNotContains(response, 'Mẫu huấn luyện chờ duyệt')
        self.assertNotContains(response, 'gf-metric"')

    def test_device_pages_do_not_expose_tokens_or_session_hashes(self):
        self.client.force_login(self.owner)
        for url in (self.list_url, self.detail_url):
            with self.subTest(url=url):
                response = self.client.get(url)
                self.assertEqual(response.status_code, 200)
                self.assertContains(response, str(self.device.installation_id))
                self.assertNotContains(response, self.device.token)
                self.assertNotContains(response, self.device.session_hash)
        self.assertContains(self.client.get(self.list_url), 'không phải thời gian sử dụng gần nhất')

    def test_even_staff_with_device_permissions_cannot_read_registry(self):
        self.staff.user_permissions.add(*Permission.objects.filter(content_type__app_label='dashboard', content_type__model='pushdevice'))
        self.client.force_login(self.staff)
        self.assertEqual(self.client.get(self.list_url).status_code, 403)
        self.assertEqual(self.client.get(self.detail_url).status_code, 403)

    def test_device_registry_cannot_be_edited_or_deleted(self):
        self.client.force_login(self.owner)
        for url in (self.detail_url, reverse('admin:dashboard_pushdevice_delete', args=[self.device.pk]), reverse('admin:dashboard_pushdevice_add')):
            with self.subTest(url=url):
                self.assertEqual(self.client.post(url, {'active': False, 'token': 'modified'}).status_code, 403)
        self.device.refresh_from_db()
        self.assertTrue(self.device.active)
        self.assertEqual(self.device.token, 'SECRET_FCM_TOKEN_MUST_NOT_APPEAR')

    def test_registry_search_and_active_filter(self):
        other = User.objects.create_user('other_console', 'other@example.com')
        hidden = PushDevice.objects.create(user=other, installation_id=uuid.uuid4(), token='other-token', session_hash='digest', active=False)
        self.client.force_login(self.owner)
        response = self.client.get(self.list_url, {'q': 'teacher@example.com'})
        self.assertContains(response, str(self.device.installation_id))
        self.assertNotContains(response, str(hidden.installation_id))
        response = self.client.get(self.list_url, {'active__exact': '0'})
        self.assertContains(response, str(hidden.installation_id))
        self.assertNotContains(response, str(self.device.installation_id))

    def test_non_staff_and_anonymous_are_redirected_to_login(self):
        self.assertEqual(self.client.get(self.list_url).status_code, 302)
        self.client.force_login(self.teacher)
        self.assertEqual(self.client.get(self.list_url).status_code, 302)

    def test_existing_admin_forms_and_security_dashboard_still_render(self):
        self.client.force_login(self.owner)
        for url in (reverse('admin:dashboard_announcement_add'), reverse('admin:auth_user_changelist'), reverse('risk_dashboard')):
            with self.subTest(url=url):
                self.assertEqual(self.client.get(url).status_code, 200)
