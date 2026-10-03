from django.contrib import admin
from .models import Announcement
from .announcements import publish_announcement


@admin.register(Announcement)
class AnnouncementAdmin(admin.ModelAdmin):
    list_display = ['title', 'kind', 'status', 'push_enabled', 'event_starts_at', 'published_at']
    list_filter = ['status', 'kind']
    search_fields = ['title', 'body']
    actions = ['publish', 'archive']

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
