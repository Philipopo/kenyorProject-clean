from django.db import models
from django.contrib.auth import get_user_model

User = get_user_model()

class Alert(models.Model):
    ALERT_TYPES = [
        ('Stock Threshold', 'Stock Threshold'),
        ('Expiry Warning', 'Expiry Warning'),
        ('Tracker Issue', 'Tracker Issue'),
        ('Unauthorized Access', 'Unauthorized Access'),
    ]

    user = models.ForeignKey(User, on_delete=models.CASCADE)
    type = models.CharField(max_length=50, choices=ALERT_TYPES)
    message = models.TextField()
    time = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.type} - {self.message[:30]}"
