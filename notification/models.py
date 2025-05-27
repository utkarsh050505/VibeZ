from django.db import models
from django.utils import timezone
from authentication.models import CoworkingUser
from projects.models import Project

class Notification(models.Model):
    # Notification type choices
    NOTIFICATION_TYPE_CHOICES = [
        ('JOIN_REQUEST', 'Project Join Request'),
        ('JOIN_ACCEPTED', 'Project Join Request Accepted'),
        ('JOIN_REJECTED', 'Project Join Request Rejected'),
        ('PROJECT_UPDATE', 'Project Update'),
        ('GENERAL', 'General Notification'),
    ]
    
    # Status choices for tracking notification state
    STATUS_CHOICES = [
        ('PENDING', 'Pending'),
        ('ACCEPTED', 'Accepted'),
        ('REJECTED', 'Rejected'),
        ('READ', 'Read'),
    ]
    
    # Notification fields
    sender = models.ForeignKey(CoworkingUser, on_delete=models.CASCADE, related_name='sent_notifications')
    recipient = models.ForeignKey(CoworkingUser, on_delete=models.CASCADE, related_name='received_notifications')
    notification_type = models.CharField(max_length=20, choices=NOTIFICATION_TYPE_CHOICES)
    title = models.CharField(max_length=100)
    message = models.TextField()
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='PENDING')
    created_at = models.DateTimeField(auto_now_add=True)
    read_at = models.DateTimeField(null=True, blank=True)
    
    # Related objects
    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name='notifications', null=True, blank=True)
    
    class Meta:
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.title} - {self.get_notification_type_display()} ({self.get_status_display()})"
    
    def mark_as_read(self):
        """Mark notification as read and update read timestamp"""
        self.status = 'READ'
        self.read_at = timezone.now()
        self.save()
    
    def accept_request(self):
        """Accept join request and update project membership"""
        if self.notification_type == 'JOIN_REQUEST' and self.status == 'PENDING':
            # Add sender to project team members
            self.project.team_members.add(self.sender)
            self.project.save()
            
            # Update notification status
            self.status = 'ACCEPTED'
            self.save()
            
            # Create acceptance notification for the requester
            Notification.objects.create(
                sender=self.recipient,
                recipient=self.sender,
                notification_type='JOIN_ACCEPTED',
                title=f'Request to join {self.project.name} accepted',
                message=f'Your request to join the project "{self.project.name}" has been accepted.',
                status='PENDING',
                project=self.project
            )
            
            return True
        return False
    
    def reject_request(self):
        """Reject join request and notify requester"""
        if self.notification_type == 'JOIN_REQUEST' and self.status == 'PENDING':
            # Update notification status
            self.status = 'REJECTED'
            self.save()
            
            # Create rejection notification for the requester
            Notification.objects.create(
                sender=self.recipient,
                recipient=self.sender,
                notification_type='JOIN_REJECTED',
                title=f'Request to join {self.project.name} rejected',
                message=f'Your request to join the project "{self.project.name}" has been rejected.',
                status='PENDING',
                project=self.project
            )
            
            return True
        return False


