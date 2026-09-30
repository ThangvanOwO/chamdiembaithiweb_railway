import re
import uuid
from unittest.mock import patch

from django.contrib.auth.models import User, Permission
from django.core import mail
from django.test import TestCase, override_settings
from django.urls import reverse
from django.templatetags.static import static

from .models import CreditWallet, CreditEntry


class AccountFeatureTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user('teacher', 'teacher@example.com', 'TeacherPassword249!')

    @override_settings(EMAIL_HOST='smtp.example.com', EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend')
    @patch('accounts.registration.verify_challenge')
    def test_registration_grants_100_and_success_message(self, challenge):
        response = self.client.post(reverse('accounts:register'), {
            'full_name': 'Nguyễn An', 'email': 'new@example.com',
            'password': 'UniquePassword249!', 'password_confirm': 'UniquePassword249!',
        }, follow=True)
        # Registration now requires email ownership and password confirmation first.
        from accounts.models import PendingSignup
        self.assertFalse(User.objects.filter(email='new@example.com').exists())
        pending = PendingSignup.objects.get(email='new@example.com')
        response = self.client.post(reverse('accounts:verify_signup', args=[pending.token]),
                                    {'password': 'UniquePassword249!'}, follow=True)
        self.assertContains(response, 'Đăng ký thành công')
        user = User.objects.get(email='new@example.com')
        self.assertEqual(user.credit_wallet.balance, 100)
        self.assertTrue(user.check_password('UniquePassword249!'))
        self.assertNotContains(response, 'UniquePassword249!')

    def test_login_success_and_failure_messages(self):
        response = self.client.post(reverse('accounts:login'), {'email': self.user.email, 'password': 'wrong'})
        self.assertNotContains(response, 'Đăng nhập thành công')
        self.assertNotIn('_auth_user_id', self.client.session)
        response = self.client.post(reverse('accounts:login'), {'email': self.user.email, 'password': 'TeacherPassword249!'}, follow=True)
        self.assertContains(response, 'Đăng nhập thành công')
        self.assertEqual(CreditEntry.objects.filter(wallet__user=self.user).count(), 1)

    def test_disabled_user_cannot_login_through_fallback(self):
        self.user.is_active = False
        self.user.save()
        self.client.post(reverse('accounts:login'), {'email': self.user.email, 'password': 'TeacherPassword249!'})
        self.assertNotIn('_auth_user_id', self.client.session)

    def test_login_next_cannot_redirect_off_site(self):
        response = self.client.post(reverse('accounts:login') + '?next=https://untrusted.example/',
                                    {'email': self.user.email, 'password': 'TeacherPassword249!'})
        self.assertRedirects(response, '/dashboard/', fetch_redirect_response=False)

    def test_password_toggle_loaded_and_no_saved_password_returned(self):
        for name in ('login', 'register'):
            response = self.client.get(reverse('accounts:' + name))
            self.assertContains(response, static('js/password-toggle.js'))
            self.assertContains(response, 'type="password"')
            self.assertNotContains(response, 'TeacherPassword249!')

    def test_credits_page_is_private_and_shows_only_own_history(self):
        self.assertEqual(self.client.get(reverse('accounts:credits')).status_code, 302)
        self.client.force_login(self.user)
        response = self.client.get(reverse('accounts:credits'))
        self.assertContains(response, '100')
        self.assertContains(response, 'chưa mở')
        self.assertContains(response, '100 điểm chào mừng')

    @override_settings(EMAIL_HOST='')
    def test_reset_without_mail_configuration_is_honest(self):
        response = self.client.post(reverse('accounts:password_reset'), {'email': self.user.email})
        self.assertContains(response, 'Email khôi phục chưa được cấu hình')

    @override_settings(EMAIL_HOST='smtp.example.com', EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend')
    def test_password_reset_link_works_once_and_does_not_leak_old_password(self):
        response = self.client.post(reverse('accounts:password_reset'), {'email': self.user.email})
        self.assertRedirects(response, reverse('accounts:password_reset_done'))
        self.assertEqual(len(mail.outbox), 1)
        self.assertNotIn('TeacherPassword249!', mail.outbox[0].body)
        path = re.search(r'https?://[^/]+([^\s]+)', mail.outbox[0].body).group(1)
        response = self.client.get(path)
        confirm = response['Location']
        response = self.client.post(confirm, {'new_password1': 'ChangedPassword249!', 'new_password2': 'ChangedPassword249!'})
        self.assertRedirects(response, reverse('accounts:password_reset_complete'))
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password('ChangedPassword249!'))
        self.assertFalse(self.user.check_password('TeacherPassword249!'))
        self.assertFalse(self.client.get(path).context['validlink'])


class CreditAdminTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user('teacher')
        self.url = reverse('admin:accounts_creditwallet_change', args=[self.user.credit_wallet.pk])

    def test_regular_user_and_staff_without_permission_cannot_adjust(self):
        self.client.force_login(self.user)
        self.assertEqual(self.client.get(self.url).status_code, 302)
        self.user.is_staff = True
        self.user.save()
        self.assertEqual(self.client.post(self.url, {'adjustment': 50}).status_code, 403)
        self.assertEqual(CreditWallet.objects.get(user=self.user).balance, 100)

    def test_admin_adjustment_logged_and_replay_safe(self):
        admin = User.objects.create_superuser('admin', 'admin@example.com', 'AdminPassword249!')
        self.client.force_login(admin)
        data = {'adjustment': 20, 'reason': 'Hỗ trợ giáo viên', 'reference': str(uuid.uuid4()), '_save': 'Save'}
        response = self.client.post(self.url, data)
        self.assertEqual(response.status_code, 302)
        self.client.post(self.url, data)
        self.assertEqual(CreditWallet.objects.get(user=self.user).balance, 120)
        entry = CreditEntry.objects.get(reference='admin:' + data['reference'])
        self.assertEqual(entry.actor, admin)
        self.assertEqual(entry.reason, data['reason'])
        # The audit ledger cannot be edited through admin.
        url = reverse('admin:accounts_creditentry_change', args=[entry.pk])
        self.assertEqual(self.client.post(url, {'amount': 999}).status_code, 403)
