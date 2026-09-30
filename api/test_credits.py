from django.contrib.auth.models import User
from django.test import TestCase
from django.test import override_settings
from rest_framework.authtoken.models import Token
from rest_framework.test import APIClient

from accounts.credits import ensure_wallet
from accounts.models import CreditEntry
from accounts.admob_rewards import create_ticket, create_verification_probe
from unittest.mock import patch
from urllib.parse import urlencode, unquote
import base64
import time
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec


class MobileWalletTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user('wallet_teacher')
        self.client = APIClient()
        token = Token.objects.create(user=self.user)
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {token.key}')

    def test_requires_authentication(self):
        response = APIClient().get('/api/v1/credits/')
        self.assertEqual(response.status_code, 401)

    def test_existing_balance_and_entries_are_owner_only(self):
        wallet = ensure_wallet(self.user)
        wallet.balance = 73
        wallet.save(update_fields=['balance'])
        other = User.objects.create_user('other_wallet')
        ensure_wallet(other)
        response = self.client.get('/api/v1/credits/?user_id=' + str(other.pk))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['balance'], 73)
        self.assertEqual(response.data['scan_cost'], 1)
        self.assertEqual(len(response.data['entries']), 1)
        self.assertNotIn('reference', response.data['entries'][0])
        self.assertIn('private', response['Cache-Control'])
        self.assertIn('no-store', response['Cache-Control'])

    def test_refresh_never_awards_more_credits(self):
        for _ in range(3):
            self.assertEqual(self.client.get('/api/v1/credits/').data['balance'], 100)
        self.assertEqual(CreditEntry.objects.filter(wallet__user=self.user).count(), 1)

    def test_post_cannot_change_balance(self):
        wallet = ensure_wallet(self.user)
        self.assertEqual(self.client.post('/api/v1/credits/', {'balance': 999}).status_code, 405)
        wallet.refresh_from_db()
        self.assertEqual(wallet.balance, 100)


@override_settings(ADMOB_SSV_ENABLED=True, CREDIT_REWARD_POINTS=5,
                   CREDIT_REWARD_PERIOD='daily', CREDIT_REWARD_LIMIT=3,
                   CREDIT_REWARD_PROVIDER='accounts.admob_rewards.AdMobRewardProvider')
class AdMobRewardTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user('reward_teacher')
        self.wallet = ensure_wallet(self.user)
        self.client = APIClient()
        self.client.credentials(HTTP_AUTHORIZATION='Token ' + Token.objects.create(user=self.user).key)
        self.key = ec.generate_private_key(ec.SECP256R1())
        pem = self.key.public_key().public_bytes(serialization.Encoding.PEM,
                    serialization.PublicFormat.SubjectPublicKeyInfo).decode()
        self.keys = patch('accounts.admob_rewards.public_keys', return_value={'42': pem})
        self.keys.start()
        self.addCleanup(self.keys.stop)

    def callback(self, ticket=None, **overrides):
        params = dict(ad_network='5450213213286189855', ad_unit='6070051413',
                      custom_data=ticket or create_ticket(self.wallet), reward_amount='5',
                      reward_item='credits', timestamp=str(int(time.time() * 1000)),
                      transaction_id='abcde1234567890f')
        params.update(overrides)
        content = urlencode(params)
        signature = self.key.sign(unquote(content).encode(), ec.ECDSA(hashes.SHA256()))
        return content + '&signature=' + base64.urlsafe_b64encode(signature).decode().rstrip('=') + '&key_id=42'

    def send(self, query):
        return APIClient().get('/api/v1/credits/admob-callback/?' + query)

    def test_verified_reward_and_duplicate_are_idempotent(self):
        ticket = create_ticket(self.wallet)
        query = self.callback(ticket)
        self.assertEqual(self.send(query).status_code, 200)
        self.assertEqual(self.send(query).status_code, 200)
        # A different signed transaction with the same ticket also grants once.
        self.assertEqual(self.send(self.callback(ticket, transaction_id='f' * 32)).status_code, 200)
        self.wallet.refresh_from_db()
        self.assertEqual(self.wallet.balance, 105)
        self.assertEqual(self.client.post('/api/v1/credits/reward-status/',
                         {'ticket': ticket}).data, {'claimed': True})

    def test_daily_limit_is_enforced_server_side(self):
        queries = [self.callback() for _ in range(4)]
        for query in queries[:3]:
            self.assertEqual(self.send(query).status_code, 200)
        self.assertEqual(self.send(queries[3]).status_code, 400)
        self.assertEqual(self.client.post('/api/v1/credits/reward-ticket/').status_code, 409)
        self.wallet.refresh_from_db()
        self.assertEqual(self.wallet.balance, 115)

    def test_invalid_signed_content_and_tickets_never_award(self):
        cases = [self.callback().replace('reward_amount=5', 'reward_amount=50'),
                 self.callback(ad_unit='5100942496'),
                 self.callback(ad_unit='1234567890'),
                 self.callback(custom_data='forged-ticket'),
                 self.callback(timestamp='1'),
                 self.callback() + '&reward_amount=999',
                 self.callback() + '&key_id=42']
        for query in cases:
            self.assertEqual(self.send(query).status_code, 400)
        self.wallet.refresh_from_db()
        self.assertEqual(self.wallet.balance, 100)

    def test_blocked_bonus_and_other_account_status(self):
        ticket = create_ticket(self.wallet)
        other = User.objects.create_user('other_reward_teacher')
        other_client = APIClient()
        other_client.credentials(HTTP_AUTHORIZATION='Token ' + Token.objects.create(user=other).key)
        self.assertEqual(other_client.post('/api/v1/credits/reward-status/', {'ticket': ticket}).status_code, 400)
        self.wallet.bonus_blocked = True
        self.wallet.save(update_fields=['bonus_blocked'])
        self.assertEqual(self.send(self.callback(ticket)).status_code, 400)

    @override_settings(ADMOB_SSV_ENABLED=False)
    def test_disabled_program_accepts_neither_ticket_nor_reward(self):
        self.assertEqual(self.client.post('/api/v1/credits/reward-ticket/').status_code, 409)
        self.assertEqual(self.send('anything').status_code, 400)

    @override_settings(ADMOB_SSV_ENABLED=False)
    def test_google_url_probe_verifies_when_rewards_disabled_without_award(self):
        query = self.callback(ticket=create_verification_probe(),
                              ad_unit='1234567890', transaction_id='123456789',
                              reward_amount='10', reward_item='Reward')
        response = self.send(query)
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.data['verification_only'])
        self.wallet.refresh_from_db()
        self.assertEqual(self.wallet.balance, 100)
        self.assertEqual(CreditEntry.objects.filter(wallet=self.wallet).count(), 1)
        self.assertEqual(self.send(query.replace('reward_amount=10', 'reward_amount=50')).status_code, 400)

    def test_probe_can_never_be_used_as_reward_ticket(self):
        probe = create_verification_probe()
        self.assertEqual(self.send(self.callback(ticket=probe)).status_code, 200)
        self.assertEqual(self.client.post('/api/v1/credits/reward-status/', {'ticket': probe}).status_code, 400)
        self.wallet.refresh_from_db()
        self.assertEqual(self.wallet.balance, 100)
