from django.contrib import admin
from django.utils.html import format_html
from .models import Classroom, Student, ExamRosterEntry, SubmissionReview, SupportTicket


class StudentInline(admin.TabularInline):
    model = Student
    extra = 0


class SuperuserToolsAdmin(admin.ModelAdmin):
    def has_module_permission(self, request):
        return request.user.is_superuser

    def has_view_permission(self, request, obj=None):
        return request.user.is_superuser

    def has_change_permission(self, request, obj=None):
        return request.user.is_superuser

    def has_delete_permission(self, request, obj=None):
        return request.user.is_superuser

    def has_add_permission(self, request):
        return request.user.is_superuser


@admin.register(Classroom)
class ClassroomAdmin(SuperuserToolsAdmin):
    list_display = ['name', 'school_year', 'owner', 'archived']
    list_filter = ['archived', 'school_year']
    search_fields = ['name', 'owner__username']
    inlines = [StudentInline]


@admin.register(SupportTicket)
class SupportTicketAdmin(SuperuserToolsAdmin):
    list_display = ['id', 'owner', 'status', 'created_at']
    list_filter = ['status', 'created_at']
    search_fields = ['message', 'owner__username']
    readonly_fields = ['owner', 'message', 'technical', 'attachment', 'created_at', 'updated_at']
    fields = ['owner', 'message', 'technical', 'attachment', 'status', 'admin_note', 'created_at', 'updated_at']

    def attachment(self, obj):
        return format_html('<a href="/api/v1/support/{}/image/" target="_blank">Xem ảnh đính kèm</a>', obj.pk) if obj.image else 'Không có ảnh'

    def has_add_permission(self, request):
        return False
