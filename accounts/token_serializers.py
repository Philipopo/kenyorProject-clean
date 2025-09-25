from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from rest_framework import serializers
from accounts.models import User

class CustomTokenObtainPairSerializer(TokenObtainPairSerializer):
    username_field = User.EMAIL_FIELD  # this sets it to 'email'

    def validate(self, attrs):
        email = attrs.get("email")
        password = attrs.get("password")

        try:
            user = User.objects.get(email=email)
        except User.DoesNotExist:
            raise serializers.ValidationError("No user with this email.")

        if not user.check_password(password):
            raise serializers.ValidationError("Incorrect password.")

        data = super().validate(attrs)
        data["user"] = {
            "id": user.id,
            "email": user.email,
            "role": user.role,
            "name": user.name
        }
        return data
