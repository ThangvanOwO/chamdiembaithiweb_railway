"""Provider boundary. Only verified server events may issue purchased/reward credits.

Adapters are configured by the operator, never by HTTP input. They must verify
provider signatures, timestamps, event IDs, user binding and successful completion.
AdMob rewards have a verified adapter; payments require a configured adapter.
"""
import uuid
from zoneinfo import ZoneInfo

from django.conf import settings
from django.db.models import F
from django.utils import timezone
from django.utils.module_loading import import_string

from .credits import CreditError, _entry, ensure_wallet, wallet_transaction
from .models import CreditEntry, CreditPurchase, CreditWallet, RewardClaim


def provider(kind):
    path = getattr(settings, f'CREDIT_{kind.upper()}_PROVIDER', '')
    if not path:
        raise CreditError('Chức năng chưa được mở. Vui lòng quay lại sau.')
    return import_string(path)()


def create_checkout(user, package):
    adapter = provider('payment')
    offer = settings.CREDIT_PACKAGES.get(package)
    if not offer or offer['points'] <= 0 or offer['amount_minor'] <= 0:
        raise CreditError('Gói tín dụng chưa khả dụng.')
    order = CreditPurchase.objects.create(user=user, reference=uuid.uuid4(),
        points=offer['points'], amount_minor=offer['amount_minor'], currency=offer['currency'])
    return adapter.create_checkout(order)


def payment_webhook(request):
    # Adapter must raise CreditError for invalid/unverified payloads.
    event = provider('payment').verify_webhook(request)
    return _complete_payment(event)


@wallet_transaction
def _complete_payment(event):
    order = CreditPurchase.objects.get(reference=event['order_reference'])
    if event['status'] != 'paid' or event['amount_minor'] != order.amount_minor or event['currency'] != order.currency:
        raise CreditError('Giao dịch chưa được xác nhận đúng giá trị.')
    changed = CreditPurchase.objects.filter(pk=order.pk, paid=False).update(paid=True)
    if changed:
        wallet = ensure_wallet(order.user)
        CreditWallet.objects.filter(pk=wallet.pk).update(balance=F('balance') + order.points)
        _entry(wallet, order.points, f'purchase:{order.reference}', 'Mua tín dụng')


def reward_webhook(request):
    event = provider('reward').verify_webhook(request)
    return _complete_reward(event)


@wallet_transaction
def _complete_reward(event):
    points = settings.CREDIT_REWARD_POINTS
    period_type = settings.CREDIT_REWARD_PERIOD
    if points <= 0 or period_type not in ('daily', 'lifetime'):
        raise CreditError('Chương trình thưởng chưa được cấu hình.')
    if event['status'] != 'completed' or not event.get('event_id') or len(event['event_id']) > 180:
        raise CreditError('Quảng cáo chưa được xác nhận hoàn tất.')
    wallet = CreditWallet.objects.get(user_id=event['user_id'])
    CreditWallet.objects.filter(pk=wallet.pk).update(balance=F('balance'))
    existing = RewardClaim.objects.filter(event_id=event['event_id']).first()
    if existing:
        if existing.wallet_id != wallet.pk:
            raise CreditError('Sự kiện thưởng không đúng tài khoản.')
        return
    wallet.refresh_from_db()
    if wallet.bonus_blocked or not wallet.user.is_active:
        raise CreditError('Tài khoản đang bị khóa nhận bonus.')
    period = timezone.now().astimezone(ZoneInfo('Asia/Ho_Chi_Minh')).date().isoformat() if period_type == 'daily' else 'lifetime'
    if RewardClaim.objects.filter(wallet=wallet, period=period).count() >= min(3, settings.CREDIT_REWARD_LIMIT):
        raise CreditError('Đã đạt giới hạn lượt nhận thưởng.')
    claim = RewardClaim.objects.create(wallet=wallet, event_id=event['event_id'], period=period)
    CreditWallet.objects.filter(pk=wallet.pk).update(balance=F('balance') + points)
    _entry(wallet, points, f'reward:{claim.pk}', 'Thưởng hoàn tất quảng cáo')
