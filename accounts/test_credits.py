import io
import json
import tempfile
import uuid
import zipfile
from concurrent.futures import ThreadPoolExecutor
from types import SimpleNamespace
from unittest.mock import patch

from django.contrib.auth.models import User, Permission
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import close_old_connections
from django.http import JsonResponse
from django.test import TestCase, TransactionTestCase, RequestFactory, override_settings
from django.urls import reverse
from rest_framework.test import APIClient

from accounts.credits import (ensure_wallet, reserve_scan, finish_scan, adjust_credits,
                             InsufficientCredits, CreditError)
from accounts.models import CreditEntry, CreditWallet, ScanOperation, CreditPurchase, RewardClaim
from accounts.scan_billing import bill_scans
from accounts.credit_integrations import create_checkout, payment_webhook, reward_webhook
from grading.models import Exam, Submission


class WalletFixture(TestCase):
    def setUp(self):
        self.user = User.objects.create_user('teacher', email='teacher@example.com', password='SafePassword249!')
        self.wallet = self.user.credit_wallet

    def balance(self):
        self.wallet.refresh_from_db()
        return self.wallet.balance


class WalletTests(WalletFixture):

    def test_initial_grant_only_once(self):
        ensure_wallet(self.user)
        self.user.save()
        self.assertEqual(self.balance(), 100)
        self.assertEqual(self.wallet.entries.count(), 1)

    def test_success_and_retry_charge_once(self):
        operation, created = reserve_scan(self.user, 'one', 'fingerprint', 1)
        self.assertTrue(created)
        finish_scan(operation, 1, '{}', 200, 'application/json')
        duplicate, created = reserve_scan(self.user, 'one', 'fingerprint', 1)
        self.assertFalse(created)
        self.assertTrue(duplicate.finished)
        finish_scan(duplicate, 1, '{}', 200, 'application/json')
        self.assertEqual(self.balance(), 99)

    def test_partial_batch_refund_only_once(self):
        operation, _ = reserve_scan(self.user, 'batch', 'fingerprint', 4)
        finish_scan(operation, 2, '{}', 200, 'application/json')
        finish_scan(operation, 0, '{}', 200, 'application/json')
        self.assertEqual(self.balance(), 98)
        self.assertEqual(sum(self.wallet.entries.values_list('amount', flat=True)), 98)

    def test_insufficient_balance_rolls_back_operation(self):
        with self.assertRaises(InsufficientCredits):
            reserve_scan(self.user, 'large', 'f', 101)
        self.assertEqual(self.balance(), 100)
        self.assertFalse(ScanOperation.objects.exists())

    def test_reused_key_with_different_content_is_rejected(self):
        reserve_scan(self.user, 'same-key', 'image-a', 1)
        with self.assertRaises(CreditError):
            reserve_scan(self.user, 'same-key', 'image-b', 1)
        self.assertEqual(self.balance(), 99)

    def test_adjustment_requires_permission_and_logs_actor(self):
        with self.assertRaises(PermissionError):
            adjust_credits(self.wallet.pk, 5, 'test', self.user, 'adjust-1')
        admin = User.objects.create_superuser('admin', 'admin@example.com', 'SafeAdmin249!')
        entry = adjust_credits(self.wallet.pk, 5, 'Đối soát', admin, 'adjust-1')
        adjust_credits(self.wallet.pk, 5, 'Đối soát', admin, 'adjust-1')
        self.assertEqual(self.balance(), 105)
        self.assertEqual(entry.actor, admin)
        with self.assertRaises(InsufficientCredits):
            adjust_credits(self.wallet.pk, -106, 'Trừ', admin, 'adjust-2')
        self.assertEqual(self.balance(), 105)


