from django.db import models
from django.utils import timezone
from django.contrib.auth.models import User
from datetime import datetime, timedelta
from django.db.models import Sum, Q
from decimal import Decimal


class CheckInRequest(models.Model):
    """Model to track check-in requests that need admin approval"""
    STATUS_CHOICES = [
        ('PENDING', 'Pending'),
        ('APPROVED', 'Approved'),
        ('REJECTED', 'Rejected'),
        ('COMPLETED', 'Completed'),
    ]
    
    user = models.ForeignKey('CoworkingUser', on_delete=models.CASCADE, related_name='check_in_requests')
    requested_date = models.DateField()
    requested_time = models.TimeField()
    request_timestamp = models.DateTimeField(auto_now_add=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='PENDING')
    admin_notes = models.TextField(blank=True, null=True)
    approved_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='approved_requests')
    approved_at = models.DateTimeField(null=True, blank=True)
    
    def __str__(self):
        return f"{self.user.name} - {self.requested_date} at {self.requested_time} ({self.status})"
    
    class Meta:
        ordering = ['-request_timestamp']


class CoworkingSession(models.Model):
    """Model to track individual coworking sessions"""
    user = models.ForeignKey('CoworkingUser', on_delete=models.CASCADE, related_name='sessions')
    check_in_request = models.OneToOneField(CheckInRequest, on_delete=models.CASCADE, null=True, blank=True)
    check_in = models.DateTimeField()
    check_out = models.DateTimeField(null=True, blank=True)
    hours = models.DecimalField(max_digits=6, decimal_places=2, null=True, blank=True)
    checked_in_by_admin = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='checked_in_sessions')
    checked_out_by_admin = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='checked_out_sessions')
    amount = models.DecimalField(max_digits=8, decimal_places=2, null=True, blank=True)
    discount = models.DecimalField(max_digits=5, decimal_places=2, default=0)  # percentage
    paid = models.DecimalField(max_digits=8, decimal_places=2, null=True, blank=True)
    is_first_time_discount = models.BooleanField(default=False)
    
    def save(self, *args, **kwargs):
        # Calculate hours when check_out is set
        if self.check_in and self.check_out:
            duration = self.check_out - self.check_in
            self.hours = Decimal(str(duration.total_seconds() / 3600))
        super().save(*args, **kwargs)
    
    def get_duration_display(self):
        """Return duration in hours and minutes format like '1hr 20min'"""
        if not self.hours:
            return "-"
        
        total_minutes = int(float(self.hours) * 60)
        hours = total_minutes // 60
        minutes = total_minutes % 60
        
        if hours > 0 and minutes > 0:
            return f"{hours}hr {minutes}min"
        elif hours > 0:
            return f"{hours}hr"
        elif minutes > 0:
            return f"{minutes}min"
        else:
            return "0min"
    
    def get_current_duration_display(self):
        """Get current session duration for ongoing sessions"""
        if self.check_in and not self.check_out:
            from django.utils import timezone
            duration = timezone.now() - self.check_in
            total_minutes = int(duration.total_seconds() / 60)
            hours = total_minutes // 60
            minutes = total_minutes % 60
            
            if hours > 0 and minutes > 0:
                return f"{hours}hr {minutes}min (ongoing)"
            elif hours > 0:
                return f"{hours}hr (ongoing)"
            elif minutes > 0:
                return f"{minutes}min (ongoing)"
            else:
                return "0min (ongoing)"
        return self.get_duration_display()
    
    def __str__(self):
        return f"{self.user.name} - {self.check_in.date()} ({self.get_duration_display()})"
    
    class Meta:
        ordering = ['-check_in']


