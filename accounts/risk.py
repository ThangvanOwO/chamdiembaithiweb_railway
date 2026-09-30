"""Review signals, never an automatic verdict. No raw client IP is persisted."""
import json
import logging
from contextvars import ContextVar
from datetime import timedelta

from django.contrib.auth.models import User
from django.db import DatabaseError
from django.db.models import F
from django.utils import timezone
from django.utils.crypto import salted_hmac

from .credits import CreditError, ensure_wallet, wallet_transaction, _entry
from .models import AccountNetwork, AccountRisk, CreditEntry, CreditWallet, ModerationEvent, ScanOperation

current_request = ContextVar('risk_request', default=None)
logger = logging.getLogger(__name__)


def observe(user, request):
    from .security import client_ip
    ip = client_ip(request)
    if ip == 'unknown' or not user.pk or user.is_staff:
        return False
    network = salted_hmac('gradeflow.network.v1', ip, algorithm='sha256').hexdigest()
    now = timezone.now()
    recent = AccountNetwork.objects.filter(user=user, network=network, last_seen__gt=now-timedelta(minutes=15))
    if recent.exists():
        return False
    AccountNetwork.objects.update_or_create(user=user, network=network, defaults={'last_seen': now})
    AccountNetwork.objects.filter(last_seen__lt=now-timedelta(days=30)).delete()
    return True


def answer_digest(raw):
    try:
        data = json.loads(raw)
    except (ValueError, TypeError):
        data = [x.strip().upper() for x in (raw or '').split(',') if x.strip()]
    if isinstance(data, dict):
        data = {k: data[k] for k in ('p1', 'p2', 'p3') if k in data}
    def leaves(value):
        if isinstance(value, dict):
            return sum(leaves(v) for v in value.values())
        if isinstance(value, list):
            return sum(leaves(v) for v in value)
        return int(value is not None and str(value).strip() != '')
    if leaves(data) < 10:
        return None
    text = json.dumps(data, sort_keys=True, ensure_ascii=False, separators=(',', ':'))
    return salted_hmac('gradeflow.answers.v1', text, algorithm='sha256').hexdigest()


def exam_keys(user_id, since):
    from grading.models import Exam
    keys = []
    for exam in Exam.objects.filter(teacher_id=user_id, created_at__gte=since).prefetch_related('variants'):
        for raw in [exam.answer_key] + [v.answers_json for v in exam.variants.all()]:
            digest = answer_digest(raw)
            if digest:
                keys.append((digest, exam.pk, exam.created_at))
    return keys


def assess(user):
    since = timezone.now()-timedelta(days=30)
    networks = AccountNetwork.objects.filter(user=user, last_seen__gte=since).values('network')
    peers = User.objects.filter(accountnetwork__network__in=networks,
        accountnetwork__last_seen__gte=since, is_staff=False).exclude(pk=user.pk).distinct()
    peers = list(peers)
    if not peers:
        return
    own_keys = exam_keys(user.pk, since)
    for peer in peers:
        a, b = sorted((user.pk, peer.pk))
        minutes = round(abs((user.date_joined-peer.date_joined).total_seconds())/60, 1)
        matching = []
        peer_keys = exam_keys(peer.pk, since)
        for left in own_keys:
            for right in peer_keys:
                if left[0] == right[0]:
                    matching.append({'exam_a': left[1], 'exam_b': right[1],
                        'minutes': round(abs((left[2]-right[2]).total_seconds())/60, 1)})
        close = any(m['minutes'] <= 10 for m in matching)
        score = 20 + (20 if minutes <= 60 else 0) + (30 if matching else 0) + (30 if close else 0)
        evidence = {'shared_network': True, 'signup_gap_minutes': minutes,
                    'matching_exams': matching[:20], 'close_exam_creation': close,
                    'window_days': 30, 'evaluated_at': timezone.now().isoformat()}
        case, created = AccountRisk.objects.get_or_create(user_a_id=a, user_b_id=b,
            defaults={'score': score, 'evidence': evidence})
        if not created:
            # Keep the review decision; new evidence is visible without undoing admin decisions.
            case.score, case.evidence = score, evidence
            case.save(update_fields=['score', 'evidence', 'updated_at'])


