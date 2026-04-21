"""
API v1 URL Configuration — Mobile App Backend
"""
from django.urls import path
from . import views

app_name = 'api'

urlpatterns = [
    # Auth
    path('v1/auth/register/', views.register_api, name='register'),
    path('v1/auth/login/', views.login_api, name='login'),
    path('v1/auth/logout/', views.logout_api, name='logout'),
    path('v1/auth/me/', views.me_api, name='me'),

    # Dashboard
    path('v1/dashboard/', views.dashboard_api, name='dashboard'),

    # Exams
    path('v1/exams/', views.exams_list_api, name='exams_list'),
    path('v1/exams/<int:exam_id>/', views.exam_detail_api, name='exam_detail'),
    path('v1/exams/<int:exam_id>/delete/', views.exam_delete_api, name='exam_delete'),

    # Parse files — for exam import
    path('v1/parse-excel/', views.parse_excel_api, name='parse_excel'),
    path('v1/parse-image/', views.parse_image_api, name='parse_image'),

    # Grading — core endpoint for mobile
    path('v1/grade/', views.grade_api, name='grade'),

    # Submissions
    path('v1/submissions/', views.submissions_list_api, name='submissions_list'),
    path('v1/submissions/<int:submission_id>/', views.submission_detail_api, name='submission_detail'),
]
