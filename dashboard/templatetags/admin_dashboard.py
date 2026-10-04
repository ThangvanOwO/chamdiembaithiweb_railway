from datetime import timedelta

from django import template
from django.contrib.auth import get_user_model
from django.db.models import Count, Q
from django.utils import timezone

from dashboard.models import Announcement, PushDevice
from grading.models import Submission, TrainingCorrection

register = template.Library()


@register.simple_tag(takes_context=True)
def admin_overview(context):
    """Only the system owner sees aggregate data across accounts."""
    if not context['request'].user.is_superuser:
        return None
    since = timezone.now() - timedelta(days=14)
    users = get_user_model().objects.aggregate(
        total=Count('pk'), recent=Count('pk', filter=Q(date_joined__gte=since)))
    devices = PushDevice.objects.filter(active=True, user__is_active=True).aggregate(
        total=Count('pk'), users=Count('user', distinct=True))
    return {
        'users': users['total'], 'new_users': users['recent'],
        'devices': devices['total'], 'device_users': devices['users'],
        'submissions': Submission.objects.filter(uploaded_at__gte=since).count(),
        'training_pending': TrainingCorrection.objects.filter(status='pending').count(),
        'notice_drafts': Announcement.objects.filter(status='draft').count(),
    }


@register.filter
def admin_model_label(model):
    return {
        'PushDevice': 'Thiết bị nhận thông báo',
        'User': 'Người dùng', 'Group': 'Nhóm quyền',
        'CreditWallet': 'Ví tín dụng', 'CreditEntry': 'Lịch sử tín dụng',
        'ScanOperation': 'Giao dịch lượt quét', 'ModerationEvent': 'Nhật ký quản trị',
        'UserSettings': 'Cài đặt người dùng', 'SocialAccount': 'Tài khoản liên kết',
        'TrainingSample': 'Mẫu phiếu huấn luyện',
        'SocialApp': 'Cấu hình đăng nhập mạng xã hội', 'SocialToken': 'Mã xác thực mạng xã hội',
        'TokenProxy': 'Mã xác thực ứng dụng',
    }.get(model['object_name'], model['name'])


@register.filter
def admin_app_label(app):
    return {
        'accounts': 'Tài khoản & tín dụng', 'auth': 'Người dùng & phân quyền',
        'grading': 'Chấm bài & huấn luyện', 'dashboard': 'Thông báo & thiết bị',
        'socialaccount': 'Đăng nhập mạng xã hội', 'authtoken': 'Xác thực ứng dụng',
    }.get(app['app_label'], app['name'])
