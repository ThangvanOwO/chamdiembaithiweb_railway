from django.contrib import admin
from .models import Exam, Submission


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
