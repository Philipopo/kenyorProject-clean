from django.db import models
from django.contrib.auth import get_user_model

User = get_user_model()


class BrandAsset(models.Model):
    ASSET_TYPES = [
        ('Logo', 'Logo'),
        ('Letterhead', 'Letterhead'),
        ('Color Palette', 'Color Palette'),
    ]
    name = models.CharField(max_length=100)
    type = models.CharField(max_length=50, choices=ASSET_TYPES)
    file = models.FileField(upload_to='brand_assets/', null=True, blank=True)
    uploaded_by = models.ForeignKey(User, on_delete=models.CASCADE)
    upload_date = models.DateField(auto_now_add=True)

    def __str__(self):
        return self.name


class ERPIntegration(models.Model):
    STATUS_CHOICES = [
        ('Connected', 'Connected'),
        ('Pending', 'Pending'),
        ('Failed', 'Failed'),
    ]
    system = models.CharField(max_length=100)
    status = models.CharField(max_length=50, choices=STATUS_CHOICES)
    last_sync = models.DateField(auto_now_add=True)
    synced_by = models.ForeignKey(User, on_delete=models.CASCADE)

    def __str__(self):
        return self.system


class Tracker(models.Model):
    STATUS_CHOICES = [
        ('Active', 'Active'),
        ('Inactive', 'Inactive'),
        ('Pending', 'Pending'),
    ]
    device_id = models.CharField(max_length=50)
    asset = models.CharField(max_length=100)
    status = models.CharField(max_length=50, choices=STATUS_CHOICES)
    last_ping = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(User, on_delete=models.CASCADE)

    def __str__(self):
        return self.device_id





class CompanyBranding(models.Model):
    name = models.CharField(max_length=255, help_text="Company name")
    logo = models.ImageField(upload_to='branding_logos/', blank=True, null=True)
    primary_color = models.CharField(max_length=7, help_text="Hex code, e.g. #1D4ED8")
    secondary_color = models.CharField(max_length=7, help_text="Hex code")
    tagline = models.CharField(max_length=255, blank=True, null=True)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name="brandings")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']  # latest first

    def __str__(self):
        return self.name


class ActivityLog(models.Model):
    ACTION_CHOICES = [
        ('CREATE', 'Created'),
        ('UPDATE', 'Updated'),
        ('DELETE', 'Deleted'),
        ('LOGIN', 'Login'),
        ('LOGOUT', 'Logout'),
    ]

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="activities")
    action = models.CharField(max_length=20, choices=ACTION_CHOICES)
    description = models.TextField()
    timestamp = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-timestamp']  # latest first

    def __str__(self):
        return f"{self.user} {self.action} at {self.timestamp}"


class Announcement(models.Model):
    title = models.CharField(max_length=200)
    message = models.TextField()
    created_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name="announcements")
    created_at = models.DateTimeField(auto_now_add=True)
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return self.title


