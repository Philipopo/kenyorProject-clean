from rest_framework import serializers
from .models import AuditLog

class AuditLogSerializer(serializers.ModelSerializer):
    user = serializers.StringRelatedField()  # returns user's email or name

    class Meta:
        model = AuditLog
        fields = ['id', 'action', 'user', 'description', 'timestamp']
