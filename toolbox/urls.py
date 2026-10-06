from django.urls import path
from . import views

urlpatterns = [
    path('classrooms/', views.classrooms),
    path('classrooms/<int:classroom_id>/', views.classroom_detail),
    path('classrooms/<int:classroom_id>/students/', views.students),
    path('classrooms/<int:classroom_id>/import/preview/', views.import_preview),
    path('classrooms/<int:classroom_id>/import/confirm/', views.import_confirm),
    path('students/<int:student_id>/', views.student_detail),
    path('exams/<int:exam_id>/roster/', views.exam_roster),
    path('exams/<int:exam_id>/report/', views.report),
    path('exams/<int:exam_id>/export/<str:file_format>/', views.export_report),
    path('submissions/<int:submission_id>/review/', views.review_submission),
    path('review-queue/', views.review_queue),
    path('templates/<str:code>/pdf/', views.template_pdf),
    path('support/', views.support_tickets),
    path('support/<int:ticket_id>/image/', views.ticket_image),
    path('admin/support/', views.admin_tickets),
    path('admin/support/<int:ticket_id>/', views.admin_ticket_detail),
]
