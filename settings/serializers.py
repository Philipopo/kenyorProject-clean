#settinhgs serializer.py



from rest_framework import serializers
from .models import BrandAsset, ERPIntegration, Tracker, CompanyBranding, Announcement, ActivityLog


class BrandAssetSerializer(serializers.ModelSerializer):
    class Meta:
        model = BrandAsset
        fields = '__all__'
        read_only_fields = ['uploaded_by', 'upload_date']


class ERPIntegrationSerializer(serializers.ModelSerializer):
    class Meta:
        model = ERPIntegration
        fields = '__all__'
        read_only_fields = ['synced_by', 'last_sync']


class TrackerSerializer(serializers.ModelSerializer):
    class Meta:
        model = Tracker
        fields = '__all__'
        read_only_fields = ['created_by', 'last_ping']


class CompanyBrandingSerializer(serializers.ModelSerializer):
    class Meta:
        model = CompanyBranding
        fields = ['id', 'name', 'logo', 'primary_color', 'secondary_color', 'tagline', 'created_by', 'created_at']
        read_only_fields = ['created_by', 'created_at']


class ActivityLogSerializer(serializers.ModelSerializer):
    user_name = serializers.CharField(source="user.username", read_only=True)

    class Meta:
        model = ActivityLog
        fields = ['id', 'user', 'user_name', 'action', 'description', 'timestamp']
        read_only_fields = ['user', 'timestamp']


class AnnouncementSerializer(serializers.ModelSerializer):
    created_by = serializers.StringRelatedField(read_only=True)  # ✅ ADD THIS
    
    class Meta:
        model = Announcement
        fields = "__all__"
        read_only_fields = ["created_by", "created_at"]