class CoworkingUser(User):
    # Study level choices
    STUDY_LEVEL_CHOICES = [
        ('UG', 'Undergraduate'),
        ('PG', 'Postgraduate'),
        ('PHD', 'Doctorate'),
        ('FACULTY', 'Faculty'),
        ('PROFESSIONAL', 'Professional'),
        ('OTHER', 'Other'),
    ]
    
    # User basic information
    name = models.CharField(max_length=100)
    phone = models.CharField(max_length=15)
    
    # Academic information
    study_level = models.CharField(max_length=20, choices=STUDY_LEVEL_CHOICES)
    specialization = models.CharField(max_length=100)
    college_name = models.CharField(max_length=200)
    
    # Current session tracking (for active check-ins)
    current_session = models.OneToOneField(CoworkingSession, on_delete=models.SET_NULL, null=True, blank=True, related_name='active_user')
    is_checked_in = models.BooleanField(default=False)
    
    def create_check_in_request(self, requested_date, requested_time):
        """Create a new check-in request"""
        # Check if user already has a pending request for the same date
        existing_request = self.check_in_requests.filter(
            requested_date=requested_date,
            status='PENDING'
        ).first()
        
        if existing_request:
            return None, "You already have a pending request for this date"
        
        # Check if user is already checked in
        if self.is_checked_in:
            return None, "You are already checked in"
        
        request = CheckInRequest.objects.create(
            user=self,
            requested_date=requested_date,
            requested_time=requested_time
        )
        
        return request, "Check-in request submitted successfully"
    
    def admin_check_in(self, admin_user, check_in_request=None):
        """Admin checks in the user"""
        if self.is_checked_in:
            return False, "User is already checked in"
        
        check_in_time = timezone.now()
        
        # Create a new session
        session = CoworkingSession.objects.create(
            user=self,
            check_in_request=check_in_request,
            check_in=check_in_time,
            checked_in_by_admin=admin_user
        )
        
        # Update user status
        self.current_session = session
        self.is_checked_in = True
        self.save()
        
        # Update request status if provided
        if check_in_request:
            check_in_request.status = 'APPROVED'
            check_in_request.approved_by = admin_user
            check_in_request.approved_at = timezone.now()
            check_in_request.save()
        
        return True, "User checked in successfully"
    
    def admin_check_out(self, admin_user, final_amount=None, discount=0, first_time=False):
        """Admin checks out the user with payment tracking"""
        if not self.is_checked_in or not self.current_session:
            return False, "User is not checked in"
        
        check_out_time = timezone.now()
        
        # Update the current session
        session = self.current_session
        session.check_out = check_out_time
        session.checked_out_by_admin = admin_user
        
        # Add payment tracking
        if final_amount is not None:
            # Calculate base amount
            duration_hours = (check_out_time - session.check_in).total_seconds() / 3600
            duration_mins = duration_hours * 60
            rate = 0.667 if duration_mins <= 180 else 0.5
            base_amount = duration_mins * rate
            
            session.amount = Decimal(str(base_amount))
            session.discount = Decimal(str(discount))
            session.paid = Decimal(str(final_amount))
            session.is_first_time_discount = first_time
        
        session.save()
        
        # Reset user status
        self.current_session = None
        self.is_checked_in = False
        self.save()
        
        # Mark associated request as completed
        if session.check_in_request:
            session.check_in_request.status = 'COMPLETED'
            session.check_in_request.save()
        
        return True, f"User checked out successfully. Amount collected: ₹{final_amount or 0}"
    
    def get_lifetime_hours(self):
        """Get total hours spent in VibeZ (lifetime)"""
        total = self.sessions.filter(
            check_out__isnull=False
        ).aggregate(total_hours=Sum('hours'))['total_hours']
        
        return float(total) if total else 0.0
    
    def get_past_year_hours(self):
        """Get hours spent in the past 365 days"""
        one_year_ago = timezone.now() - timedelta(days=365)
        
        total = self.sessions.filter(
            check_out__isnull=False,
            check_in__gte=one_year_ago
        ).aggregate(total_hours=Sum('hours'))['total_hours']
        
        return float(total) if total else 0.0
    
    def get_past_month_hours(self):
        """Get hours spent in the past 30 days"""
        one_month_ago = timezone.now() - timedelta(days=30)
        
        total = self.sessions.filter(
            check_out__isnull=False,
            check_in__gte=one_month_ago
        ).aggregate(total_hours=Sum('hours'))['total_hours']
        
        return float(total) if total else 0.0
    
    def get_hours_summary(self):
        """Get a summary of all hour statistics"""
        return {
            'lifetime': self.get_lifetime_hours(),
            'past_year': self.get_past_year_hours(),
            'past_month': self.get_past_month_hours(),
            'current_session_duration': self.get_current_session_duration()
        }
    
    def get_current_session_duration(self):
        """Get current session duration in hours (if checked in)"""
        if self.is_checked_in and self.current_session:
            duration = timezone.now() - self.current_session.check_in
            return round(duration.total_seconds() / 3600, 2)
        return 0.0
    
    def get_sessions_in_date_range(self, start_date, end_date):
        """Get sessions within a specific date range"""
        return self.sessions.filter(
            check_in__date__gte=start_date,
            check_in__date__lte=end_date,
            check_out__isnull=False
        )
    
    def get_average_daily_hours(self, days=30):
        """Get average daily hours over specified number of days"""
        start_date = timezone.now() - timedelta(days=days)
        total_hours = self.sessions.filter(
            check_out__isnull=False,
            check_in__gte=start_date
        ).aggregate(total_hours=Sum('hours'))['total_hours']
        
        if total_hours:
            return float(total_hours) / days
        return 0.0
    
    def __str__(self):
        return f"{self.name} ({self.email})"


