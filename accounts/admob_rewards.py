"""AdMob ECDSA verification and account-bound, single-use reward tickets."""
import base64
import json
import re
import time
import uuid
from urllib.parse import parse_qsl, unquote
from urllib.request import urlopen
from zoneinfo import ZoneInfo

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec
from django.conf import settings
from django.core import signing
from django.core.cache import cache
from django.utils import timezone

from .credits import CreditError
from .models import RewardClaim

SALT = 'gradeflow.admob.reward.v1'
PROBE_SALT = 'gradeflow.admob.verify-url.v1'
KEY_URL = 'https://www.gstatic.com/admob/reward/verifier-keys.json'


def reward_period():
    return timezone.now().astimezone(ZoneInfo('Asia/Ho_Chi_Minh')).date().isoformat()


def reward_state(wallet):
    remaining = max(0, min(3, settings.CREDIT_REWARD_LIMIT) -
                    RewardClaim.objects.filter(wallet=wallet, period=reward_period()).count())
    return {'enabled': settings.ADMOB_SSV_ENABLED and not wallet.bonus_blocked,
            'points': settings.CREDIT_REWARD_POINTS, 'remaining': remaining}


def create_ticket(wallet):
    state = reward_state(wallet)
    if not state['enabled'] or state['remaining'] == 0:
        raise CreditError('Nhận thưởng chưa khả dụng hoặc đã hết lượt hôm nay.')
    return signing.dumps({'user_id': wallet.user_id, 'nonce': uuid.uuid4().hex,
                          'period': reward_period(), 'issued': int(time.time())}, salt=SALT)


def read_ticket(ticket, user_id=None):
    try:
        data = signing.loads(ticket, salt=SALT, max_age=86400)
        if not isinstance(data.get('user_id'), int) or data['user_id'] <= 0:
            raise ValueError()
        if not re.fullmatch(r'[0-9a-f]{32}', data['nonce']):
            raise ValueError()
        if user_id is not None and data['user_id'] != user_id:
            raise ValueError()
        return data
    except (signing.BadSignature, KeyError, ValueError, TypeError):
        raise CreditError('Phiên nhận thưởng không hợp lệ.') from None


def create_verification_probe():
    """Operator-generated token for Google's URL tester; never a reward ticket."""
    return signing.dumps({'purpose': 'verify-url', 'nonce': uuid.uuid4().hex}, salt=PROBE_SALT)


def verify_probe(request):
    token = request.GET.get('custom_data', '')
    try:
        data = signing.loads(token, salt=PROBE_SALT, max_age=1200)
        if data.get('purpose') != 'verify-url':
            return False
    except (signing.BadSignature, ValueError, TypeError, AttributeError):
        return False
    AdMobRewardProvider.verify_signature(request, verification_only=True)
    return True


def public_keys():
    keys = cache.get('admob-ssv-public-keys')
    if keys is None:
        with urlopen(KEY_URL, timeout=5) as response:
            keys = json.loads(response.read(65536))['keys']
        cache.set('admob-ssv-public-keys', keys, 3600)
    return {str(key['keyId']): key['pem'] for key in keys}


class AdMobRewardProvider:
    @staticmethod
    def verify_signature(request, verification_only=False):
        raw = request.META.get('QUERY_STRING', '')
        if len(raw) > 8192 or raw.count('&signature=') != 1:
            raise CreditError('Chữ ký quảng cáo không hợp lệ.')
        content, tail = raw.split('&signature=')
        pairs = parse_qsl(raw, keep_blank_values=True)
        params = dict(pairs)
        if len(params) != len(pairs) or not re.fullmatch(r'[^&]+&key_id=\d+', tail):
            raise CreditError('Tham số quảng cáo không hợp lệ.')
        try:
            pem = public_keys()[params['key_id']]
            key = serialization.load_pem_public_key(pem.encode())
            if not isinstance(key, ec.EllipticCurvePublicKey):
                raise ValueError()
            encoded = params['signature']
            signature = base64.b64decode(encoded + '=' * (-len(encoded) % 4),
                                         altchars=b'-_', validate=True)
            # Match Google's verifier using URI.getQuery(): percent-decoded
            # content with the original parameter order, never reserialized.
            key.verify(signature, unquote(content).encode('utf-8'), ec.ECDSA(hashes.SHA256()))
            timestamp = int(params['timestamp']) / 1000
            if not time.time() - 86400 <= timestamp <= time.time() + 300:
                raise ValueError()
            allowed_units = {settings.ADMOB_REWARDED_UNIT_ID,
                             settings.ADMOB_REWARDED_UNIT_ID.split('/')[-1]}
            if verification_only:
                # Google's URL tester uses this dummy unit, not the selected unit.
                allowed_units.add('1234567890')
            if params['ad_unit'] not in allowed_units:
                raise ValueError()
        except (InvalidSignature, KeyError, ValueError, TypeError):
            raise CreditError('Không xác minh được quảng cáo hoàn tất.') from None
        return params

    def verify_webhook(self, request):
        if not settings.ADMOB_SSV_ENABLED:
            raise CreditError('Nhận thưởng chưa được mở.')
        params = self.verify_signature(request)
        try:
            if not re.fullmatch(r'[0-9a-fA-F]{16,128}', params['transaction_id']):
                raise ValueError()
            if int(params['reward_amount']) <= 0:
                raise ValueError()
            ticket = read_ticket(params['custom_data'])
            if ticket['period'] != reward_period() or int(params['timestamp']) / 1000 < ticket['issued'] - 300:
                raise ValueError()
        except (KeyError, ValueError, TypeError):
            raise CreditError('Không xác minh được quảng cáo hoàn tất.') from None
        # One ticket grants at most once, even across multiple Google transactions.
        return {'status': 'completed', 'user_id': ticket['user_id'],
                'event_id': 'admob:' + ticket['nonce']}
