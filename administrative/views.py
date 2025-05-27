from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import user_passes_test
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
from django.contrib import auth
from django.utils import timezone
from django.http import JsonResponse
import json
from authentication.models import CoworkingUser, CoworkingSession, CheckInRequest
from projects.models import Project
from notification.models import AdminNotification

def is_administrative_user(user):
    """Check if user has administrative privileges"""
    return user

def admin_login(request):
    if request.method == 'GET':
        return render(request, 'administrative/login.html')
    else:
        username = request.POST["username"]
        password = request.POST["password"]
        
        user, created = CoworkingUser.objects.get_or_create(
            username='vibez-desk',
            defaults={
                'email': 'vibezconnect610@gmail.com',
            }
        )
            
        if created:
            user.set_password('vibez-connect@00319')
            user.save()
        
        user = auth.authenticate(username=username, password=password)
        
        if user is not None:
            auth.login(request, user)
            is_administrative_user(True)
            return redirect('administrative:dashboard')  # Change to your desired redirect
        else:
            is_administrative_user(False)
            return render(request, 'administrative/login.html', {'message': 'Invalid credentials'})       

@user_passes_test(is_administrative_user)
def administrative_projects(request):
    if request.method == 'GET':
        projects = Project.objects.all()
        return render(request, 'administrative/projects.html', {
            'projects': projects
        })

@user_passes_test(is_administrative_user)
def administrative_dashboard(request):
    """Administrative dashboard for managing check-ins"""
    pending_requests = CheckInRequest.objects.filter(status='PENDING').order_by('-request_timestamp')
    current_sessions = CoworkingSession.objects.filter(check_out__isnull=True).order_by('-check_in')
    recent_notifications = AdminNotification.objects.filter(is_read=False)[:10]
    
    # Get additional stats
    total_users = CoworkingUser.objects.count()
    total_sessions_today = CoworkingSession.objects.filter(
        check_in__date=timezone.now().date()
    ).count()
    
    context = {
        'pending_requests': pending_requests,
        'current_sessions': current_sessions,
        'notifications': recent_notifications,
        'total_pending': pending_requests.count(),
        'total_active_sessions': current_sessions.count(),
        'total_users': total_users,
        'total_sessions_today': total_sessions_today,
    }
    
    return render(request, 'administrative/dashboard.html', context)

@user_passes_test(is_administrative_user)
@csrf_exempt
def approve_check_in_request(request):
    """Administrative approval and check-in of a user"""
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            request_id = data.get('request_id')
            
            check_in_request = get_object_or_404(CheckInRequest, id=request_id)
            
            if check_in_request.status != 'PENDING':
                return JsonResponse({
                    'success': False,
                    'message': 'Request is no longer pending'
                })
            
            success, message = check_in_request.user.admin_check_in(
                request.user, check_in_request
            )
            
            if success:
                # Create notification about approval
                AdminNotification.objects.create(
                    notification_type='REQUEST_APPROVED',
                    title=f'Check-in Request Approved for {check_in_request.user.name}',
                    message=f'User {check_in_request.user.name} has been checked in successfully.',
                    user=check_in_request.user,
                    check_in_request=check_in_request
                )
            
            return JsonResponse({
                'success': success,
                'message': message
            })
            
        except Exception as e:
            return JsonResponse({
                'success': False,
                'message': f'Error approving check-in request: {str(e)}'
            })
    
    return JsonResponse({'success': False, 'message': 'Invalid request method'})


@user_passes_test(is_administrative_user)
@csrf_exempt
def administrative_check_out_user(request):
    """Administrative check-out of a user with payment tracking"""
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            session_id = data.get('session_id')
            final_amount = data.get('final_amount', 0)
            discount = data.get('discount', 0)
            first_time = data.get('first_time', False)
            
            session = get_object_or_404(CoworkingSession, id=session_id)
            
            if session.check_out:
                return JsonResponse({
                    'success': False,
                    'message': 'User is already checked out'
                })
            
            success, message = session.user.admin_check_out(
                request.user,
                final_amount=final_amount,
                discount=discount,
                first_time=first_time
            )
            
            if success:
                # Create notification about checkout
                AdminNotification.objects.create(
                    notification_type='USER_CHECKED_OUT',
                    title=f'{session.user.name} Checked Out by Admin',
                    message=f'{session.user.name} was checked out. Amount collected: ₹{final_amount}',
                    user=session.user,
                    session=session
                )
            
            return JsonResponse({
                'success': success,
                'message': message
            })
            
        except Exception as e:
            return JsonResponse({
                'success': False,
                'message': f'Error checking out user: {str(e)}'
            })
    
    return JsonResponse({'success': False, 'message': 'Invalid request method'})


