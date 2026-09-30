"""Short atomic wallet transactions; never hold a DB transaction during OMR."""
import time
from functools import wraps

from django.db import OperationalError, transaction
from django.db.models import F

from .models import CreditEntry, CreditWallet, ScanOperation


class CreditError(Exception):
    pass


class InsufficientCredits(CreditError):
    pass


def wallet_transaction(function):
    @wraps(function)
    def wrapped(*args, **kwargs):
        for attempt in range(6):
            try:
                with transaction.atomic():
                    return function(*args, **kwargs)
            except OperationalError as exc:
                if 'locked' not in str(exc).lower() or attempt == 5:
                    raise
                time.sleep(0.02 * (attempt + 1))
    return wrapped


@wallet_transaction
def ensure_wallet(user):
    wallet, created = CreditWallet.objects.get_or_create(user=user)
    if created:
        CreditEntry.objects.create(wallet=wallet, amount=100, balance_after=100,
                                   reference=f'welcome:{user.pk}', reason='100 điểm chào mừng')
    return wallet


def _entry(wallet, amount, reference, reason, actor=None):
    wallet.refresh_from_db(fields=['balance'])
    return CreditEntry.objects.create(wallet=wallet, amount=amount, balance_after=wallet.balance,
                                     reference=reference, reason=reason, actor=actor)


@wallet_transaction
def reserve_scan(user, key, fingerprint, count):
    if count < 1:
        raise ValueError('Invalid scan count')
    wallet = ensure_wallet(user)
    operation, created = ScanOperation.objects.get_or_create(
        wallet=wallet, key=key, defaults={'fingerprint': fingerprint, 'reserved': count})
    if not created:
        if operation.fingerprint != fingerprint:
            raise CreditError('Mã yêu cầu đã được dùng cho dữ liệu khác.')
        return operation, False
    updated = CreditWallet.objects.filter(pk=wallet.pk, balance__gte=count).update(balance=F('balance') - count)
    if not updated:
        raise InsufficientCredits('Không đủ tín dụng. Vui lòng vào mục Tín dụng để bổ sung điểm.')
    _entry(wallet, -count, f'scan:{operation.pk}:reserve', f'Tạm giữ {count} điểm để quét')
    return operation, True


@wallet_transaction
def finish_scan(operation, count, body, status, content_type, redirect_url=''):
    # Conditional update serializes competing settlement attempts, including SQLite.
    if not 0 <= count <= operation.reserved:
        raise ValueError('Invalid charged count')
    changed = ScanOperation.objects.filter(pk=operation.pk, finished=False).update(
        finished=True, charged=count, response_body=body, response_status=status,
        response_type=content_type, redirect_url=redirect_url)
    if not changed:
        return
    refund = operation.reserved - count
    if refund:
        CreditWallet.objects.filter(pk=operation.wallet_id).update(balance=F('balance') + refund)
        _entry(operation.wallet, refund, f'scan:{operation.pk}:refund', 'Hoàn điểm cho ảnh chưa chấm thành công')


@wallet_transaction
def adjust_credits(wallet_id, amount, reason, actor, reference):
    if not actor.is_active or not actor.is_staff or not actor.has_perm('accounts.change_creditwallet'):
        raise PermissionError('Không có quyền điều chỉnh tín dụng.')
    if not isinstance(amount, int) or not amount or not reason.strip():
        raise CreditError('Nhập số điểm khác 0 và lý do điều chỉnh.')
    # Lock the wallet before reading the idempotency record.
    CreditWallet.objects.filter(pk=wallet_id).update(balance=F('balance'))
    wallet = CreditWallet.objects.get(pk=wallet_id)
    existing = CreditEntry.objects.filter(reference=reference).first()
    if existing:
        if existing.wallet_id != wallet_id or existing.amount != amount or existing.reason != reason:
            raise CreditError('Mã giao dịch đã được dùng cho nội dung khác.')
        return existing
    if not CreditWallet.objects.filter(pk=wallet_id, balance__gte=max(0, -amount)).update(balance=F('balance') + amount):
        raise InsufficientCredits('Không thể điều chỉnh thành số dư âm.')
    return _entry(wallet, amount, reference, reason, actor)
