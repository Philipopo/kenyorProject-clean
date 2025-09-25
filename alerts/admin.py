# alerts/admin.py
from django.contrib import admin
from .models import Alert

@admin.register(Alert)
class AlertAdmin(admin.ModelAdmin):
    list_display = ['type', 'user', 'message', 'time']
    search_fields = ['type', 'message']
    list_filter = ['type', 'time']
