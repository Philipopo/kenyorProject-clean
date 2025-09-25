from rest_framework import serializers
from .models import Conversation, Message
from django.contrib.auth import get_user_model

User = get_user_model()


class UserSearchSerializer(serializers.ModelSerializer):
    full_name = serializers.SerializerMethodField()
    profile_image = serializers.SerializerMethodField()
    initials = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = ['id', 'full_name', 'email', 'role', 'profile_image', 'initials']

    def get_full_name(self, obj):
        return (
            obj.full_name
            or getattr(obj.profile, 'full_name', None)
            or getattr(obj, 'name', None)
            or obj.email
        )

    def get_profile_image(self, obj):
        return obj.profile.profile_image.url if hasattr(obj, 'profile') and obj.profile.profile_image else None

    def get_initials(self, obj):
        name = (
            obj.full_name
            or getattr(obj.profile, 'full_name', None)
            or getattr(obj, 'name', None)
            or obj.email
        )
        return name[0].upper() if name else ''


class MessageSerializer(serializers.ModelSerializer):
    sender = serializers.SlugRelatedField(slug_field='email', queryset=User.objects.all())
    initials = serializers.SerializerMethodField()

    class Meta:
        model = Message
        fields = ['id', 'conversation', 'sender', 'initials', 'content', 'timestamp', 'is_read']

    def get_initials(self, obj):
        return obj.sender.full_name[0].upper() if obj.sender.full_name else obj.sender.email[0].upper()


class ConversationSerializer(serializers.ModelSerializer):
    participants = UserSearchSerializer(many=True)
    last_message = serializers.SerializerMethodField()
    unread_count = serializers.SerializerMethodField()

    class Meta:
        model = Conversation
        fields = ['id', 'participants', 'last_message', 'unread_count']

    def get_last_message(self, obj):
        last_msg = obj.messages.order_by('-timestamp').first()
        return MessageSerializer(last_msg).data if last_msg else None

    def get_unread_count(self, obj):
        request = self.context.get('request')
        user = request.user if request else None

        if user and user.is_authenticated:
            # Count unread messages
            unread = Message.objects.filter(
                conversation=obj,
                is_read=False
            ).exclude(sender=user)

            return unread.count()
        return 0
