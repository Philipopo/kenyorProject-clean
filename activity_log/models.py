from django.db import models
from django.conf import settings

User = settings.AUTH_USER_MODEL

class ActivityLog(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    role = models.CharField(max_length=50)  # e.g. "admin", "staff"
    app = models.CharField(max_length=100)  # e.g. "procurement"
    table = models.CharField(max_length=100)  # e.g. "vendor"
    action = models.CharField(max_length=20)  # "create", "update", "delete"
    description = models.TextField(blank=True, null=True)  # optional details
    timestamp = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.user} | {self.app}.{self.table} | {self.action}"