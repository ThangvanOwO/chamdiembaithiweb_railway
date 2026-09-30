from django.contrib import admin
from .models import Exam, Submission, TrainingSample, TrainingCorrection, UserSettings
from django.utils.html import format_html
from django.utils import timezone
from grading.training_data import validate_labels


@admin.register(TrainingCorrection)
class TrainingCorrectionAdmin(admin.ModelAdmin):
    list_display = ('id', 'part', 'question', 'subquestion', 'detected', 'answer', 'status', 'created_at')
    list_filter = ('status', 'part', 'template_code', 'created_at')
    readonly_fields = ('image_preview', 'teacher', 'source_hash', 'template_code', 'part', 'question',
                       'subquestion', 'detected', 'answer', 'cells', 'labels', 'geometry', 'status',
                       'reviewed_by', 'reviewed_at', 'created_at')
    exclude = ('image',)
    actions = ('approve_labels', 'reject_labels')

    def has_module_permission(self, request):
        return request.user.is_superuser

    def has_view_permission(self, request, obj=None):
        return request.user.is_superuser

    def has_change_permission(self, request, obj=None):
        return request.user.is_superuser

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    @admin.display(description='Ảnh gốc của câu')
    def image_preview(self, obj):
        if not obj.image:
            return 'Chưa có ảnh'
        return format_html('<img src="{}" style="max-width:600px;max-height:500px" />', obj.image.url)

    @admin.action(description='Đã đối chiếu ảnh: duyệt nhãn các câu được chọn')
    def approve_labels(self, request, queryset):
        for sample in queryset:
            validate_labels(sample.cells, sample.labels)
            if sample.geometry.get('aligned') is not True or not sample.image.storage.exists(sample.image.name):
                self.message_user(request, f'Mẫu #{sample.pk} chưa khớp lưới hoặc thiếu ảnh.', level='error')
                return
        queryset.update(status='approved', reviewed_by=request.user, reviewed_at=timezone.now())

    @admin.action(description='Loại các mẫu ảnh/nhãn không phù hợp')
    def reject_labels(self, request, queryset):
        queryset.update(status='rejected', reviewed_by=request.user, reviewed_at=timezone.now())


@admin.register(UserSettings)
class UserSettingsAdmin(admin.ModelAdmin):
    list_display = ('user', 'temp_retention_days', 'contribute_training_data', 'updated_at')
    list_filter = ('contribute_training_data', 'temp_retention_days')
    search_fields = ('user__username', 'user__email')


@admin.register(TrainingSample)
class TrainingSampleAdmin(admin.ModelAdmin):
    list_display = ('id', 'teacher', 'made', 'sbd', 'template_code', 'label_status', 'uploaded_at')
    list_filter = ('template_code', 'uploaded_at')
    search_fields = ('teacher__username', 'made', 'sbd')
    readonly_fields = ('uploaded_at',)

    @admin.display(description='Nguồn nhãn')
    def label_status(self, obj):
        return 'Máy tự đọc · chưa được xác minh'


@admin.register(Exam)
class ExamAdmin(admin.ModelAdmin):
    list_display = ('title', 'subject', 'num_questions', 'teacher', 'submission_count', 'created_at')
    list_filter = ('subject', 'created_at')
    search_fields = ('title', 'subject')


@admin.register(Submission)
class SubmissionAdmin(admin.ModelAdmin):
    list_display = ('student_name', 'exam', 'status', 'score', 'correct_count', 'uploaded_at')
    list_filter = ('status', 'exam', 'uploaded_at')
    search_fields = ('student_name', 'student_id')
    readonly_fields = ('score', 'correct_count', 'answers_detected', 'detail_json', 'graded_at', 'processing_time')