@user_passes_test(is_administrative_user)
@csrf_exempt
def reject_check_in_request(request):
    """Administrative rejection of a check-in request"""
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            request_id = data.get('request_id')
            admin_notes = data.get('notes', '')
                
            check_in_request = get_object_or_404(CheckInRequest, id=request_id)
            
            if check_in_request.status != 'PENDING':
                return JsonResponse({
                    'success': False,
                    'message': 'Request is no longer pending'
                })
            
            check_in_request.status = 'REJECTED'
            check_in_request.admin_notes = admin_notes
            check_in_request.approved_by = request.user
            check_in_request.approved_at = timezone.now()
            check_in_request.save()
            
            # Create notification about rejection
            AdminNotification.objects.create(
                notification_type='REQUEST_REJECTED',
                title=f'Check-in Request Rejected for {check_in_request.user.name}',
                message=f'Request for {check_in_request.user.name} was rejected. Notes: {admin_notes}',
                user=check_in_request.user,
                check_in_request=check_in_request
            )
            
            return JsonResponse({
                'success': True,
                'message': 'Request rejected successfully'
            })
            
        except Exception as e:
            return JsonResponse({
                'success': False,
                'message': f'Error rejecting request: {str(e)}'
            })
    
    return JsonResponse({'success': False, 'message': 'Invalid request method'})


@user_passes_test(is_administrative_user)
def administrative_users_list(request):
    """List all users with their current status"""
    users = CoworkingUser.objects.all().order_by('name')
    
    # Add current session info to each user
    for user in users:
        user.current_session = user.sessions.filter(check_out__isnull=True).first()
        user.total_hours = user.get_hours_summary().get('lifetime_hours', 0)
    
    context = {
        'users': users,
        'total_users': users.count(),
        'checked_in_users': sum(1 for user in users if user.is_checked_in),
    }
    
    return render(request, 'administrative/users_list.html', context)


@user_passes_test(is_administrative_user)
def administrative_sessions_history(request):
    """View session history with filtering options"""
    sessions = CoworkingSession.objects.select_related('user').order_by('-check_in')
    
    # Filter by date range if provided
    date_from = request.GET.get('date_from')
    date_to = request.GET.get('date_to')
    
    if date_from:
        sessions = sessions.filter(check_in__date__gte=date_from)
    if date_to:
        sessions = sessions.filter(check_in__date__lte=date_to)
    
    # Filter by user if provided
    user_id = request.GET.get('user_id')
    if user_id:
        sessions = sessions.filter(user_id=user_id)
    
    # Pagination - show 50 sessions per page
    sessions = sessions[:50]
    
    context = {
        'sessions': sessions,
        'users': CoworkingUser.objects.all().order_by('name'),
        'filters': {
            'date_from': date_from,
            'date_to': date_to,
            'user_id': user_id,
        }
    }
    
    return render(request, 'administrative/sessions_history.html', context)


@user_passes_test(is_administrative_user)
def administrative_requests_history(request):
    """View all check-in requests history"""
    requests = CheckInRequest.objects.select_related('user', 'approved_by').order_by('-request_timestamp')
    
    # Filter by status if provided
    status = request.GET.get('status')
    if status:
        requests = requests.filter(status=status)
    
    # Filter by user if provided
    user_id = request.GET.get('user_id')
    if user_id:
        requests = requests.filter(user_id=user_id)
    
    # Pagination - show 50 requests per page
    requests = requests[:50]
    
    context = {
        'requests': requests,
        'users': CoworkingUser.objects.all().order_by('name'),
        'status_choices': CheckInRequest.STATUS_CHOICES if hasattr(CheckInRequest, 'STATUS_CHOICES') else [
            ('PENDING', 'Pending'),
            ('APPROVED', 'Approved'),
            ('REJECTED', 'Rejected'),
        ],
        'filters': {
            'status': status,
            'user_id': user_id,
        }
    }
    
    return render(request, 'administrative/requests_history.html', context)


@user_passes_test(is_administrative_user)
@csrf_exempt
def manual_check_in_user(request):
    """Manually check in a user without a request"""
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            user_id = data.get('user_id')
            
            coworking_user = get_object_or_404(CoworkingUser, id=user_id)
            
            if coworking_user.is_checked_in:
                return JsonResponse({
                    'success': False,
                    'message': 'User is already checked in'
                })
            
            success, message = coworking_user.admin_check_in(request.user)
            
            if success:
                # Create notification about manual check-in
                AdminNotification.objects.create(
                    notification_type='MANUAL_CHECK_IN',
                    title=f'Manual Check-in for {coworking_user.name}',
                    message=f'{coworking_user.name} was manually checked in by {request.user.username}.',
                    user=coworking_user
                )
                
                return JsonResponse({
                    'success': True,
                    'message': f'{coworking_user.name} checked in successfully'
                })
            else:
                return JsonResponse({
                    'success': False,
                    'message': message
                })
            
        except Exception as e:
            return JsonResponse({
                'success': False,
                'message': f'Error checking in user: {str(e)}'
            })
    
    return JsonResponse({'success': False, 'message': 'Invalid request method'})

@user_passes_test(is_administrative_user)
def delete_project(request, pk):
    if request.method == 'POST':
        project = get_object_or_404(Project, pk=pk)
        # Delete directly without POST form
        project.delete()
        return redirect('administrative:projects')