class AdminNotification(models.Model):
    # Administrative notification type choices
    ADMIN_NOTIFICATION_TYPE_CHOICES = [
        ('CHECK_IN_REQUEST', 'Check-in Request'),
        ('REQUEST_APPROVED', 'Request Approved'),
        ('REQUEST_REJECTED', 'Request Rejected'),
        ('USER_CHECKED_OUT', 'User Checked Out'),
        ('MANUAL_CHECK_IN', 'Manual Check-in'),
        ('SYSTEM_ALERT', 'System Alert'),
        ('USER_VIOLATION', 'User Violation'),
        ('MAINTENANCE', 'Maintenance Notice'),
    ]
    
    # Administrative notification fields
    notification_type = models.CharField(max_length=20, choices=ADMIN_NOTIFICATION_TYPE_CHOICES)
    title = models.CharField(max_length=200)
    message = models.TextField()
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    read_at = models.DateTimeField(null=True, blank=True)
    read_by = models.ForeignKey('auth.User', on_delete=models.SET_NULL, null=True, blank=True, related_name='read_admin_notifications')
    
    # Related objects for context
    user = models.ForeignKey(CoworkingUser, on_delete=models.CASCADE, related_name='admin_notifications', null=True, blank=True)
    check_in_request = models.ForeignKey('authentication.CheckInRequest', on_delete=models.CASCADE, related_name='admin_notifications', null=True, blank=True)
    session = models.ForeignKey('authentication.CoworkingSession', on_delete=models.CASCADE, related_name='admin_notifications', null=True, blank=True)
    
    # Priority level for administrative notifications
    PRIORITY_CHOICES = [
        ('LOW', 'Low'),
        ('MEDIUM', 'Medium'),
        ('HIGH', 'High'),
        ('URGENT', 'Urgent'),
    ]
    priority = models.CharField(max_length=10, choices=PRIORITY_CHOICES, default='MEDIUM')
    
    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['is_read', '-created_at']),
            models.Index(fields=['notification_type', '-created_at']),
            models.Index(fields=['priority', '-created_at']),
        ]
    
    def __str__(self):
        return f"Admin: {self.title} - {self.get_notification_type_display()} ({self.get_priority_display()})"
    
    def mark_as_read(self, admin_user=None):
        """Mark administrative notification as read"""
        self.is_read = True
        self.read_at = timezone.now()
        if admin_user:
            self.read_by = admin_user
        self.save()
    
    @classmethod
    def create_check_in_alert(cls, user, request_obj=None):
        """Create a check-in request notification for admins"""
        return cls.objects.create(
            notification_type='CHECK_IN_REQUEST',
            title=f'New Check-in Request from {user.name}',
            message=f'User {user.name} has requested to check in and requires administrative approval.',
            user=user,
            check_in_request=request_obj,
            priority='MEDIUM'
        )
    
    @classmethod
    def create_approval_notification(cls, user, request_obj, approved_by):
        """Create notification when request is approved"""
        return cls.objects.create(
            notification_type='REQUEST_APPROVED',
            title=f'Check-in Request Approved for {user.name}',
            message=f'User {user.name} has been checked in successfully by {approved_by.username}.',
            user=user,
            check_in_request=request_obj,
            priority='LOW'
        )
    
    @classmethod
    def create_rejection_notification(cls, user, request_obj, rejected_by, notes=''):
        """Create notification when request is rejected"""
        message = f'Request for {user.name} was rejected by {rejected_by.username}.'
        if notes:
            message += f' Notes: {notes}'
        
        return cls.objects.create(
            notification_type='REQUEST_REJECTED',
            title=f'Check-in Request Rejected for {user.name}',
            message=message,
            user=user,
            check_in_request=request_obj,
            priority='LOW'
        )
    
    @classmethod
    def create_checkout_notification(cls, user, session_obj, checked_out_by):
        """Create notification when user is checked out by admin"""
        return cls.objects.create(
            notification_type='USER_CHECKED_OUT',
            title=f'{user.name} Checked Out by Admin',
            message=f'{user.name} was checked out by administrative user {checked_out_by.username}.',
            user=user,
            session=session_obj,
            priority='LOW'
        )
    
    @classmethod
    def create_manual_checkin_notification(cls, user, checked_in_by):
        """Create notification for manual check-in"""
        return cls.objects.create(
            notification_type='MANUAL_CHECK_IN',
            title=f'Manual Check-in for {user.name}',
            message=f'{user.name} was manually checked in by administrative user {checked_in_by.username}.',
            user=user,
            priority='MEDIUM'
        )
    
    @classmethod
    def create_system_alert(cls, title, message, priority='HIGH'):
        """Create system-wide alert for administrators"""
        return cls.objects.create(
            notification_type='SYSTEM_ALERT',
            title=title,
            message=message,
            priority=priority
        )
    
    @classmethod
    def get_unread_count(cls):
        """Get count of unread administrative notifications"""
        return cls.objects.filter(is_read=False).count()
    
    @classmethod
    def get_urgent_notifications(cls):
        """Get all urgent unread notifications"""
        return cls.objects.filter(is_read=False, priority='URGENT').order_by('-created_at')
    
    def get_related_url(self):
        """Get URL for related object if applicable"""
        if self.check_in_request:
            return f'/admin/check-in-requests/{self.check_in_request.id}/'
        elif self.session:
            return f'/admin/sessions/{self.session.id}/'
        elif self.user:
            return f'/admin/users/{self.user.id}/'
        return '/admin/dashboard/'