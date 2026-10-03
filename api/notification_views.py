import uuid
from django.db import transaction
from django.db.models import Count
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import serializers
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import BasePermission
from rest_framework.response import Response

from dashboard.announcements import digest, firebase_status, publish_announcement, visible_announcements
from dashboard.models import Announcement, AnnouncementRead, PushDevice


class NotificationAdmin(BasePermission):
    def has_permission(self, request, view):
        return bool(request.user.is_authenticated and request.user.is_superuser)


class AnnouncementInput(serializers.ModelSerializer):
    title = serializers.CharField(max_length=120, trim_whitespace=True)
    body = serializers.CharField(max_length=4000, trim_whitespace=True)
    class Meta:
        model = Announcement
        fields = ['title', 'body', 'kind', 'push_enabled', 'expires_at']

    def validate_expires_at(self, value):
        if value and value <= timezone.now():
            raise serializers.ValidationError('Ngày hết hạn phải ở trong tương lai.')
        return value


def serialize_notice(notice, read=False, admin=False):
    data = {'id': notice.pk, 'title': notice.title, 'body': notice.body, 'kind': notice.kind,
            'published_at': notice.published_at, 'expires_at': notice.expires_at, 'is_read': read}
    if admin:
        data.update(status=notice.status, push_enabled=notice.push_enabled,
                    deliveries={item['state']: item['total'] for item in
                                notice.pushdelivery_set.values('state').annotate(total=Count('id'))})
    return data


@api_view(['GET', 'POST'])
def inbox_api(request):
    read_ids = set(AnnouncementRead.objects.filter(user=request.user).values_list('announcement_id', flat=True))
    notices = visible_announcements()
    if request.method == 'POST':
        AnnouncementRead.objects.bulk_create([
            AnnouncementRead(announcement_id=pk, user=request.user)
            for pk in notices.exclude(pk__in=read_ids).values_list('pk', flat=True)
        ], ignore_conflicts=True)
        return Response({'ok': True})
    return Response({'items': [serialize_notice(n, n.pk in read_ids) for n in notices[:100]],
                     'unread_count': notices.exclude(pk__in=read_ids).count()})


@api_view(['POST'])
def read_api(request, notice_id):
    notice = get_object_or_404(visible_announcements(), pk=notice_id)
    AnnouncementRead.objects.get_or_create(announcement=notice, user=request.user)
    return Response({'ok': True})


@api_view(['POST', 'DELETE'])
def device_api(request):
    try:
        installation_id = uuid.UUID(str(request.data.get('installation_id', '')))
    except (ValueError, TypeError, AttributeError):
        return Response({'message': 'Mã thiết bị không hợp lệ.'}, status=400)
    if request.method == 'DELETE':
        PushDevice.objects.filter(installation_id=installation_id, user=request.user).update(active=False)
        return Response({'ok': True})
    token = request.data.get('token')
    if not isinstance(token, str) or not 20 <= len(token) <= 4096 or any(c.isspace() for c in token):
        return Response({'message': 'Mã thông báo thiết bị không hợp lệ.'}, status=400)
    if not request.auth or not getattr(request.auth, 'key', None):
        return Response({'message': 'Vui lòng đăng nhập trong ứng dụng.'}, status=400)
    with transaction.atomic():
        # A refreshed FCM token belongs to only one installation/account at a time.
        PushDevice.objects.filter(token=token).exclude(installation_id=installation_id).delete()
        PushDevice.objects.update_or_create(installation_id=installation_id, defaults={
            'token': token, 'user': request.user, 'session_hash': digest(request.auth.key), 'active': True})
    return Response({'ok': True})


@api_view(['GET', 'POST'])
@permission_classes([NotificationAdmin])
def admin_list_api(request):
    if request.method == 'POST':
        form = AnnouncementInput(data=request.data)
        form.is_valid(raise_exception=True)
        notice = form.save(author=request.user)
        return Response(serialize_notice(notice, admin=True), status=201)
    return Response({'items': [serialize_notice(n, admin=True) for n in Announcement.objects.order_by('-id')[:100]],
                     'push_configured': firebase_status(),
                     'active_devices': PushDevice.objects.filter(active=True).count()})


@api_view(['PATCH', 'DELETE'])
@permission_classes([NotificationAdmin])
def admin_detail_api(request, notice_id):
    with transaction.atomic():
        notice = get_object_or_404(Announcement.objects.select_for_update(), pk=notice_id)
        if request.method == 'DELETE':
            notice.status = 'archived'
            notice.save(update_fields=['status'])
            notice.pushdelivery_set.filter(state='pending').update(state='skipped', error_code='archived')
            return Response({'ok': True})
        if notice.status != 'draft':
            return Response({'message': 'Chỉ sửa được bản nháp. Hãy tạo thông báo mới nếu cần điều chỉnh.'}, status=409)
        form = AnnouncementInput(notice, data=request.data, partial=True)
        form.is_valid(raise_exception=True)
        return Response(serialize_notice(form.save(), admin=True))


@api_view(['POST'])
@permission_classes([NotificationAdmin])
def publish_api(request, notice_id):
    get_object_or_404(Announcement, pk=notice_id)
    try:
        notice = publish_announcement(notice_id)
    except ValueError as exc:
        return Response({'message': str(exc)}, status=400)
    return Response(serialize_notice(notice, admin=True))