class ScanEndpointTests(WalletFixture):
    def setUp(self):
        super().setUp()
        self.media = tempfile.TemporaryDirectory()
        self.addCleanup(self.media.cleanup)
        setting = override_settings(MEDIA_ROOT=self.media.name)
        setting.enable()
        self.addCleanup(setting.disable)
        self.client.force_login(self.user)
        self.api = APIClient()
        self.api.force_authenticate(self.user)
        self.exam = Exam.objects.create(teacher=self.user, title='Test', template_code='40-08-06',
            answer_key=json.dumps({'parts': [40, 8, 6], 'scoring': {'p1': 0.1, 'p2': 0.5, 'p3': 0.25, 'max': 10}}))

    def image(self, content=b'image', name='sheet.jpg'):
        return SimpleUploadedFile(name, content, content_type='image/jpeg')

    def result(self):
        return {'success': True, 'score': 1, 'max_score': 40, 'sbd': '001', 'made': '', 'part1': {}, 'part2': {}, 'part3': {}}

    def test_mobile_success_replay_and_no_duplicate_submission(self):
        with patch('api.views.grade_image', return_value=self.result()) as engine:
            response = self.api.post('/api/v1/grade/', {'image': self.image(), 'exam_id': self.exam.pk}, format='multipart', HTTP_IDEMPOTENCY_KEY='mobile-1')
            self.assertTrue(response.json()['success'])
            replay = self.api.post('/api/v1/grade/', {'image': self.image(), 'exam_id': self.exam.pk}, format='multipart', HTTP_IDEMPOTENCY_KEY='mobile-1')
            self.assertEqual(replay.json(), response.json())
            self.assertEqual(engine.call_count, 1)
        self.assertEqual(Submission.objects.count(), 1)
        self.assertEqual(self.balance(), 99)

    def test_mobile_failure_refunds_and_zero_credit_blocks_engine(self):
        with patch('api.views.grade_image', return_value={'success': False}) as engine:
            self.api.post('/api/v1/grade/', {'image': self.image()}, format='multipart')
            self.assertEqual(self.balance(), 100)
            CreditWallet.objects.filter(pk=self.wallet.pk).update(balance=0)
            response = self.api.post('/api/v1/grade/', {'image': self.image(b'another')}, format='multipart')
            self.assertEqual(response.status_code, 402)
            self.assertEqual(engine.call_count, 1)

    def test_mobile_invalid_exam_refunds(self):
        response = self.api.post('/api/v1/grade/', {'image': self.image(), 'exam_id': 999999}, format='multipart')
        self.assertEqual(response.status_code, 404)
        self.assertEqual(self.balance(), 100)

    def test_old_client_content_retry_and_changed_answer_key(self):
        with patch('api.views.grade_image', return_value=self.result()) as engine:
            for _ in range(2):
                self.api.post('/api/v1/grade/', {'image': self.image(), 'exam_id': self.exam.pk}, format='multipart')
            self.assertEqual(engine.call_count, 1)
            self.exam.answer_key = json.dumps({'parts': [40, 8, 6], 'scoring': {'p1': 0.2, 'max': 10}})
            self.exam.save()
            self.api.post('/api/v1/grade/', {'image': self.image(), 'exam_id': self.exam.pk}, format='multipart')
            self.assertEqual(engine.call_count, 2)
        self.assertEqual(self.balance(), 98)

    def test_invalid_key_does_not_call_engine(self):
        with patch('api.views.grade_image') as engine:
            response = self.api.post('/api/v1/grade/', {'image': self.image(), 'scan_key': 'bad\nkey'}, format='multipart')
            self.assertEqual(response.status_code, 409)
            engine.assert_not_called()
        self.assertEqual(self.balance(), 100)

    def test_web_partial_batch(self):
        with patch('grading.views.grade_image', side_effect=[self.result(), {'success': False}]):
            response = self.client.post('/grading/upload/', {'images': [self.image(), self.image(b'bad')], 'exam_id': self.exam.pk, 'template_code': '40-08-06', 'scan_key': 'web1'})
        self.assertEqual(response.status_code, 302)
        self.assertEqual(self.balance(), 99)
        self.assertEqual(ScanOperation.objects.get().charged, 1)

    def test_regrade_success_charges_once(self):
        sub = Submission.objects.create(teacher=self.user, exam=self.exam, image=self.image())
        with patch('grading.views.grade_image', return_value=self.result()) as engine:
            url = reverse('grading:submission_regrade', args=[sub.pk])
            self.client.post(url, {'scan_key': 'regrade1'})
            self.client.post(url, {'scan_key': 'regrade1'})
            self.assertEqual(engine.call_count, 1)
        self.assertEqual(self.balance(), 99)

    def test_frame_success_and_failure(self):
        with patch('grading.views.grade_image', return_value=self.result()):
            response = self.client.post('/grading/api/grade-frame/', {'image': self.image(), 'fast': '1'})
        self.assertTrue(response.json()['success'])
        self.assertEqual(self.balance(), 99)
        with patch('grading.views.grade_image', return_value={'success': False}):
            self.client.post('/grading/api/grade-frame/', {'image': self.image(b'bad'), 'fast': '1'})
        self.assertEqual(self.balance(), 99)

    def test_legacy_batch_requires_login_and_owner(self):
        self.client.logout()
        url = f'/api/exams/{self.exam.pk}/grade'
        self.assertEqual(self.client.post(url, {'files': self.image()}).status_code, 401)
        other = User.objects.create_user('other')
        self.client.force_login(other)
        self.assertEqual(self.client.post(url, {'files': self.image()}).status_code, 404)
        self.assertEqual(other.credit_wallet.balance, 100)

    def test_zip_reserves_per_image_and_refunds_decode_errors(self):
        data = io.BytesIO()
        with zipfile.ZipFile(data, 'w') as archive:
            archive.writestr('a.jpg', b'invalid')
            archive.writestr('b.png', b'invalid')
            archive.writestr('readme.txt', b'ignored')
        response = self.client.post(f'/api/exams/{self.exam.pk}/grade', {'files': self.image(data.getvalue(), 'sheets.zip')})
        self.assertEqual(response.json()['n_errors'], 2)
        self.assertEqual(ScanOperation.objects.get().reserved, 2)
        self.assertEqual(self.balance(), 100)

    def test_exception_refunds_unused_reservation(self):
        @bill_scans()
        def failing_view(request):
            raise RuntimeError('test')
        request = RequestFactory().post('/fake', {'image': self.image()})
        request.user = self.user
        with self.assertRaises(RuntimeError):
            failing_view(request)
        self.assertEqual(self.balance(), 100)

    def test_csrf_required_for_session_scan(self):
        from django.test import Client
        client = Client(enforce_csrf_checks=True)
        client.force_login(self.user)
        for url in ('/grading/api/grade-frame/', f'/api/exams/{self.exam.pk}/grade'):
            self.assertEqual(client.post(url, {'image': self.image()}).status_code, 403)


