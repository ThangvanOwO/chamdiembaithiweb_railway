import uuid
from datetime import timedelta

from django import forms
from django.contrib import admin, messages
from django.contrib.auth.models import User
from django.core.exceptions import PermissionDenied
from django.core.paginator import Paginator
from django.db.models import Count, Sum, Q
from django.db.models.functions import TruncDate
from django.shortcuts import get_object_or_404, redirect
from django.template.response import TemplateResponse
from django.utils import timezone

from .credits import CreditError
from .models import AccountNetwork, AccountRisk, CreditWallet, ModerationEvent
from .risk import moderate, welcome_remaining


class ReviewForm(forms.Form):
    user = forms.IntegerField(widget=forms.HiddenInput)
    reference = forms.UUIDField(widget=forms.HiddenInput, initial=uuid.uuid4)
    action = forms.ChoiceField(label='Thao tác', choices=[('block_bonus', 'Khóa nhận bonus'),
        ('revoke', 'Thu hồi bonus chào mừng còn lại + khóa bonus'), ('lock', 'Khóa tài khoản'),
        ('unblock_bonus', 'Mở nhận bonus'), ('unlock', 'Mở tài khoản')])
    reason = forms.CharField(label='Lý do / kết quả kiểm tra', max_length=255, widget=forms.Textarea(attrs={'rows': 3}))
    confirm = forms.BooleanField(label='Tôi đã kiểm tra bằng chứng và xác nhận thao tác này')


def dashboard(request):
    if not request.user.is_superuser:
        raise PermissionDenied
    cases = AccountRisk.objects.select_related('user_a', 'user_b').order_by('-score', '-updated_at')
    status = request.GET.get('status', '')
    level = request.GET.get('level', '')
    query = request.GET.get('q', '').strip()[:150]
    if status in dict(AccountRisk._meta.get_field('status').choices):
        cases = cases.filter(status=status)
    if level == 'high':
        cases = cases.filter(score__gte=80)
    elif level == 'medium':
        cases = cases.filter(score__gte=40, score__lt=80)
    elif level == 'low':
        cases = cases.filter(score__lt=40)
    if query:
        cases = cases.filter(Q(user_a__email__icontains=query) | Q(user_b__email__icontains=query))
    today = timezone.localdate()
    dates = dict(User.objects.filter(date_joined__date__gte=today-timedelta(days=13))
                 .annotate(day=TruncDate('date_joined')).values('day').annotate(n=Count('id')).values_list('day', 'n'))
    peak = max(dates.values(), default=1) or 1
    chart = [{'label': (today-timedelta(days=i)).strftime('%d/%m'),
              'count': dates.get(today-timedelta(days=i), 0),
              'height': round(100*dates.get(today-timedelta(days=i), 0)/peak)} for i in reversed(range(14))]
    all_cases = AccountRisk.objects.all()
    counts = [('Theo dõi', all_cases.filter(score__lt=40).count()),
              ('Nghi vấn', all_cases.filter(score__gte=40, score__lt=80).count()),
              ('Rủi ro cao', all_cases.filter(score__gte=80).count())]
    total = sum(x[1] for x in counts) or 1
    context = {**admin.site.each_context(request), 'title': 'Trung tâm quản trị',
        'users': User.objects.count(), 'locked': User.objects.filter(is_active=False).count(),
        'credits': CreditWallet.objects.aggregate(n=Sum('balance'))['n'] or 0,
        'pending': all_cases.filter(status__in=['new', 'review']).count(),
        'observed': AccountNetwork.objects.values('user_id').distinct().count(),
        'chart': chart, 'distribution': [{'label': k, 'count': n, 'width': round(n/total*100)} for k, n in counts],
        'page': Paginator(cases, 20).get_page(request.GET.get('page')), 'q': query, 'level': level, 'status': status,
        'events': ModerationEvent.objects.select_related('actor', 'user').order_by('-id')[:10]}
    return TemplateResponse(request, 'admin/risk_dashboard.html', context)


def detail(request, case_id):
    if not request.user.is_superuser:
        raise PermissionDenied
    case = get_object_or_404(AccountRisk.objects.select_related('user_a', 'user_b'), pk=case_id)
    form = ReviewForm(request.POST or None)
    if request.method == 'POST':
        if request.POST.get('decision') in ('review', 'dismissed', 'confirmed'):
            reason = request.POST.get('reason', '').strip()
            if not reason or len(reason) > 255:
                messages.error(request, 'Cần ghi lý do (tối đa 255 ký tự).')
            else:
                from django.db import transaction
                with transaction.atomic():
                    old = case.status
                    case.status = request.POST['decision']
                    case.save(update_fields=['status', 'updated_at'])
                    ModerationEvent.objects.create(user=case.user_a, actor=request.user, action='review',
                        reference=uuid.uuid4(), reason=reason,
                        details={'case': case.pk, 'before': old, 'after': case.status})
                return redirect('risk_detail', case_id=case.pk)
        elif form.is_valid():
            data = form.cleaned_data
            if data['user'] not in (case.user_a_id, case.user_b_id):
                raise PermissionDenied
            try:
                moderate(request.user, data['user'], data['action'], data['reason'], data['reference'])
                messages.success(request, 'Đã xử lý và ghi lịch sử quản trị.')
                return redirect('risk_detail', case_id=case.pk)
            except CreditError as exc:
                form.add_error(None, str(exc))
    people = []
    for user in (case.user_a, case.user_b):
        wallet = user.credit_wallet
        people.append({'user': user, 'wallet': wallet, 'remaining': welcome_remaining(wallet),
                       'form': ReviewForm(initial={'user': user.pk}, auto_id=f'id_{user.pk}_%s')})
    context = {**admin.site.each_context(request), 'title': f'Hồ sơ nghi vấn #{case.pk}',
        'case': case, 'people': people, 'errors': form.errors if request.method == 'POST' else None,
        'events': ModerationEvent.objects.filter(user__in=[case.user_a, case.user_b]).select_related('actor', 'user').order_by('-id')[:30]}
    return TemplateResponse(request, 'admin/risk_detail.html', context)
