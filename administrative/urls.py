from django.urls import path
from . import views

app_name = 'administrative'

urlpatterns = [
    # Main administrative dashboard
    path('dashboard/', views.administrative_dashboard, name='dashboard'),
    
    # Check-in/Check-out management
    path('approve-checkin/', views.approve_check_in_request, name='approve_check_in_request'),
    path('checkout-user/', views.administrative_check_out_user, name='check_out_user'),
    path('reject-request/', views.reject_check_in_request, name='reject_check_in_request'),
    path('manual-checkin/', views.manual_check_in_user, name='manual_check_in_user'),
    
    # User management
    path('users/', views.administrative_users_list, name='users_list'),
    
    # History and reports
    path('sessions/', views.administrative_sessions_history, name='sessions_history'),
    path('requests/', views.administrative_requests_history, name='requests_history'),
    path('projects/', views.administrative_projects, name='projects'),
    path('projects/<int:pk>/delete/', views.delete_project, name='delete_project'),
    path('', views.admin_login, name='admin-login')
]