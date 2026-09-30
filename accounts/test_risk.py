import uuid
from datetime import timedelta

from django.contrib.auth.models import User
from django.test import TestCase, RequestFactory, override_settings
from django.utils import timezone

from grading.models import Exam, ExamVariant
from .credits import CreditError, reserve_scan, finish_scan, adjust_credits
from .credit_integrations import _complete_reward
from .models import AccountNetwork, AccountRisk, ModerationEvent, CreditEntry
from .risk import observe, assess, moderate, welcome_remaining, answer_digest


@override_settings(SECURE_SSL_REDIRECT=False, TRUST_PROXY_CLIENT_IP=False,
 STORAGES={'default': {'BACKEND': 'django.core.files.storage.FileSystemStorage'},
           'staticfiles': {'BACKEND': 'django.contrib.staticfiles.storage.StaticFilesStorage'}})
class RiskTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_superuser('riskadmin', 'admin@test.test', 'SomePassword123!')
        self.a = User.objects.create_user('a', 'a@test.test', 'SomePassword123!')
        self.b = User.objects.create_user('b', 'b@test.test', 'SomePassword123!')
        self.request = RequestFactory().get('/', REMOTE_ADDR='192.0.2.10')

    def pair(self):
        observe(self.a, self.request)
        observe(self.b, self.request)
        assess(self.b)
        return AccountRisk.objects.get()

    def test_shared_ip_flags_without_penalty_and_hashes_ip(self):
        case = self.pair()
        self.assertEqual(case.score, 40)
        self.assertNotEqual(AccountNetwork.objects.first().network, '192.0.2.10')
        self.a.refresh_from_db()
        self.assertTrue(self.a.is_active)
        self.assertEqual(self.a.credit_wallet.balance, 100)
        self.assertEqual(self.b.credit_wallet.balance, 100)

    def test_old_signup_shared_ip_only_low(self):
        self.a.date_joined -= timedelta(days=3)
        self.a.save()
        self.assertEqual(self.pair().score, 20)

    def test_same_answers_near_creation_high_including_variant(self):
        e1 = Exam.objects.create(teacher=self.a, title='One')
        e2 = Exam.objects.create(teacher=self.b, title='Two')
        import json
        key = json.dumps({'p1': {str(i): 'A' for i in range(1, 11)}})
        ExamVariant.objects.create(exam=e1, variant_code='101', answers_json=key)
        ExamVariant.objects.create(exam=e2, variant_code='201', answers_json=key)
        case = self.pair()
        self.assertEqual(case.score, 100)
        self.assertTrue(case.evidence['matching_exams'])
        case.status = 'dismissed'
        case.save()
        assess(self.a)
        self.assertEqual(AccountRisk.objects.count(), 1)
        case.refresh_from_db()
        self.assertEqual(case.status, 'dismissed')

    def test_blank_config_keys_and_different_networks_do_not_match(self):
        self.assertIsNone(answer_digest('{"parts":[40,8,6],"scoring":{}}'))
        self.assertIsNone(answer_digest(''))
        self.assertIsNone(answer_digest('A,B'))
        observe(self.a, self.request)
        observe(self.b, RequestFactory().get('/', REMOTE_ADDR='192.0.2.11'))
        assess(self.b)
        self.assertFalse(AccountRisk.objects.exists())

    def test_welcome_revoke_preserves_purchased_credits_and_is_idempotent(self):
        wallet = self.a.credit_wallet
        op, _ = reserve_scan(self.a, 'scan1', 'abc', 20)
        finish_scan(op, 20, '{}', 200, 'application/json')
        adjust_credits(wallet.pk, 500, 'Purchase equivalent', self.admin, 'purchase:test')
        ref = uuid.uuid4()
        event = moderate(self.admin, self.a.pk, 'revoke', 'Confirmed by admin', ref)
        self.assertEqual(event.details['revoked'], 80)
        moderate(self.admin, self.a.pk, 'revoke', 'Confirmed by admin', ref)
        wallet.refresh_from_db()
        self.assertEqual(wallet.balance, 500)
        self.assertTrue(wallet.bonus_blocked)
        self.assertEqual(ModerationEvent.objects.count(), 1)
        with self.assertRaises(CreditError):
            moderate(self.admin, self.a.pk, 'revoke', 'Again', uuid.uuid4())

    def test_refund_restores_only_welcome_portion(self):
        wallet = self.a.credit_wallet
        adjust_credits(wallet.pk, 100, 'Extra', self.admin, 'purchase:extra')
        op, _ = reserve_scan(self.a, 'large', 'x', 150)
        with self.assertRaises(CreditError):
            moderate(self.admin, self.a.pk, 'revoke', 'Check', uuid.uuid4())
        finish_scan(op, 60, '{}', 200, 'application/json')
        wallet.refresh_from_db()
        self.assertEqual(welcome_remaining(wallet), 40)
        moderate(self.admin, self.a.pk, 'revoke', 'Check', uuid.uuid4())
        wallet.refresh_from_db()
        self.assertEqual(wallet.balance, 100)

    @override_settings(CREDIT_REWARD_POINTS=2, CREDIT_REWARD_PERIOD='daily', CREDIT_REWARD_LIMIT=3)
    def test_block_bonus_at_backend_and_unlock(self):
        moderate(self.admin, self.a.pk, 'block_bonus', 'Review', uuid.uuid4())
        event = {'status': 'completed', 'event_id': 'verified-provider-event', 'user_id': self.a.pk}
        with self.assertRaises(CreditError):
            _complete_reward(event)
        moderate(self.admin, self.a.pk, 'unblock_bonus', 'Cleared', uuid.uuid4())
        _complete_reward(event)
        self.a.credit_wallet.refresh_from_db()
        self.assertEqual(self.a.credit_wallet.balance, 102)

    def test_permissions_lock_and_protected_admin(self):
        with self.assertRaises(CreditError):
            moderate(self.a, self.b.pk, 'lock', 'Try', uuid.uuid4())
        with self.assertRaises(CreditError):
            moderate(self.admin, self.admin.pk, 'lock', 'Try', uuid.uuid4())
        from rest_framework.authtoken.models import Token
        Token.objects.create(user=self.a)
        self.client.force_login(self.a)
        moderate(self.admin, self.a.pk, 'lock', 'Confirmed', uuid.uuid4())
        self.assertFalse(Token.objects.filter(user=self.a).exists())
        self.assertEqual(self.client.get('/dashboard/').status_code, 302)
        moderate(self.admin, self.a.pk, 'unlock', 'Resolved', uuid.uuid4())
        self.a.refresh_from_db()
        self.assertTrue(self.a.is_active)

    def test_dashboard_detail_render_and_staff_denied(self):
        case = self.pair()
        self.client.force_login(self.admin)
        self.assertContains(self.client.get('/admin/'), 'Trung tâm quản trị')
        self.assertContains(self.client.get('/admin/security/'), self.a.email)
        self.assertContains(self.client.get(f'/admin/security/{case.pk}/'), 'Bằng chứng quan sát')
        self.b.is_staff = True
        self.b.save()
        self.client.force_login(self.b)
        self.assertEqual(self.client.get('/admin/security/').status_code, 403)

    def test_csrf_and_get_cannot_moderate(self):
        from django.test import Client
        case = self.pair()
        client = Client(enforce_csrf_checks=True)
        client.force_login(self.admin)
        url = f'/admin/security/{case.pk}/'
        client.get(url+'?action=lock&user='+str(self.a.pk))
        self.assertFalse(ModerationEvent.objects.exists())
        self.assertEqual(client.post(url, {'user': self.a.pk, 'action': 'lock'}).status_code, 403)

    def test_successful_login_records_network_through_middleware(self):
        self.client.force_login(self.a)
        self.client.get('/dashboard/', REMOTE_ADDR='192.0.2.10')
        self.assertTrue(AccountNetwork.objects.filter(user=self.a).exists())

    def test_mobile_login_records_network(self):
        response = self.client.post('/api/v1/auth/login/', {'email': self.a.email, 'password': 'SomePassword123!'}, content_type='application/json', REMOTE_ADDR='192.0.2.10')
        self.assertEqual(response.status_code, 200)
        self.assertTrue(AccountNetwork.objects.filter(user=self.a).exists())

    def test_admin_post_requires_confirmation_and_pair_membership(self):
        case = self.pair()
        self.client.force_login(self.admin)
        url = f'/admin/security/{case.pk}/'
        data = {'user': self.a.pk, 'action': 'block_bonus', 'reason': 'Reviewed', 'reference': str(uuid.uuid4())}
        response = self.client.post(url, data)
        self.assertEqual(response.status_code, 200)
        self.assertFalse(ModerationEvent.objects.exists())
        data['confirm'] = 'on'
        self.assertEqual(self.client.post(url, data).status_code, 302)
        self.a.credit_wallet.refresh_from_db()
        self.assertTrue(self.a.credit_wallet.bonus_blocked)
        data.update(user=self.admin.pk, reference=str(uuid.uuid4()))
        self.assertEqual(self.client.post(url, data).status_code, 403)


from django.test import TransactionTestCase
from django.db import close_old_connections
from concurrent.futures import ThreadPoolExecutor


@override_settings(PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher'])
class ConcurrentModerationTests(TransactionTestCase):
    def test_concurrent_revoke_only_one_ledger_entry(self):
        admin = User.objects.create_superuser('root', 'root@test.test', 'test')
        user = User.objects.create_user('target', 'target@test.test', 'test')
        def run(_):
            close_old_connections()
            try:
                return moderate(admin, user.pk, 'revoke', 'Verified', uuid.uuid4()).details['revoked']
            except CreditError:
                return 0
            finally:
                close_old_connections()
        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(run, range(2)))
        self.assertEqual(sum(results), 100)
        self.assertEqual(CreditEntry.objects.filter(reference=f'revoke-welcome:{user.pk}').count(), 1)
        user.credit_wallet.refresh_from_db()
        self.assertEqual(user.credit_wallet.balance, 0)
