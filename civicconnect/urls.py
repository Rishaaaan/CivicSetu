from django.urls import path
from . import views

urlpatterns = [
    path('', views.root_redirect, name='root'),
    path('login/', views.login_page, name='login'),
    path('auth/verify', views.verify_token, name='verify_token'),
    path('register/', views.register_page, name='register_page'),
    path('auth/create_user', views.auth_create_user, name='auth_create_user'),
    path('logout/', views.logout_view, name='logout'),

    path('dashboard/', views.admin_dashboard, name='admin_dashboard'),

    # APIs
    path('api/reports/', views.get_reports, name='get_reports'),
    path('api/users/create', views.api_create_user, name='api_create_user'),
    path('api/reports/create', views.api_create_report, name='api_create_report'),
    path('api/users/increment', views.api_increment_report_count, name='api_increment_report_count'),
]
