from django.urls import path
from . import views

app_name = 'dashboard'

urlpatterns = [
    path('dashboard/', views.dashboard_view, name='index'),
    path('dashboard/history/', views.history_view, name='history'),
]