def welcome_remaining(wallet):
    """Conservative welcome-first consumption. Positive purchases never become welcome money."""
    remaining = 0
    allocations = {}
    for row in wallet.entries.order_by('id'):
        if row.reference == f'welcome:{wallet.user_id}':
            remaining += min(100, max(0, row.amount))
        elif row.amount < 0:
            used = min(remaining, -row.amount)
            remaining -= used
            if row.reference.startswith('scan:') and row.reference.endswith(':reserve'):
                allocations[row.reference.rsplit(':', 1)[0]] = (used, -row.amount)
        elif row.reference.startswith('scan:') and row.reference.endswith(':refund'):
            used, reserved = allocations.get(row.reference.rsplit(':', 1)[0], (0, 0))
            remaining += max(0, used - max(0, reserved-row.amount))
    return min(remaining, wallet.balance, 100)


@wallet_transaction
def moderate(actor, user_id, action, reason, reference):
    if not actor.is_active or not actor.is_superuser:
        raise CreditError('Chỉ quản trị viên cao nhất được xử lý tài khoản.')
    if action not in ('revoke', 'block_bonus', 'unblock_bonus', 'lock', 'unlock') or not reason.strip() or len(reason) > 255:
        raise CreditError('Cần chọn thao tác và ghi lý do hợp lệ.')
    user = User.objects.get(pk=user_id)
    if user.is_staff or user.is_superuser or user.pk == actor.pk:
        raise CreditError('Không xử lý tài khoản quản trị qua màn hình này.')
    wallet = ensure_wallet(user)
    CreditWallet.objects.filter(pk=wallet.pk).update(balance=F('balance'))
    wallet.refresh_from_db()
    previous = ModerationEvent.objects.filter(reference=reference).first()
    if previous:
        if previous.user_id != user.pk or previous.action != action or previous.actor_id != actor.pk or previous.reason != reason.strip():
            raise CreditError('Mã thao tác đã được sử dụng.')
        return previous
    details = {'balance_before': wallet.balance, 'active_before': user.is_active,
               'bonus_blocked_before': wallet.bonus_blocked}
    if action == 'revoke':
        if ScanOperation.objects.filter(wallet=wallet, finished=False).exists():
            raise CreditError('Có lượt quét đang giữ điểm. Đợi lượt quét hoàn tất trước khi thu hồi.')
        if CreditEntry.objects.filter(reference=f'revoke-welcome:{user.pk}').exists():
            raise CreditError('Bonus chào mừng đã được xử lý thu hồi trước đó.')
        amount = welcome_remaining(wallet)
        CreditWallet.objects.filter(pk=wallet.pk).update(balance=F('balance')-amount, bonus_blocked=True)
        _entry(wallet, -amount, f'revoke-welcome:{user.pk}', 'Thu hồi bonus: '+reason.strip()[:230], actor)
        details['revoked'] = amount
    elif action in ('block_bonus', 'unblock_bonus'):
        CreditWallet.objects.filter(pk=wallet.pk).update(bonus_blocked=action == 'block_bonus')
    else:
        User.objects.filter(pk=user.pk).update(is_active=action == 'unlock')
        if action == 'lock':
            from rest_framework.authtoken.models import Token
            Token.objects.filter(user=user).delete()
    wallet.refresh_from_db()
    user.refresh_from_db()
    details.update(balance_after=wallet.balance, active_after=user.is_active, bonus_blocked_after=wallet.bonus_blocked)
    return ModerationEvent.objects.create(user=user, actor=actor, action=action, reason=reason.strip(), reference=reference, details=details)


class RiskMonitoringMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        token = current_request.set(request)
        request.risk_users = set()
        try:
            response = self.get_response(request)
            if response.status_code < 400:
                user = getattr(request, 'user', None)
                if user and user.is_authenticated and not user.is_staff:
                    request.risk_users.add(user.pk)
                try:
                    for user in User.objects.filter(pk__in=request.risk_users, is_staff=False):
                        changed = observe(user, request)
                        if changed or request.method in ('POST', 'PUT', 'PATCH', 'DELETE'):
                            assess(user)
                except DatabaseError:
                    logger.exception('Account risk monitoring unavailable')
            return response
        finally:
            current_request.reset(token)
