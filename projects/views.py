from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.forms import modelformset_factory
from django.contrib import messages
from django.http import HttpResponseRedirect
from django.urls import reverse
from .models import Project, CoworkingUser
from notification.models import Notification
from django.db import transaction

# @login_required(login_url='authentication/login')
def projects_list(request):
    projects = Project.objects.all().order_by('-created_at')

    unread_count = 0
    if request.user.is_authenticated:
        try:
            user = CoworkingUser.objects.get(id=request.user.id)
            notifications = Notification.objects.filter(recipient=user).order_by('-created_at')
            unread_count = notifications.filter(status='PENDING').count()
        except CoworkingUser.DoesNotExist:
            pass  # User authenticated but no CoworkingUser entry
    
    context = {
        'projects': projects,
        'unread_count': unread_count
    }
    return render(request, 'projects/projects_list.html', context)

def project_detail(request, pk):
    project = get_object_or_404(Project, pk=pk)
    team_usernames = list(
        project.team_members.values_list('username', flat=True)
    )
    
    unread_count = 0
    if request.user.is_authenticated:
        try:
            user = CoworkingUser.objects.get(id=request.user.id)
            notifications = Notification.objects.filter(recipient=user).order_by('-created_at')
            unread_count = notifications.filter(status='PENDING').count()
        except CoworkingUser.DoesNotExist:
            pass

    context = {
        'project': project,
        'team_usernames': team_usernames,
        'unread_count': unread_count,
    }
    return render(request, 'projects/project_detail.html', context)

@login_required(login_url='authentication/login')
def create_project(request):
    if request.method == 'POST':
        # Get form data
        name = request.POST.get('name')
        description = request.POST.get('description')
        working_field = request.POST.get('working_field')
        github_link = request.POST.get('github_link')
        
        user = CoworkingUser.objects.get(username=request.user)
        
        # Create project with current user as leader
        project = Project.objects.create(
            name=name,
            description=description,
            working_field=working_field,
            github_link=github_link if github_link else None,
            leader=user
        )
        
        # Handle team members - Get array data
        team_members = request.POST.getlist('team_members[]')
        print(f"Team members from form: {team_members}")  # Debug print
        
        if team_members:
            try:
                with transaction.atomic():
                    for member_email in team_members:
                        member_email = member_email.strip()  # Clean any whitespace
                        if member_email:  # Only process non-empty emails
                            try:
                                # Try to find existing user by email
                                member = CoworkingUser.objects.get(email=member_email)
                                project.team_members.add(member)
                                print(f"Added existing user: {member_email}")  # Debug print
                            except CoworkingUser.DoesNotExist:
                                # If user doesn't exist, delete the project and show error
                                project.delete()
                                return render(request, 'projects/create_project.html', {
                                    'message': f'User with email {member_email} is not registered.'
                                })
            except Exception as e:
                print(f"Error adding team members: {e}")
                project.delete()
                return render(request, 'projects/create_project.html', {
                    'message': 'An error occurred while adding team members.'
                })
        
        return redirect('projects_list')
    
    # Handle GET request
    return render(request, 'projects/create_project.html')