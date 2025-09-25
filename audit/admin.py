from django.contrib import admin
from .models import AuditLog

@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    list_display = ('id', 'action', 'user', 'description', 'timestamp')
    search_fields = ('action', 'user__email', 'description')
    list_filter = ('action', 'timestamp')
