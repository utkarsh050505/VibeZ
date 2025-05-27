from django.shortcuts import render, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_POST
from django.views.decorators.csrf import csrf_exempt
from django.utils import timezone
from django.http import JsonResponse
from datetime import datetime, timedelta
from authentication.models import CoworkingUser, CoworkingSession, UserHoursService
from notification.models import Notification, AdminNotification
from projects.models import Project
import random
import json

# Create your views here.
def start_page(request):
    return render(request, 'user/index.html')

# @login_required(login_url='authentication/login')
def home(request):
    
    projects = list(Project.objects.all())
    random_projects = random.sample(projects, min(3, len(projects))) if projects else []
    
    if request.user.is_authenticated:
        try:
            user = CoworkingUser.objects.get(id=request.user.id)
            notifications = Notification.objects.filter(recipient=user).order_by('-created_at')
            unread_count = notifications.filter(status='PENDING').count()
        except CoworkingUser.DoesNotExist:
            unread_count = 0
    else:
        unread_count = 0

    context = {
        'unread_count': unread_count,
        'random_projects': random_projects,
    }

    return render(request, 'user/home.html', context)

@login_required
def profile_view(request):
    """Display user's profile with hours tracking information"""
    try:
        # Get the CoworkingUser instance
        coworking_user = CoworkingUser.objects.get(id=request.user.id)
    except CoworkingUser.DoesNotExist:
        # Handle case where user is not a CoworkingUser
        pass
    
    # Get hours summary
    hours_summary = coworking_user.get_hours_summary()
    
    # Get recent sessions (last 10)
    recent_sessions = coworking_user.sessions.filter(
        check_out__isnull=False
    ).order_by('-check_in')[:10]
    
    # Get this week's sessions
    week_start = timezone.now().date() - timedelta(days=timezone.now().weekday())
    week_sessions = coworking_user.get_sessions_in_date_range(
        week_start, 
        timezone.now().date()
    )
    
    # Calculate this week's total hours
    week_total_hours = sum(float(session.hours) for session in week_sessions)
    
    # Get average daily hours for past 30 days
    avg_daily_hours = coworking_user.get_average_daily_hours(30)
    
    # Get user's rank among all users (lifetime hours)
    user_ranking = UserHoursService.get_user_ranking_by_hours('lifetime', 100)
    user_rank = None
    for idx, user_data in enumerate(user_ranking, 1):
        if user_data['user'].id == coworking_user.id:
            user_rank = idx
            break
    
    # Prepare context
    context = {
        'user': coworking_user,
        'hours_summary': hours_summary,
        'recent_sessions': recent_sessions,
        'week_sessions': week_sessions,
        'week_total_hours': round(week_total_hours, 2),
        'avg_daily_hours': round(avg_daily_hours, 2),
        'user_rank': user_rank,
        'total_users': CoworkingUser.objects.count(),
        'is_checked_in': coworking_user.is_checked_in,
        'current_session_duration': coworking_user.get_current_session_duration(),
    }
    
    return render(request, 'user/profile.html', context)


@login_required
@require_POST
def check_in_out(request):
    """Handle check-in/check-out AJAX requests"""
    try:
        coworking_user = CoworkingUser.objects.get(id=request.user.id)
    except CoworkingUser.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'User not found'})
    
    action = request.POST.get('action')
    
    if action == 'check_in':
        success = coworking_user.check_in_user()
        if success:
            return JsonResponse({
                'success': True, 
                'message': 'Checked in successfully!',
                'is_checked_in': True,
                'check_in_time': coworking_user.current_check_in.strftime('%H:%M')
            })
        else:
            return JsonResponse({
                'success': False, 
                'error': 'Already checked in'
            })
    
    elif action == 'check_out':
        success = coworking_user.check_out_user()
        if success:
            return JsonResponse({
                'success': True, 
                'message': 'Checked out successfully!',
                'is_checked_in': False
            })
        else:
            return JsonResponse({
                'success': False, 
                'error': 'Not currently checked in'
            })
    
    return JsonResponse({'success': False, 'error': 'Invalid action'})


@login_required
def get_current_session_duration(request):
    """Get current session duration for live updates"""
    try:
        coworking_user = CoworkingUser.objects.get(id=request.user.id)
        duration = coworking_user.get_current_session_duration()
        return JsonResponse({
            'duration': duration,
            'is_checked_in': coworking_user.is_checked_in
        })
    except CoworkingUser.DoesNotExist:
        return JsonResponse({'duration': 0, 'is_checked_in': False})


@login_required
def home_view(request):
    """Home view with check-in functionality"""
    try:
        coworking_user = CoworkingUser.objects.get(id=request.user.id)
    except CoworkingUser.DoesNotExist:
        pass
    
    context = {
        'user': coworking_user,
        'is_checked_in': coworking_user.is_checked_in,
        'current_session_duration': coworking_user.get_current_session_duration(),
    }
    
    return render(request, 'user/home.html', context)


@login_required
@csrf_exempt
def create_check_in_request(request):
    """Create a check-in request"""
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            requested_date = datetime.strptime(data['date'], '%Y-%m-%d').date()
            requested_time = datetime.strptime(data['time'], '%H:%M').time()
            
            coworking_user = CoworkingUser.objects.get(id=request.user.id)
            
            check_in_request, message = coworking_user.create_check_in_request(
                requested_date, requested_time
            )
            
            if check_in_request:
                # Create admin notification
                AdminNotification.objects.create(
                    notification_type='CHECK_IN_REQUEST',
                    title=f'New Check-in Request from {coworking_user.name}',
                    message=f'{coworking_user.name} (Phone: {coworking_user.phone}, Email: {coworking_user.email}) wants to check in on {requested_date} at {requested_time}',
                    user=coworking_user,
                    check_in_request=check_in_request
                )
                
                return JsonResponse({
                    'success': True,
                    'message': 'Check-in request submitted successfully! Admin will approve your request.'
                })
            else:
                return JsonResponse({
                    'success': False,
                    'message': message
                })
                
        except CoworkingUser.DoesNotExist:
            return JsonResponse({
                'success': False,
                'message': 'User profile not found. Please complete your profile setup.'
            })
        except Exception as e:
            return JsonResponse({
                'success': False,
                'message': f'Error creating request: {str(e)}'
            })
    
    return JsonResponse({'success': False, 'message': 'Invalid request method'})


@login_required
def user_requests_view(request):
    """View user's check-in requests"""
    try:
        coworking_user = CoworkingUser.objects.get(id=request.user.id)
        requests = coworking_user.check_in_requests.all()[:10]  # Last 10 requests
        
        context = {
            'requests': requests,
            'user': coworking_user
        }
        
        return render(request, 'user_requests.html', context)
    except CoworkingUser.DoesNotExist:
        pass

@login_required
def get_user_status(request):
    """Get current user status for frontend updates"""
    try:
        coworking_user = CoworkingUser.objects.get(id=request.user.id)
        
        # Get latest request status
        latest_request = coworking_user.check_in_requests.first()
        request_status = latest_request.status if latest_request else None
        
        return JsonResponse({
            'is_checked_in': coworking_user.is_checked_in,
            'current_session_duration': coworking_user.get_current_session_duration(),
            'latest_request_status': request_status,
            'latest_request_date': latest_request.requested_date.isoformat() if latest_request else None,
            'latest_request_time': latest_request.requested_time.isoformat() if latest_request else None
        })
        
    except CoworkingUser.DoesNotExist:
        return JsonResponse({'error': 'User profile not found'})