class CreditConcurrencyTests(TransactionTestCase):
    def test_two_simultaneous_requests_cannot_spend_last_credit_twice(self):
        user = User.objects.create_user('concurrency')
        CreditWallet.objects.filter(user=user).update(balance=1)

        def spend(key):
            close_old_connections()
            try:
                reserve_scan(User.objects.get(pk=user.pk), key, key, 1)
                return 'reserved'
            except InsufficientCredits:
                return 'insufficient'
            finally:
                close_old_connections()

        with ThreadPoolExecutor(max_workers=2) as executor:
            results = list(executor.map(spend, ['one', 'two']))
        self.assertCountEqual(results, ['reserved', 'insufficient'])
        self.assertEqual(CreditWallet.objects.get(user=user).balance, 0)
        self.assertEqual(ScanOperation.objects.count(), 1)

    def test_simultaneous_same_key_reserves_once(self):
        from threading import Barrier
        user = User.objects.create_user('same-request')
        barrier = Barrier(2)

        def spend(_):
            close_old_connections()
            try:
                local_user = User.objects.get(pk=user.pk)
                barrier.wait(timeout=5)
                return reserve_scan(local_user, 'same', 'fingerprint', 1)[1]
            finally:
                close_old_connections()

        with ThreadPoolExecutor(max_workers=2) as executor:
            results = list(executor.map(spend, range(2)))
        self.assertCountEqual(results, [True, False])
        self.assertEqual(CreditWallet.objects.get(user=user).balance, 99)
        self.assertEqual(ScanOperation.objects.count(), 1)

    def test_pending_duplicate_returns_conflict(self):
        user = User.objects.create_user('pending-request')
        api = APIClient()
        api.force_authenticate(user)
        with patch('accounts.scan_billing._request_identity', return_value=('pending', 'fingerprint')):
            reserve_scan(user, 'pending', 'fingerprint', 1)
            with patch('api.views.grade_image') as engine:
                response = api.post('/api/v1/grade/', {'image': SimpleUploadedFile('s.jpg', b'image')}, format='multipart')
                self.assertEqual(response.status_code, 409)
                engine.assert_not_called()
        self.assertEqual(CreditWallet.objects.get(user=user).balance, 99)


class IntegrationTests(WalletFixture):
    def test_unconfigured_providers_never_issue_points(self):
        for function in (payment_webhook, reward_webhook):
            with self.assertRaises(CreditError):
                function(SimpleNamespace())
        with self.assertRaises(CreditError):
            create_checkout(self.user, 'anything')
        self.assertEqual(self.balance(), 100)

    @override_settings(CREDIT_REWARD_POINTS=2, CREDIT_REWARD_PERIOD='daily', CREDIT_REWARD_LIMIT=3)
    def test_verified_reward_quota_and_replay(self):
        with patch('accounts.credit_integrations.provider') as provider:
            for index in range(3):
                provider.return_value.verify_webhook.return_value = {'status': 'completed', 'event_id': str(index), 'user_id': self.user.pk}
                reward_webhook(None)
                reward_webhook(None)
            provider.return_value.verify_webhook.return_value = {'status': 'completed', 'event_id': 'four', 'user_id': self.user.pk}
            with self.assertRaises(CreditError):
                reward_webhook(None)
        self.assertEqual(self.balance(), 106)
        self.assertEqual(RewardClaim.objects.count(), 3)

    def test_invalid_signature_never_reaches_grant(self):
        with patch('accounts.credit_integrations.provider') as provider:
            provider.return_value.verify_webhook.side_effect = CreditError('invalid signature')
            with self.assertRaises(CreditError):
                reward_webhook(None)
        self.assertEqual(self.balance(), 100)

    def test_payment_replay_and_amount_check(self):
        order = CreditPurchase.objects.create(user=self.user, reference=uuid.uuid4(), points=20, amount_minor=1000, currency='VND')
        event = {'order_reference': order.reference, 'amount_minor': 1, 'currency': 'VND', 'status': 'paid'}
        with patch('accounts.credit_integrations.provider') as provider:
            provider.return_value.verify_webhook.return_value = event
            with self.assertRaises(CreditError):
                payment_webhook(None)
            event['amount_minor'] = 1000
            payment_webhook(None)
            payment_webhook(None)
        self.assertEqual(self.balance(), 120)
