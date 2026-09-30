import json
import tempfile
from datetime import timedelta
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch, Mock
from concurrent.futures import ThreadPoolExecutor

import requests
from django.contrib.auth.models import User, Permission, Group
from django.contrib.auth.hashers import make_password
from django.core import mail
from django.core.exceptions import ValidationError
from django.db import DatabaseError, close_old_connections
from django.test import Client, RequestFactory, TestCase, TransactionTestCase, override_settings
from django.urls import reverse
from django.utils import timezone
from rest_framework.authtoken.models import Token
from allauth.account.models import EmailAddress
from allauth.core.exceptions import ImmediateHttpResponse

from accounts.adapters import GoogleSocialAdapter
from accounts.models import CreditEntry, CreditWallet, PendingSignup, SecurityRateBucket, TeacherProfile
from accounts.registration import verify_challenge
from accounts.security import client_ip, take_limit
from grading.models import Exam, Submission, TrainingSample

TEST_STORAGES = {
    'default': {'BACKEND': 'django.core.files.storage.FileSystemStorage'},
    'staticfiles': {'BACKEND': 'django.contrib.staticfiles.storage.StaticFilesStorage'},
}


@override_settings(STORAGES=TEST_STORAGES)
class AccessBoundaryTests(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user('owner', 'owner@example.com', 'UniquePassword249!')
        self.other = User.objects.create_user('other', 'other@example.com', 'DifferentPassword249!')
        self.exam = Exam.objects.create(teacher=self.owner, title='Private exam', answer_key='{}')
        self.sub = Submission.objects.create(teacher=self.owner, exam=self.exam, student_name='Private student')

    def test_anonymous_legacy_and_v1_data_are_denied(self):
        paths = ['/api/me', '/api/dashboard', '/api/exams', '/api/events',
                 f'/api/exams/{self.exam.pk}', f'/api/exams/{self.exam.pk}/sheets',
                 f'/api/exams/{self.exam.pk}/export.xlsx', f'/api/sheets/{self.sub.pk}',
                 '/api/v1/exams/', '/api/v1/admin/users/']
        for path in paths:
            with self.subTest(path=path):
                self.assertEqual(self.client.get(path).status_code, 401)

    def test_other_user_cannot_read_modify_delete_or_export(self):
        self.client.force_login(self.other)
        operations = [
            ('get', f'/api/exams/{self.exam.pk}'),
            ('put', f'/api/exams/{self.exam.pk}'),
            ('delete', f'/api/exams/{self.exam.pk}'),
            ('post', f'/api/exams/{self.exam.pk}/key'),
            ('get', f'/api/exams/{self.exam.pk}/sheets'),
            ('get', f'/api/exams/{self.exam.pk}/export.xlsx'),
            ('get', f'/api/sheets/{self.sub.pk}'),
            ('put', f'/api/sheets/{self.sub.pk}'),
            ('get', f'/api/v1/exams/{self.exam.pk}/'),
            ('get', f'/api/v1/submissions/{self.sub.pk}/'),
        ]
        for method, path in operations:
            with self.subTest(method=method, path=path):
                response = getattr(self.client, method)(path, data='{}', content_type='application/json') if method != 'get' else self.client.get(path)
                self.assertEqual(response.status_code, 404)
        self.exam.refresh_from_db()
        self.assertEqual(self.exam.title, 'Private exam')
        self.assertEqual(self.exam.answer_key, '{}')
        self.assertEqual(Submission.objects.count(), 1)
        self.assertEqual(self.client.get('/api/exams').json()['items'], [])
        self.assertEqual(self.client.get('/api/v1/admin/users/').status_code, 403)

    def test_owner_can_read_and_edit_but_get_cannot_change_answer_key(self):
        self.client.force_login(self.owner)
        self.assertEqual(self.client.get(f'/api/exams/{self.exam.pk}').status_code, 200)
        self.assertEqual(self.client.get(f'/api/exams/{self.exam.pk}/key').status_code, 405)
        response = self.client.put(f'/api/exams/{self.exam.pk}', json.dumps({'name': 'Edited'}), content_type='application/json')
        self.assertEqual(response.status_code, 200)
        self.exam.refresh_from_db()
        self.assertEqual(self.exam.title, 'Edited')

    def test_csrf_protects_legacy_mutations_and_login(self):
        client = Client(enforce_csrf_checks=True)
        client.force_login(self.owner)
        path = f'/api/exams/{self.exam.pk}'
        self.assertEqual(client.put(path, '{}', content_type='application/json').status_code, 403)
        self.assertEqual(client.delete(path).status_code, 403)
        self.assertEqual(client.post('/api/logout').status_code, 403)
        self.assertEqual(Client(enforce_csrf_checks=True).post('/api/login', {}).status_code, 403)
        client.cookies['csrftoken'] = 'a' * 32
        self.assertEqual(client.put(path, '{}', content_type='application/json', HTTP_X_CSRFTOKEN='a' * 32).status_code, 200)

    def test_staff_with_user_permissions_cannot_promote_or_reset_admin(self):
        self.other.is_staff = True
        self.other.save()
        self.other.user_permissions.add(*Permission.objects.filter(codename__in=['change_user', 'add_user', 'change_group']))
        client = self.client
        client.force_login(self.other)
        self.assertEqual(client.post(reverse('admin:auth_user_change', args=[self.other.pk]), {'is_superuser': True}).status_code, 403)
        self.assertEqual(client.post(reverse('admin:auth_user_password_change', args=[self.owner.pk]), {}).status_code, 403)
        self.assertEqual(client.post(reverse('admin:auth_user_add'), {}).status_code, 403)
        group = Group.objects.create(name='operator')
        self.assertEqual(client.post(reverse('admin:auth_group_change', args=[group.pk]), {}).status_code, 403)
        self.other.refresh_from_db()
        self.assertFalse(self.other.is_superuser)


@override_settings(STORAGES=TEST_STORAGES)
class PrivateMediaTests(TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)
        self.settings_override = override_settings(MEDIA_ROOT=self.folder.name)
        self.settings_override.enable()
        self.addCleanup(self.settings_override.disable)
        self.owner = User.objects.create_user('owner')
        self.other = User.objects.create_user('other')
        self.sub = Submission.objects.create(teacher=self.owner, image='submissions/2026/09/test.png')
        TrainingSample.objects.create(teacher=self.owner, image='training/sample.jpg')
        TeacherProfile.objects.create(user=self.owner, avatar='avatars/test.jpg')
        self.paths = ['submissions/2026/09/test.png', 'submissions/2026/09/test_overlay.jpg',
                      'training/sample.jpg', 'avatars/test.jpg']
        for name in self.paths:
            target = Path(self.folder.name) / name
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(b'image fixture')

    def test_media_requires_owner_session_or_token_and_is_not_cached(self):
        for path in self.paths:
            self.assertEqual(self.client.get('/media/' + path).status_code, 401)
        self.client.force_login(self.other)
        for path in self.paths:
            self.assertEqual(self.client.get('/media/' + path).status_code, 404)
        self.client.logout()
        token = Token.objects.create(user=self.owner)
        for path in self.paths:
            response = self.client.get('/media/' + path, HTTP_AUTHORIZATION='Token ' + token.key)
            self.assertEqual(response.status_code, 200)
            self.assertIn('no-store', response['Cache-Control'])
            self.assertEqual(b''.join(response.streaming_content), b'image fixture')
            response.close()
        self.client.force_login(self.owner)
        response = self.client.get('/media/' + self.paths[0])
        self.assertEqual(response.status_code, 200)
        response.close()

    def test_unknown_file_traversal_and_html_denied(self):
        self.client.force_login(self.owner)
        for path in ['../db.sqlite3', 'submissions/../../../db.sqlite3', 'avatars/test.html', 'unknown.jpg']:
            self.assertEqual(self.client.get('/media/' + path).status_code, 404)

    def test_disabled_owner_token_cannot_read(self):
        token = Token.objects.create(user=self.owner)
        self.owner.is_active = False
        self.owner.save()
        self.assertEqual(self.client.get('/media/' + self.paths[0], HTTP_AUTHORIZATION='Token ' + token.key).status_code, 401)


@override_settings(STORAGES=TEST_STORAGES, EMAIL_HOST='smtp.example.com',
    EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend', TURNSTILE_SITE_KEY='test-site',
    TURNSTILE_SECRET_KEY='test-secret', TURNSTILE_HOSTNAMES=['gradeflow.io.vn'])
class VerifiedSignupTests(TestCase):
    data = {'full_name': 'Nguyễn An', 'email': 'new@example.com', 'password': 'UniquePassword249!',
            'password_confirm': 'UniquePassword249!', 'cf-turnstile-response': 'challenge-token'}

    def mock_challenge(self):
        patcher = patch('accounts.registration.requests.post')
        mock = patcher.start()
        self.addCleanup(patcher.stop)
        mock.return_value.json.return_value = {'success': True, 'hostname': 'gradeflow.io.vn', 'action': 'signup'}
        return mock

    def test_signup_requires_email_then_password_and_grants_once(self):
        self.mock_challenge()
        response = self.client.post('/accounts/register/', self.data)
        self.assertEqual(response.status_code, 302)
        self.assertFalse(User.objects.exists())
        self.assertFalse(CreditWallet.objects.exists())
        pending = PendingSignup.objects.get()
        self.assertNotEqual(pending.password_hash, self.data['password'])
        self.assertNotIn(self.data['password'], mail.outbox[0].body)
        url = reverse('accounts:verify_signup', args=[pending.token])
        self.assertEqual(self.client.get(url).status_code, 200)
        self.assertFalse(User.objects.exists())
        self.assertEqual(self.client.post(url, {'password': 'wrong'}).status_code, 400)
        self.assertFalse(User.objects.exists())
        self.assertEqual(self.client.post(url, {'password': self.data['password']}).status_code, 302)
        user = User.objects.get()
        self.assertTrue(user.check_password(self.data['password']))
        self.assertTrue(EmailAddress.objects.get(user=user).verified)
        self.assertEqual(user.credit_wallet.balance, 100)
        self.assertEqual(self.client.post(url, {'password': self.data['password']}).status_code, 400)
        self.assertEqual(CreditEntry.objects.count(), 1)

    def test_missing_config_and_forged_challenge_fail_closed(self):
        with override_settings(EMAIL_HOST=''):
            self.client.post('/accounts/register/', self.data)
        self.assertFalse(PendingSignup.objects.exists())
        self.assertFalse(User.objects.exists())
        mock = self.mock_challenge()
        for payload in ({'success': False}, {'success': True, 'hostname': 'evil.example', 'action': 'signup'},
                        {'success': True, 'hostname': 'gradeflow.io.vn', 'action': 'login'}):
            mock.return_value.json.return_value = payload
            with self.assertRaises(ValidationError):
                verify_challenge(RequestFactory().post('/'), 'forged')
        mock.side_effect = requests.Timeout()
        with self.assertRaises(ValidationError):
            verify_challenge(RequestFactory().post('/'), 'timeout')

    def test_expired_confirmation_and_alternate_signup_are_blocked(self):
        pending = PendingSignup.objects.create(email='old@example.com', password_hash=make_password('secret'),
                                              expires_at=timezone.now() - timedelta(seconds=1))
        self.assertEqual(self.client.post(reverse('accounts:verify_signup', args=[pending.token]), {'password': 'secret'}).status_code, 400)
        self.client.post('/accounts/signup/', {'email': 'bypass@example.com', 'password1': 'UniquePassword249!', 'password2': 'UniquePassword249!'})
        self.assertFalse(User.objects.exists())

    def test_api_cannot_bypass_email_or_create_admin(self):
        self.mock_challenge()
        data = {'email': 'api@example.com', 'password': self.data['password'], 'first_name': 'An',
                'turnstile_token': 'challenge', 'is_superuser': True, 'is_staff': True, 'balance': 99999}
        response = self.client.post('/api/v1/auth/register/', data, content_type='application/json')
        self.assertEqual(response.status_code, 202)
        self.assertNotIn('token', response.json())
        self.assertFalse(User.objects.exists())
        pending = PendingSignup.objects.get()
        self.client.post(reverse('accounts:verify_signup', args=[pending.token]), {'password': data['password']})
        user = User.objects.get()
        self.assertFalse(user.is_staff or user.is_superuser)
        self.assertEqual(user.credit_wallet.balance, 100)

    def test_unverified_google_email_is_rejected(self):
        social = SimpleNamespace(user=User(email='fake@example.com'), account=SimpleNamespace(provider='google'),
                                 email_addresses=[SimpleNamespace(email='fake@example.com', verified=False)])
        with self.assertRaises(ImmediateHttpResponse):
            GoogleSocialAdapter().pre_social_login(RequestFactory().get('/'), social)

    def test_two_verified_emails_same_ip_currently_receive_two_welcome_grants(self):
        """Documents the abuse gap: rate limiting is not one-person verification."""
        self.mock_challenge()
        for email in ['multi-one@example.com', 'multi-two@example.com']:
            client = Client(REMOTE_ADDR='192.0.2.20')
            response = client.post('/accounts/register/', dict(self.data, email=email))
            self.assertEqual(response.status_code, 302)
            pending = PendingSignup.objects.get(email=email)
            response = client.post(reverse('accounts:verify_signup', args=[pending.token]),
                                   {'password': self.data['password']})
            self.assertEqual(response.status_code, 302)
        self.assertEqual(User.objects.count(), 2)
        self.assertEqual(list(CreditWallet.objects.order_by('pk').values_list('balance', flat=True)), [100, 100])
        self.assertEqual(CreditEntry.objects.count(), 2)

    def test_sixth_signup_same_ip_is_blocked_even_with_new_session(self):
        self.mock_challenge()
        for index in range(6):
            client = Client(REMOTE_ADDR='192.0.2.21')
            response = client.post('/accounts/register/', dict(self.data, email=f'limit-{index}@example.com'))
            self.assertEqual(response.status_code, 302 if index < 5 else 429)
        self.assertEqual(PendingSignup.objects.count(), 5)
        self.assertEqual(User.objects.count(), 0)

    @override_settings(EMAIL_HOST='', TURNSTILE_SECRET_KEY='')
    def test_two_email_signups_without_configuration_create_no_accounts(self):
        for email in ['closed-one@example.com', 'closed-two@example.com']:
            self.client.post('/accounts/register/', dict(self.data, email=email))
        self.assertEqual(User.objects.count(), 0)
        self.assertEqual(CreditWallet.objects.count(), 0)
        self.assertEqual(PendingSignup.objects.count(), 0)


@override_settings(STORAGES=TEST_STORAGES, TRUST_PROXY_CLIENT_IP=False)
class AuthenticationLimitTests(TestCase):
    @override_settings(SECURE_SSL_REDIRECT=True, SECURE_REDIRECT_EXEMPT=[r'^ads\.txt$'], SECURE_HSTS_SECONDS=3600)
    def test_http_redirects_before_login_and_internal_healthcheck_still_works(self):
        response = self.client.get('/accounts/login/')
        self.assertEqual(response.status_code, 301)
        self.assertTrue(response['Location'].startswith('https://'))
        self.assertEqual(self.client.get('/ads.txt').status_code, 200)
        response = self.client.get('/accounts/login/', HTTP_X_FORWARDED_PROTO='https')
        self.assertEqual(response.status_code, 200)
        self.assertIn('max-age=3600', response['Strict-Transport-Security'])

    def test_shared_limit_covers_different_login_routes(self):
        for i in range(12):
            response = self.client.post('/api/v1/auth/login/', {'email': 'unknown@example.com', 'password': 'wrong'}, content_type='application/json')
            self.assertEqual(response.status_code, 401)
        response = self.client.post('/accounts/login/', {'email': 'UNKNOWN@example.com', 'password': 'wrong'})
        self.assertEqual(response.status_code, 429)
        self.assertIn('Retry-After', response)
        self.assertFalse(any('unknown@example.com' in bucket.key for bucket in SecurityRateBucket.objects.all()))

    def test_limit_expires_and_is_shared_between_calls(self):
        with patch('accounts.security.time.time', return_value=6000):
            self.assertTrue(take_limit('test', 'identity', 1, 60))
            self.assertFalse(take_limit('test', 'identity', 1, 60))
        with patch('accounts.security.time.time', return_value=6061):
            self.assertTrue(take_limit('test', 'identity', 1, 60))

    def test_arbitrary_forwarded_ip_is_not_trusted(self):
        request = RequestFactory().get('/', REMOTE_ADDR='127.0.0.1', HTTP_X_FORWARDED_FOR='1.2.3.4',
                                       HTTP_X_GRADEFLOW_CLIENT_IP='5.6.7.8')
        self.assertEqual(client_ip(request), '127.0.0.1')
        with override_settings(TRUST_PROXY_CLIENT_IP=True):
            self.assertEqual(client_ip(request), '5.6.7.8')

    def test_storage_failure_denies_authentication(self):
        with patch('accounts.security.take_limit', side_effect=DatabaseError('unavailable')):
            self.assertEqual(self.client.post('/api/v1/auth/login/', {}).status_code, 503)

    def test_login_never_bypasses_backend_denial(self):
        User.objects.create_user('teacher', 'teacher@example.com', 'UniquePassword249!')
        with patch('accounts.views.authenticate', return_value=None):
            self.client.post('/accounts/login/', {'email': 'teacher@example.com', 'password': 'UniquePassword249!'})
        self.assertNotIn('_auth_user_id', self.client.session)


class ConcurrentLimitTests(TransactionTestCase):
    def test_parallel_requests_cannot_exceed_bucket(self):
        def attempt(_):
            close_old_connections()
            try:
                return take_limit('parallel', 'same-ip', 3, 3600)
            finally:
                close_old_connections()
        with ThreadPoolExecutor(max_workers=4) as pool:
            results = list(pool.map(attempt, range(8)))
        self.assertEqual(sum(results), 3)
        self.assertEqual(SecurityRateBucket.objects.get().hits, 3)
