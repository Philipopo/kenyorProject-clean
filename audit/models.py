from django.db import models
from django.contrib.auth import get_user_model

User = get_user_model()

class AuditLog(models.Model):
    ACTION_CHOICES = [
        ('Stock Moved', 'Stock Moved'),
        ('User Modified', 'User Modified'),
        ('System Config Updated', 'System Config Updated'),
        ('Approval Granted', 'Approval Granted'),
    ]

    action = models.CharField(max_length=100, choices=ACTION_CHOICES)
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    description = models.TextField()
    timestamp = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.user} - {self.action} at {self.timestamp}"
