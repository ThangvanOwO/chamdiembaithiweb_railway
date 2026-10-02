import json
from unittest.mock import patch

from allauth.account.models import EmailAddress
from django.contrib.auth.models import User
from django.test import Client, TestCase, override_settings
from django.urls import reverse

from .models import CreditEntry


@override_settings(ALLOW_USERNAME_SIGNUP=True, SECURE_SSL_REDIRECT=False)
class UsernameSignupTests(TestCase):
    password = 'TestClosed249!Strong'

    def payload(self, **changes):
        return dict(username='teacher_test', full_name='Nguyễn Văn An',
                    password=self.password, **changes)

    def signup(self, data=None, **changes):
        return self.client.post(reverse('api:register'),
            json.dumps(data if data is not None else self.payload(**changes)),
            content_type='application/json')

    def test_signup_hashes_password_and_returns_usable_token(self):
        response = self.signup()
        self.assertEqual(response.status_code, 201, response.content)
        user = User.objects.get(username='teacher_test')
        self.assertEqual(user.get_full_name(), 'Nguyễn Văn An')
        self.assertTrue(user.check_password(self.password))
        self.assertNotEqual(user.password, self.password)
        self.assertEqual(user.email, '')
        self.assertFalse(EmailAddress.objects.filter(user=user).exists())
        self.assertEqual(user.credit_wallet.balance, 100)
        self.assertEqual(CreditEntry.objects.filter(wallet__user=user).count(), 1)
        token = response.json()['token']
        me = self.client.get(reverse('api:me'), HTTP_AUTHORIZATION='Token ' + token)
        self.assertEqual(me.json()['full_name'], 'Nguyễn Văn An')
        self.assertEqual(me.json()['username'], 'teacher_test')
        self.assertNotIn(self.password, response.content.decode())
        self.assertFalse(me.json()['is_admin'])

    def test_new_account_cannot_grant_admin_or_claim_an_email(self):
        self.assertEqual(self.signup(email='owner@example.com', is_staff=True,
            is_superuser=True, is_admin=True).status_code, 201)
        user = User.objects.get(username='teacher_test')
        self.assertFalse(user.is_staff)
        self.assertFalse(user.is_superuser)
        self.assertEqual(user.email, '')
        self.assertFalse(EmailAddress.objects.filter(user=user).exists())

    def test_username_is_normalized_and_duplicate_cannot_change_password(self):
        data = self.payload()
        data['username'] = '  Teacher_Test  '
        self.assertEqual(self.signup(data).status_code, 201)
        data['password'] = 'AnotherClosed249!Strong'
        self.assertEqual(self.signup(data).status_code, 400)
        user = User.objects.get(username='teacher_test')
        self.assertTrue(user.check_password(self.password))
        self.assertEqual(User.objects.count(), 1)

    def test_existing_mixed_case_username_is_not_duplicated(self):
        User.objects.create_user('Teacher_Test', password=self.password)
        self.assertEqual(self.signup().status_code, 400)
        self.assertEqual(User.objects.count(), 1)

    def test_password_login_accepts_username_without_email(self):
        self.signup()
        for identity in ('teacher_test', 'TEACHER_TEST'):
            response = self.client.post(reverse('api:login'),
                json.dumps({'email': identity, 'password': self.password}),
                content_type='application/json')
            self.assertEqual(response.status_code, 200, response.content)
        user = User.objects.get(username='teacher_test')
        user.is_active = False
        user.save()
        response = self.client.post(reverse('api:login'),
            json.dumps({'email': user.username, 'password': self.password}),
            content_type='application/json')
        self.assertEqual(response.status_code, 401)

    def test_existing_email_login_still_works(self):
        User.objects.create_user('legacy_account', 'teacher@example.com', self.password)
        response = self.client.post(reverse('api:login'),
            json.dumps({'email': 'TEACHER@example.com', 'password': self.password}),
            content_type='application/json')
        self.assertEqual(response.status_code, 200)

    def test_weak_passwords_rejected(self):
        for password in ('12345678', 'password', 'short'):
            data = self.payload()
            data['password'] = password
            self.assertEqual(self.signup(data).status_code, 400)
        self.assertFalse(User.objects.exists())

    def test_username_and_full_name_required(self):
        for field in ('username', 'full_name'):
            data = self.payload()
            data[field] = ' '
            self.assertEqual(self.signup(data).status_code, 400)
        self.assertFalse(User.objects.exists())

    def test_email_cannot_be_used_as_unverified_username(self):
        data = self.payload()
        data['username'] = 'teacher@example.com'
        self.assertEqual(self.signup(data).status_code, 400)
        self.assertFalse(User.objects.exists())

    def test_malformed_fields_and_payload_rejected(self):
        for data in ({'username': []}, ['teacher'], {'full_name': 123}):
            self.assertEqual(self.signup(data).status_code, 400)
        self.assertFalse(User.objects.exists())

    def test_signup_rate_limit_still_blocks_sixth_attempt(self):
        for index in range(5):
            data = self.payload()
            data['username'] = f'teacher_{index}'
            self.assertEqual(self.signup(data).status_code, 201)
        response = self.signup()
        self.assertEqual(response.status_code, 429)
        self.assertIn('Retry-After', response)
        self.assertEqual(User.objects.count(), 5)

    @override_settings(ALLOW_USERNAME_SIGNUP=False)
    def test_feature_can_be_closed_without_disabling_existing_logins(self):
        self.assertEqual(self.signup().status_code, 400)
        self.assertFalse(User.objects.exists())
        User.objects.create_user('teacher_test', password=self.password)
        response = self.client.post(reverse('api:login'),
            json.dumps({'email': 'teacher_test', 'password': self.password}),
            content_type='application/json')
        self.assertEqual(response.status_code, 200)

    def test_web_form_signup_and_username_login(self):
        response = self.client.get(reverse('accounts:register'))
        self.assertContains(response, 'name="username"')
        self.assertNotContains(response, 'style="display:none"')
        self.assertNotContains(response, 'adsbygoogle.js')
        data = self.payload(password_confirm=self.password)
        response = self.client.post(reverse('accounts:register'), data)
        self.assertRedirects(response, reverse('accounts:login'), fetch_redirect_response=False)
        response = self.client.post(reverse('accounts:login'),
            {'email': 'teacher_test', 'password': self.password})
        self.assertRedirects(response, '/dashboard/', fetch_redirect_response=False)
        self.assertIn('_auth_user_id', self.client.session)

    def test_web_mismatched_password_does_not_create_user(self):
        response = self.client.post(reverse('accounts:register'),
            self.payload(password_confirm='DifferentPassword249!'))
        self.assertContains(response, 'Mật khẩu không khớp')
        self.assertFalse(User.objects.exists())

    def test_web_csrf_remains_required(self):
        response = Client(enforce_csrf_checks=True).post(reverse('accounts:register'),
            self.payload(password_confirm=self.password))
        self.assertEqual(response.status_code, 403)
        self.assertFalse(User.objects.exists())

    @patch('accounts.registration.start_signup')
    def test_legacy_email_api_keeps_verification_response(self, start):
        response = self.signup({'email': 'legacy@example.com', 'password': self.password,
                                'first_name': 'Nguyễn', 'last_name': 'An'})
        self.assertEqual(response.status_code, 202)
        self.assertTrue(response.json()['requires_email_verification'])
        self.assertNotIn('token', response.json())
        start.assert_called_once()
