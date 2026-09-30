"""Mobile wallet read model; credit awards remain server controlled."""
from rest_framework.decorators import api_view, permission_classes, authentication_classes
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.response import Response

from accounts.credits import ensure_wallet, CreditError
from accounts.admob_rewards import create_ticket, read_ticket, reward_state, verify_probe
from accounts.credit_integrations import reward_webhook
from accounts.models import RewardClaim, CreditWallet
from accounts.security import take_limit


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def wallet_api(request):
    wallet = ensure_wallet(request.user)
    response = Response({
        'balance': wallet.balance,
        'scan_cost': 1,
        'reward': reward_state(wallet),
        'entries': [
            {'amount': entry.amount, 'balance_after': entry.balance_after,
             'reason': entry.reason, 'created_at': entry.created_at.isoformat()}
            for entry in wallet.entries.all()[:20]
        ],
    })
    response['Cache-Control'] = 'private, no-store'
    return response


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def reward_ticket_api(request):
    if not take_limit('reward-ticket', str(request.user.pk), 15, 3600):
        return Response({'error': 'Vui lòng thử lại sau.'}, status=429)
    try:
        return Response({'ticket': create_ticket(ensure_wallet(request.user))})
    except CreditError as exc:
        return Response({'error': str(exc)}, status=409)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def reward_status_api(request):
    try:
        ticket = read_ticket(request.data.get('ticket', ''), request.user.pk)
        claimed = RewardClaim.objects.filter(wallet__user=request.user,
                    event_id='admob:' + ticket['nonce']).exists()
        return Response({'claimed': claimed})
    except (CreditError, AttributeError) as exc:
        return Response({'error': 'Phiên nhận thưởng không hợp lệ.'}, status=400)


@api_view(['GET'])
@authentication_classes([])
@permission_classes([AllowAny])
def admob_callback(request):
    try:
        if verify_probe(request):
            # Google's URL verification must work before rewards are enabled.
            # Separate salt, no user binding, no ledger/wallet writes.
            return Response({'ok': True, 'verification_only': True})
        reward_webhook(request)
    except (CreditError, CreditWallet.DoesNotExist):
        return Response({'error': 'Không xác minh được phần thưởng.'}, status=400)
    # Network/key-service failures intentionally remain 5xx so Google retries.
    return Response({'ok': True})
