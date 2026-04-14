from django.urls import path
from . import views

app_name = 'grading'

urlpatterns = [
    path('upload/', views.upload_view, name='upload'),
    path('exams/', views.exams_view, name='exams'),
    path('exams/new/', views.exam_create_view, name='exam_create'),
    path('exams/<int:exam_id>/edit/', views.exam_edit_view, name='exam_edit'),
    path('exams/<int:exam_id>/delete/', views.exam_delete_view, name='exam_delete'),
    path('exams/import/', views.exam_import_view, name='exam_import'),
    path('api/parse-excel/', views.parse_excel_api, name='parse_excel'),
    path('api/parse-image/', views.parse_image_api, name='parse_image'),
    path('results/<int:exam_id>/', views.results_view, name='results'),
    path('api/submission/<int:submission_id>/status/', views.submission_status_api, name='submission_status'),
    path('submission/<int:submission_id>/', views.submission_detail_view, name='submission_detail'),
    path('submission/<int:submission_id>/regrade/', views.submission_regrade_view, name='submission_regrade'),
]
