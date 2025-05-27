from django.urls import path
from . import views

urlpatterns = [
    path('', views.start_page, name='start_page'),
    path('home', views.home, name='home'),
    path('profile', views.profile_view, name='profile'),
    path('get-user-status/', views.get_user_status, name='get_user_status'),
    path('my-requests/', views.user_requests_view, name='user_requests'),
    path('create-checkin-request/', views.create_check_in_request, name='create_check_in_request'),
]
