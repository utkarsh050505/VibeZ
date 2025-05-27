from django.db import models
from authentication.models import CoworkingUser

# Create your models here.
class Project(models.Model):
    FIELD_CHOICES = [
        ('AI', 'Artificial Intelligence'),
        ('ML', 'Machine Learning'),
        ('WEB', 'Web Development'),
        ('MOB', 'Mobile Development'),
        ('GAME', 'Game Development'),
        ('DATA', 'Data Science'),
        ('IOT', 'Internet of Things'),
        ('CYBER', 'Cybersecurity'),
        ('VLSI', 'VLSI'),
        ('OTHER', 'Other')
    ]
    
    name = models.CharField(max_length=100)
    description = models.TextField()
    working_field = models.CharField(max_length=20, choices=FIELD_CHOICES)
    github_link = models.URLField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    leader = models.ForeignKey(CoworkingUser, on_delete=models.CASCADE, related_name='led_projects')
    team_members = models.ManyToManyField(CoworkingUser, related_name='projects', blank=True)
    
    def __str__(self):
        return self.name