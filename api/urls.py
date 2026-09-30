"""
API v1 URL Configuration — Mobile App Backend
"""
from django.urls import path, re_path
from . import views
from . import training_views
from .credit_views import wallet_api, reward_ticket_api, reward_status_api, admob_callback
from grading import chamtn_api

app_name = 'api'

urlpatterns = [
    # Auth
    path('v1/auth/register/', views.register_api, name='register'),
    path('v1/auth/login/', views.login_api, name='login'),
    path('v1/auth/logout/', views.logout_api, name='logout'),
    path('v1/auth/me/', views.me_api, name='me'),

    # Dashboard
    path('v1/dashboard/', views.dashboard_api, name='dashboard'),
    path('v1/credits/', wallet_api, name='credits'),
    path('v1/credits/reward-ticket/', reward_ticket_api, name='reward_ticket'),
    path('v1/credits/reward-status/', reward_status_api, name='reward_status'),
    path('v1/credits/admob-callback/', admob_callback, name='admob_callback'),

    # Exams
    path('v1/exams/', views.exams_list_api, name='exams_list'),
    path('v1/exams/<int:exam_id>/', views.exam_detail_api, name='exam_detail'),
    path('v1/exams/<int:exam_id>/delete/', views.exam_delete_api, name='exam_delete'),

    # Parse files — for exam import
    path('v1/parse-excel/', views.parse_excel_api, name='parse_excel'),
    path('v1/parse-image/', views.parse_image_api, name='parse_image'),

    # Templates — answer sheet formats
    path('v1/templates/', views.templates_list_api, name='templates_list'),
    path('v1/templates/<str:code>/image/<str:filename>', views.template_image_api, name='template_image'),

    # Grading — core endpoint for mobile
    path('v1/grade/', views.grade_api, name='grade'),

    # Submissions
    path('v1/submissions/', views.submissions_list_api, name='submissions_list'),
    path('v1/submissions/<int:submission_id>/', views.submission_detail_api, name='submission_detail'),

    # User settings
    path('v1/settings/', views.user_settings_api, name='user_settings'),
    path('v1/settings/cleanup-now/', views.cleanup_now_api, name='cleanup_now'),

    # Training data (Active Learning)
    path('v1/training/upload/', views.training_upload_api, name='training_upload'),
    path('v1/training/stats/', views.training_stats_api, name='training_stats'),
    path('v1/training/download/', views.training_download_api, name='training_download'),
    path('v1/training/corrections/preview/', training_views.preview_api, name='training_preview'),
    path('v1/training/corrections/save/', training_views.save_api, name='training_save'),
    path('v1/training/corrections/', training_views.list_api, name='training_corrections'),
    path('v1/training/corrections/<int:sample_id>/review/', training_views.review_api, name='training_review'),
    path('v1/training/corrections/export/', training_views.export_api, name='training_export'),

    # Admin
    path('v1/admin/users/', views.admin_users_api, name='admin_users'),

    # =========================================================================
    # ChamTN Web SPA REST APIs
    # =========================================================================
    re_path(r'^health/?$', chamtn_api.api_health, name='chamtn_health'),
    re_path(r'^login/?$', chamtn_api.api_login, name='chamtn_login'),
    re_path(r'^logout/?$', chamtn_api.api_logout, name='chamtn_logout'),
    re_path(r'^me/?$', chamtn_api.api_me, name='chamtn_me'),
    re_path(r'^dashboard/?$', chamtn_api.api_dashboard, name='chamtn_dashboard'),
    re_path(r'^templates/?$', chamtn_api.api_templates_list, name='chamtn_templates'),
    re_path(r'^templates/(?P<template_id>[\w\-_]+)/?$', chamtn_api.api_template_detail, name='chamtn_template_detail'),
    re_path(r'^exams/?$', chamtn_api.api_exams_collection, name='chamtn_exams'),
    re_path(r'^exams/(?P<exam_id>\d+)/?$', chamtn_api.api_exam_item, name='chamtn_exam_item'),
    re_path(r'^exams/(?P<exam_id>\d+)/key/?$', chamtn_api.api_exam_save_key, name='chamtn_exam_save_key'),
    re_path(r'^exams/(?P<exam_id>\d+)/grade/?$', chamtn_api.api_exam_grade_batch, name='chamtn_exam_grade'),
    re_path(r'^exams/(?P<exam_id>\d+)/sheets/?$', chamtn_api.api_exam_sheets_list, name='chamtn_exam_sheets'),
    re_path(r'^exams/(?P<exam_id>\d+)/export\.xlsx/?$', chamtn_api.api_exam_export_excel, name='chamtn_exam_export'),
    re_path(r'^sheets/(?P<sheet_id>\d+)/?$', chamtn_api.api_sheet_review_detail, name='chamtn_sheet_detail'),
    re_path(r'^events/?$', chamtn_api.api_events_stream, name='chamtn_events'),
]