class AdminNotification(models.Model):
    """Model to track admin notifications"""
    NOTIFICATION_TYPES = [
        ('CHECK_IN_REQUEST', 'Check-in Request'),
        ('USER_CHECKED_OUT', 'User Checked Out'),
        ('SYSTEM', 'System Notification'),
    ]
    
    notification_type = models.CharField(max_length=20, choices=NOTIFICATION_TYPES)
    title = models.CharField(max_length=200)
    message = models.TextField()
    user = models.ForeignKey(CoworkingUser, on_delete=models.CASCADE, null=True, blank=True)
    check_in_request = models.ForeignKey(CheckInRequest, on_delete=models.CASCADE, null=True, blank=True)
    session = models.ForeignKey(CoworkingSession, on_delete=models.CASCADE, null=True, blank=True)
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return f"{self.title} - {self.created_at.strftime('%Y-%m-%d %H:%M')}"
    
    class Meta:
        ordering = ['-created_at']


class UserHoursService:
    """Service class for advanced hours tracking and analytics"""
    
    @staticmethod
    def get_user_ranking_by_hours(period='lifetime', limit=10):
        """Get top users by hours for a specific period"""
        users = CoworkingUser.objects.all()
        
        if period == 'lifetime':
            user_hours = [
                {'user': user, 'hours': user.get_lifetime_hours()}
                for user in users
            ]
        elif period == 'past_year':
            user_hours = [
                {'user': user, 'hours': user.get_past_year_hours()}
                for user in users
            ]
        elif period == 'past_month':
            user_hours = [
                {'user': user, 'hours': user.get_past_month_hours()}
                for user in users
            ]
        else:
            return []
        
        # Sort by hours in descending order
        user_hours.sort(key=lambda x: x['hours'], reverse=True)
        
        return user_hours[:limit]
    
    @staticmethod
    def get_total_space_hours(period='lifetime'):
        """Get total hours across all users for analytics"""
        if period == 'lifetime':
            total = CoworkingSession.objects.filter(
                check_out__isnull=False
            ).aggregate(total_hours=Sum('hours'))['total_hours']
        elif period == 'past_year':
            one_year_ago = timezone.now() - timedelta(days=365)
            total = CoworkingSession.objects.filter(
                check_out__isnull=False,
                check_in__gte=one_year_ago
            ).aggregate(total_hours=Sum('hours'))['total_hours']
        elif period == 'past_month':
            one_month_ago = timezone.now() - timedelta(days=30)
            total = CoworkingSession.objects.filter(
                check_out__isnull=False,
                check_in__gte=one_month_ago
            ).aggregate(total_hours=Sum('hours'))['total_hours']
        else:
            return 0.0
        
        return float(total) if total else 0.0
    
    @staticmethod
    def get_currently_checked_in_users():
        """Get all users currently checked in"""
        return CoworkingUser.objects.filter(is_checked_in=True)
    
    @staticmethod
    def get_daily_usage_stats(days=30):
        """Get daily usage statistics for the past N days"""
        start_date = timezone.now() - timedelta(days=days)
        
        sessions = CoworkingSession.objects.filter(
            check_out__isnull=False,
            check_in__gte=start_date
        )
        
        daily_stats = {}
        for session in sessions:
            date_key = session.check_in.date()
            if date_key not in daily_stats:
                daily_stats[date_key] = {
                    'total_hours': 0,
                    'unique_users': set(),
                    'session_count': 0
                }
            
            daily_stats[date_key]['total_hours'] += float(session.hours)
            daily_stats[date_key]['unique_users'].add(session.user.id)
            daily_stats[date_key]['session_count'] += 1
        
        # Convert sets to counts for JSON serialization
        for date_key in daily_stats:
            daily_stats[date_key]['unique_users'] = len(daily_stats[date_key]['unique_users'])
        
        return daily_stats
