from django.contrib import admin
from django.utils import timezone
from django.utils.formats import date_format
from .models import Announcement, PushDevice
from .announcements import publish_announcement


@admin.register(Announcement)
class AnnouncementAdmin(admin.ModelAdmin):
    list_display = ['title', 'kind', 'status', 'push_enabled', 'event_starts_at', 'published_at']
    list_filter = ['status', 'kind']
    search_fields = ['title', 'body']
    actions = ['publish', 'archive']
    fieldsets = [
        ('Nội dung thông báo', {'fields': ['title', 'body', 'kind']}),
        ('Lịch sự kiện', {'fields': ['event_starts_at', 'event_ends_at'],
                         'description': 'Chỉ cần điền khi chọn loại Sự kiện. Thời gian theo múi giờ hệ thống.'}),
        ('Gửi & thời hạn', {'fields': ['push_enabled', 'expires_at']}),
        ('Thông tin quản lý', {'fields': ['status', 'published_at', 'author', 'created_at'], 'classes': ['collapse']}),
    ]

    def has_module_permission(self, request):
        return request.user.is_superuser

    def has_view_permission(self, request, obj=None):
        return request.user.is_superuser

    has_add_permission = has_view_permission
    has_change_permission = has_view_permission
    has_delete_permission = has_view_permission

    def get_readonly_fields(self, request, obj=None):
        fields = ['status', 'published_at', 'created_at', 'author']
        return fields + (['title', 'body', 'kind', 'push_enabled', 'expires_at', 'event_starts_at', 'event_ends_at'] if obj and obj.status != 'draft' else [])

    def save_model(self, request, obj, form, change):
        if not change:
            obj.author = request.user
        super().save_model(request, obj, form, change)

    @admin.action(description='Gửi thông báo đã chọn đến người dùng')
    def publish(self, request, queryset):
        for notice in queryset.filter(status='draft'):
            try:
                publish_announcement(notice.pk)
            except ValueError as exc:
                self.message_user(request, str(exc), level='ERROR')

    @admin.action(description='Thu hồi khỏi hộp thông báo trong ứng dụng')
    def archive(self, request, queryset):
        queryset.update(status='archived')


class RegistrationStateFilter(admin.BooleanFieldListFilter):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.title = 'Đăng ký thông báo'


class DeviceAccountStateFilter(admin.BooleanFieldListFilter):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.title = 'Tài khoản hoạt động'


class RegistrationDateFilter(admin.DateFieldListFilter):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.title = 'Cập nhật đăng ký'


@admin.register(PushDevice)
class PushDeviceAdmin(admin.ModelAdmin):
    """Inspect existing notification registrations without exposing credentials."""
    change_list_template = 'admin/dashboard/pushdevice/change_list.html'
    list_display = ['account', 'installation', 'notification_status', 'registration_updated']
    list_filter = [('active', RegistrationStateFilter), ('user__is_active', DeviceAccountStateFilter), ('updated_at', RegistrationDateFilter)]
    search_fields = ['user__username', 'user__email', 'user__first_name', 'user__last_name']
    list_select_related = ['user']
    ordering = ['-updated_at']
    fields = readonly_fields = ['account', 'installation', 'notification_status', 'registration_updated']
    actions = None

    def has_module_permission(self, request):
        return request.user.is_superuser

    def has_view_permission(self, request, obj=None):
        return request.user.is_active and request.user.is_superuser

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    @admin.display(description='Tài khoản', ordering='user__username')
    def account(self, obj):
        return obj.user.email or obj.user.username

    @admin.display(description='Mã cài đặt', ordering='installation_id')
    def installation(self, obj):
        return obj.installation_id

    @admin.display(description='Cập nhật đăng ký', ordering='updated_at')
    def registration_updated(self, obj):
        return date_format(timezone.localtime(obj.updated_at), 'd/m/Y H:i')

    @admin.display(description='Nhận thông báo')
    def notification_status(self, obj):
        return 'Đã đăng ký' if obj.active and obj.user.is_active else 'Đã ngừng / tài khoản đã khóa'

    def changelist_view(self, request, extra_context=None):
        return super().changelist_view(request, extra_context={
            **(extra_context or {}), 'title': 'Thiết bị nhận thông báo'})
