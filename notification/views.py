from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.utils import timezone
from django.urls import reverse
from django.contrib import messages
from .models import Notification
from projects.models import Project
from authentication.models import CoworkingUser

@login_required(login_url='authentication/login')
def notifications_list(request):
    user = CoworkingUser.objects.get(id=request.user.id)
    Notification.objects.filter(recipient=user, status='READ').delete()
    Notification.objects.filter(recipient=user, status='ACCEPTED').delete()
    Notification.objects.filter(recipient=user, status='REJECTED').delete()
    
    notifications = Notification.objects.filter(recipient=user).order_by('-created_at')
    
    # Count unread notifications
    unread_count = notifications.filter(status='PENDING').count()
    
    context = {
        'notifications': notifications,
        'unread_count': unread_count,
    }
    
    return render(request, 'notifications/notifications_list.html', context)

@login_required(login_url='authentication/login')
def mark_as_read(request, notification_id):
    notification = get_object_or_404(Notification, id=notification_id, recipient=request.user.id)
    notification.mark_as_read()
    
    if request.headers.get('x-requested-with') == 'XMLHttpRequest':
        return JsonResponse({'status': 'success'})
    
    user = CoworkingUser.objects.get(id=request.user.id)
    Notification.objects.filter(recipient=user, status='READ').delete()
    Notification.objects.filter(recipient=user, status='ACCEPTED').delete()
    Notification.objects.filter(recipient=user, status='REJECTED').delete()
    
    return redirect('notifications_list')

@login_required(login_url='authentication/login')
def handle_join_request(request, notification_id, action):
    """
    Handle project join requests - accept or reject
    """
    notification = get_object_or_404(Notification, id=notification_id, recipient=request.user.id)
    
    # Verify this is a join request and user is the project leader
    if notification.notification_type != 'JOIN_REQUEST' or notification.project.leader.id != request.user.id:
        messages.error(request, "You don't have permission to perform this action.")
        return redirect('notifications_list')
    
    success = False
    if action == 'accept':
        success = notification.accept_request()
        if success:
            messages.success(request, f"Join request accepted. {notification.sender.name} has been added to the project.")
    elif action == 'reject':
        success = notification.reject_request()
        if success:
            messages.info(request, f"Join request rejected.")
    
    if request.headers.get('x-requested-with') == 'XMLHttpRequest':
        return JsonResponse({'status': 'success' if success else 'error'})
    
    user = CoworkingUser.objects.get(id=request.user.id)
    Notification.objects.filter(recipient=user, status='READ').delete()
    Notification.objects.filter(recipient=user, status='ACCEPTED').delete()
    Notification.objects.filter(recipient=user, status='REJECTED').delete()
    
    return redirect('notifications_list')

@login_required(login_url='authentication/login')
def create_join_request(request, project_id):
    """
    Create a notification for joining a project
    """
    project = get_object_or_404(Project, id=project_id)
    user = CoworkingUser.objects.get(id=request.user.id)
    
    # Check if user is already a member
    if user in project.team_members.all() or user == project.leader:
        messages.info(request, "You are already a member of this project.")
        return redirect('project_detail', project_id=project_id)
    
    # Check if there's already a pending request
    existing_request = Notification.objects.filter(
        sender=user,
        recipient=project.leader,
        project=project,
        notification_type='JOIN_REQUEST',
        status='PENDING'
    ).exists()
    
    if existing_request:
        messages.info(request, "You have already sent a request to join this project.")
    else:
        # Create the notification
        Notification.objects.create(
            sender=user,
            recipient=project.leader,
            notification_type='JOIN_REQUEST',
            title=f"Join Request: {project.name}",
            message=f"{user.name} would like to join your project '{project.name}'.",
            project=project
        )
        messages.success(request, "Your request to join this project has been sent.")
    
    return redirect('projects_list')

@login_required(login_url='authentication/login')
def notification_count(request):
    """
    Get the count of unread notifications (for AJAX calls)
    """
    if not request.user.is_authenticated:
        return JsonResponse({'count': 0})
    
    user = CoworkingUser.objects.get(id=request.user.id)
    count = Notification.objects.filter(recipient=user, status='PENDING').count()
    
    Notification.objects.filter(recipient=user, status='READ').delete()
    Notification.objects.filter(recipient=user, status='ACCEPTED').delete()
    Notification.objects.filter(recipient=user, status='REJECTED').delete()
    
    return JsonResponse({'count': count})