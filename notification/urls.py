from django.urls import path
from django.views.decorators.csrf import csrf_exempt
from . import views

urlpatterns = [
    path('', views.notifications_list, name='notifications_list'),
    path('count/', views.notification_count, name='notification_count'),
    path('mark-read/<int:notification_id>/', views.mark_as_read, name='mark_as_read'),
    path('handle-request/<int:notification_id>/<str:action>/', views.handle_join_request, name='handle_join_request'),
    path('join-request/<int:project_id>/', csrf_exempt(views.create_join_request), name='create_join_request'),
]