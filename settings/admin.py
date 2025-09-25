# settings/admin.py
from django.contrib import admin
from .models import BrandAsset, ERPIntegration, CompanyBranding, Tracker, Announcement, ActivityLog

@admin.register(BrandAsset)
class BrandAssetAdmin(admin.ModelAdmin):
    list_display = ['name', 'type', 'uploaded_by', 'upload_date']
    list_filter = ['type', 'upload_date']
    search_fields = ['name', 'type']
    readonly_fields = ['uploaded_by', 'upload_date']

    def save_model(self, request, obj, form, change):
        if not change:  # Only set uploaded_by on create
            obj.uploaded_by = request.user
        super().save_model(request, obj, form, change)

@admin.register(ERPIntegration)
class ERPIntegrationAdmin(admin.ModelAdmin):
    list_display = ['system', 'status', 'last_sync', 'synced_by']
    list_filter = ['status', 'last_sync']
    search_fields = ['system']
    readonly_fields = ['synced_by', 'last_sync']

    def save_model(self, request, obj, form, change):
        if not change:
            obj.synced_by = request.user
        super().save_model(request, obj, form, change)

@admin.register(CompanyBranding)
class CompanyBrandingAdmin(admin.ModelAdmin):
    list_display = ['name', 'primary_color', 'secondary_color', 'created_by', 'created_at']
    list_filter = ['created_at']
    search_fields = ['name', 'tagline']
    readonly_fields = ['created_by', 'created_at']

    def save_model(self, request, obj, form, change):
        if not change:
            obj.created_by = request.user
        super().save_model(request, obj, form, change)

@admin.register(Tracker)
class TrackerAdmin(admin.ModelAdmin):
    list_display = ['device_id', 'asset', 'status', 'last_ping', 'created_by']
    list_filter = ['status', 'last_ping']
    search_fields = ['device_id', 'asset']
    readonly_fields = ['created_by', 'last_ping']

    def save_model(self, request, obj, form, change):
        if not change:
            obj.created_by = request.user
        super().save_model(request, obj, form, change)

@admin.register(Announcement)
class AnnouncementAdmin(admin.ModelAdmin):
    list_display = ['title', 'is_active', 'created_by', 'created_at']
    list_filter = ['is_active', 'created_at']
    search_fields = ['title', 'message']
    readonly_fields = ['created_by', 'created_at']
    
    def save_model(self, request, obj, form, change):
        if not change:
            obj.created_by = request.user
        super().save_model(request, obj, form, change)

@admin.register(ActivityLog)
class ActivityLogAdmin(admin.ModelAdmin):
    list_display = ['user', 'action', 'timestamp', 'description_truncated']
    list_filter = ['action', 'timestamp']
    search_fields = ['user__username', 'description']
    readonly_fields = ['user', 'action', 'description', 'timestamp']
    date_hierarchy = 'timestamp'
    
    def description_truncated(self, obj):
        return obj.description[:50] + '...' if len(obj.description) > 50 else obj.description
    description_truncated.short_description = 'Description'