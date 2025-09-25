from rest_framework import serializers
from django.contrib.auth import get_user_model
from .models import UserProfile, PagePermission, ActionPermission, ApiKey

User = get_user_model()

class PagePermissionSerializer(serializers.ModelSerializer):
    class Meta:
        model = PagePermission
        fields = ['id', 'page_name', 'min_role']

class ActionPermissionSerializer(serializers.ModelSerializer):
    class Meta:
        model = ActionPermission
        fields = ['id', 'action_name', 'min_role']

class RegisterSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True)
    class Meta:
        model = User
        fields = ['email', 'name', 'password', 'role']
    def create(self, validated_data):
        return User.objects.create_user(**validated_data)

class UserSerializer(serializers.ModelSerializer):
    profile = serializers.SerializerMethodField()
    class Meta:
        model = User
        fields = ['id', 'email', 'name', 'role', 'profile']
    def get_profile(self, obj):
        profile = obj.profile
        return {
            'full_name': profile.full_name or obj.name or obj.email.split('@')[0],
            'profile_image': profile.profile_image.url if profile.profile_image else None,
            'state': profile.state
        }

class UserListSerializer(serializers.ModelSerializer):
    status = serializers.SerializerMethodField()
    full_name = serializers.SerializerMethodField()
    class Meta:
        model = User
        fields = ['id', 'full_name', 'email', 'role', 'status']
    def get_full_name(self, obj):
        return obj.name
    def get_status(self, obj):
        return "Active" if obj.is_active else "Inactive"

class ProfileSerializer(serializers.ModelSerializer):
    email = serializers.EmailField(source='user.email', read_only=True)
    name = serializers.CharField(source='user.name', read_only=True)
    role = serializers.CharField(source='user.role', read_only=True)
    full_name = serializers.CharField(max_length=255, required=False, allow_blank=True)
    class Meta:
        model = UserProfile
        fields = ['email', 'name', 'full_name', 'profile_image', 'role', 'state']
        read_only_fields = ['email', 'name', 'role']

class ProfilePictureUploadSerializer(serializers.ModelSerializer):
    class Meta:
        model = UserProfile
        fields = ['profile_image']

class ForgotPasswordSerializer(serializers.Serializer):
    email = serializers.EmailField()

class ResetPasswordSerializer(serializers.Serializer):
    new_password = serializers.CharField(min_length=6, write_only=True)
    token = serializers.CharField()
    uid = serializers.CharField()


    

class ApiKeySerializer(serializers.ModelSerializer):
    created_by_email = serializers.EmailField(source='created_by.email', read_only=True)
    created_by_full_name = serializers.SerializerMethodField()

    class Meta:
        model = ApiKey
        fields = ['id', 'name', 'key', 'user', 'created_by_email', 'created_by_full_name', 'created_at', 'is_active', 'is_viewed']
        read_only_fields = ['id', 'key', 'created_at', 'created_by_email', 'created_by_full_name', 'is_viewed', 'user']
        extra_kwargs = {
            'name': {'required': False, 'allow_blank': True},
        }

    def get_created_by_full_name(self, obj):
        profile = UserProfile.objects.filter(user=obj.created_by).first()
        return profile.full_name if profile and profile.full_name else obj.created_by.name

    def validate(self, data):
        if self.context['request'].method == 'POST':
            data['created_by'] = self.context['request'].user
            if not data.get('name'):
                data['name'] = 'Unnamed'
        return data