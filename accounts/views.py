import logging
import secrets
import string
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework_simplejwt.views import TokenObtainPairView
from rest_framework import generics, status, permissions, serializers, viewsets
from rest_framework.generics import CreateAPIView, DestroyAPIView
from rest_framework.parsers import MultiPartParser, FormParser
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.exceptions import TokenError
from rest_framework.decorators import api_view, permission_classes, action
from django.views.decorators.csrf import csrf_exempt
from .models import User, UserProfile, PagePermission, ActionPermission, ApiKey
from .serializers import (
    RegisterSerializer, UserSerializer, UserListSerializer, ProfileSerializer,
    ProfilePictureUploadSerializer, ForgotPasswordSerializer,
    ResetPasswordSerializer, PagePermissionSerializer, ActionPermissionSerializer, ApiKeySerializer
)
from .token_serializers import CustomTokenObtainPairSerializer
from .permissions import HasMinimumRole, APIKeyPermission
from django.contrib.auth.tokens import PasswordResetTokenGenerator
from django.utils.http import urlsafe_base64_encode, urlsafe_base64_decode
from django.utils.encoding import force_bytes, force_str
from django.conf import settings
from django.utils import timezone
import requests
from fuzzywuzzy import process

logger = logging.getLogger(__name__)

NIGERIAN_STATES = [
    ('Abia', 'Abia'), ('Adamawa', 'Adamawa'), ('Akwa Ibom', 'Akwa Ibom'), ('Anambra', 'Anambra'),
    ('Bauchi', 'Bauchi'), ('Bayelsa', 'Bayelsa'), ('Benue', 'Benue'), ('Borno', 'Borno'),
    ('Cross River', 'Cross River'), ('Delta', 'Delta'), ('Ebonyi', 'Ebonyi'), ('Edo', 'Edo'),
    ('Ekiti', 'Ekiti'), ('Enugu', 'Enugu'), ('FCT', 'Federal Capital Territory'),
    ('Gombe', 'Gombe'), ('Imo', 'Imo'), ('Jigawa', 'Jigawa'), ('Kaduna', 'Kaduna'),
    ('Kano', 'Kano'), ('Katsina', 'Katsina'), ('Kebbi', 'Kebbi'), ('Kogi', 'Kogi'),
    ('Kwara', 'Kwara'), ('Lagos', 'Lagos'), ('Nasarawa', 'Nasarawa'), ('Niger', 'Niger'),
    ('Ogun', 'Ogun'), ('Ondo', 'Ondo'), ('Osun', 'Osun'), ('Oyo', 'Oyo'),
    ('Plateau', 'Plateau'), ('Rivers', 'Rivers'), ('Sokoto', 'Sokoto'),
    ('Taraba', 'Taraba'), ('Yobe', 'Yobe'), ('Zamfara', 'Zamfara')
]

STATE_VARIATIONS = {
    'Lagos State': 'Lagos',
    'Abuja': 'FCT',
    'Federal Capital Territory': 'FCT',
    'Oyo State': 'Oyo',
    'Kano State': 'Kano',
    'Anambra State': 'Anambra',
    'Rivers State': 'Rivers',
    'Delta State': 'Delta',
    'Abuja Federal Capital Territory': 'FCT',
    'FCT Abuja': 'FCT',
    'Kaduna State': 'Kaduna',
    'Ogun State': 'Ogun',
}

ROLE_LEVELS = {
    "staff": 1,
    "finance_manager": 2,
    "operations_manager": 3,
    "md": 4,
    "admin": 5,
}

def get_user_role_level(user):
    return ROLE_LEVELS.get(getattr(user, 'role', 'staff').lower(), 0)

def get_page_required_level(page):
    perm = PagePermission.objects.filter(page_name=page).first()
    return ROLE_LEVELS.get(perm.min_role.lower(), 1) if perm else 1

def get_action_required_level(action_name: str) -> int:
    try:
        perm = ActionPermission.objects.get(action_name=action_name)
        return ROLE_LEVELS.get(perm.min_role.lower(), 1)
    except ActionPermission.DoesNotExist:
        return 1

def check_permission(user, page=None, action=None):
    logger.info(f"[check_permission] Checking for user: {user}, role: {getattr(user, 'role', 'None')}, page: {page}, action: {action}")
    user_level = get_user_role_level(user)
    if not user.is_authenticated:
        logger.warning("[check_permission] User not authenticated")
        raise permissions.PermissionDenied("User not authenticated")
    if page:
        required = get_page_required_level(page)
        if user_level < required:
            logger.warning(f"[check_permission] Denied: page {page} requires level {required}, user has {user_level}")
            raise permissions.PermissionDenied(f"Access denied: {page} requires role level {required}")
    if action:
        required = get_action_required_level(action)
        if user_level < required:
            logger.warning(f"[check_permission] Denied: action {action} requires level {required}, user has {user_level}")
            raise permissions.PermissionDenied(f"Access denied: {action} requires role level {required}")
    return True

class SomeProtectedView(APIView):
    permission_classes = [IsAuthenticated, HasMinimumRole]
    required_role_level = 2
    def get(self, request):
        return Response({"message": "Authorized access"})

class MeView(APIView):
    permission_classes = [IsAuthenticated]
    def get(self, request):
        user = request.user
        profile, _ = UserProfile.objects.get_or_create(user=user)
        return Response({
            "id": user.id,
            "email": user.email,
            "role": user.role,
            "name": profile.full_name or user.name or user.email.split('@')[0]
        })

class CustomTokenObtainPairView(TokenObtainPairView):
    serializer_class = CustomTokenObtainPairSerializer
    @classmethod
    def as_view(cls, **initkwargs):
        view = super().as_view(**initkwargs)
        return csrf_exempt(view)

class UserProfileView(generics.RetrieveUpdateAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = ProfileSerializer
    def get_object(self):
        check_permission(self.request.user, page='user_profile')
        profile, created = UserProfile.objects.get_or_create(user=self.request.user)
        return profile
    def perform_update(self, serializer):
        logger.info(f"[UserProfileView] Validated data: {serializer.validated_data}")
        profile = serializer.save()
        full_name = serializer.validated_data.get('full_name')
        if full_name:
            self.request.user.name = full_name
            self.request.user.full_name = full_name
            self.request.user.save()
            logger.info(f"[UserProfileView] Updated User.name and User.full_name to: {full_name}")

class ProfilePictureUploadView(APIView):
    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser]
    def post(self, request, *args, **kwargs):
        profile, created = UserProfile.objects.get_or_create(user=request.user)
        serializer = ProfilePictureUploadSerializer(profile, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response({
                "detail": "Profile image uploaded successfully.",
                "profile_image": serializer.data['profile_image']
            })
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

class UserListView(generics.ListAPIView):
    queryset = User.objects.all().order_by('id')
    serializer_class = UserListSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        # Only return active users who can be added to approval board
        return User.objects.filter(is_active=True).order_by('name', 'email')
    
    def list(self, request, *args, **kwargs):
        queryset = self.get_queryset()
        serializer = self.get_serializer(queryset, many=True)
        # Return in the format your frontend expects
        return Response({
            'results': serializer.data,
            'count': queryset.count()
        })

class RegisterView(APIView):
    permission_classes = [AllowAny]
    def post(self, request):
        serializer = RegisterSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response({"message": "User created successfully"})
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

class UserView(APIView):
    permission_classes = [IsAuthenticated]
    def get(self, request):
        serializer = UserSerializer(request.user)
        return Response(serializer.data)

class ChangePasswordSerializer(serializers.Serializer):
    old_password = serializers.CharField(required=True)
    new_password = serializers.CharField(required=True)

class ChangePasswordView(APIView):
    permission_classes = [IsAuthenticated]
    def post(self, request):
        serializer = ChangePasswordSerializer(data=request.data)
        if serializer.is_valid():
            if not request.user.check_password(serializer.validated_data['old_password']):
                return Response({'old_password': 'Incorrect'}, status=400)
            request.user.set_password(serializer.validated_data['new_password'])
            request.user.save()
            return Response({'detail': 'Password changed successfully'})
        return Response(serializer.errors, status=400)

class AdminCreateUserView(CreateAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = RegisterSerializer
    def post(self, request, *args, **kwargs):
        if request.user.role != 'admin':
            return Response({"detail": "Only admin users can create accounts."}, status=403)
        data = request.data.copy()
        data['password'] = 'Password10'
        serializer = self.get_serializer(data=data)
        if serializer.is_valid():
            serializer.save()
            return Response({"message": "User created successfully with default password 'Password10'"})
        return Response(serializer.errors, status=400)

class AdminDeleteUserView(DestroyAPIView):
    permission_classes = [IsAuthenticated]
    queryset = User.objects.all()
    lookup_field = 'id'
    def delete(self, request, *args, **kwargs):
        if request.user.role != 'admin':
            return Response({"detail": "Only admin users can delete accounts."}, status=403)
        return super().delete(request, *args, **kwargs)

class LogoutView(APIView):
    permission_classes = [IsAuthenticated]
    def post(self, request):
        try:
            refresh_token = request.data.get("refresh")
            if not refresh_token:
                return Response({"detail": "Refresh token is required."}, status=status.HTTP_400_BAD_REQUEST)
            token = RefreshToken(refresh_token)
            token.blacklist()
            return Response({"detail": "Successfully logged out."}, status=status.HTTP_205_RESET_CONTENT)
        except TokenError:
            return Response({"detail": "Invalid or expired token."}, status=status.HTTP_400_BAD_REQUEST)

class IsAdminRole(permissions.BasePermission):
    def has_permission(self, request, view):
        return request.user.is_authenticated and request.user.role == "admin"

class PagePermissionViewSet(viewsets.ModelViewSet):
    queryset = PagePermission.objects.all()
    serializer_class = PagePermissionSerializer
    permission_classes = [IsAuthenticated, IsAdminRole]
    def create(self, request, *args, **kwargs):
        data = request.data.copy()
        if "min_role" not in data:
            data["min_role"] = "staff"
        instance = PagePermission.objects.filter(page_name=data.get("page_name")).first()
        if instance:
            serializer = self.get_serializer(instance, data=data, partial=True)
            serializer.is_valid(raise_exception=True)
            serializer.save()
            return Response(serializer.data, status=status.HTTP_200_OK)
        serializer = self.get_serializer(data=data)
        serializer.is_valid(raise_exception=True)
        self.perform_create(serializer)
        return Response(serializer.data, status=status.HTTP_201_CREATED)

class ActionPermissionViewSet(viewsets.ModelViewSet):
    queryset = ActionPermission.objects.all()
    serializer_class = ActionPermissionSerializer
    permission_classes = [IsAuthenticated, IsAdminRole]
    def create(self, request, *args, **kwargs):
        data = request.data.copy()
        if "min_role" not in data:
            data["min_role"] = "staff"
        instance = ActionPermission.objects.filter(action_name=data.get("action_name")).first()
        if instance:
            serializer = self.get_serializer(instance, data=data, partial=True)
            serializer.is_valid(raise_exception=True)
            serializer.save()
            return Response(serializer.data, status=status.HTTP_200_OK)
        serializer = self.get_serializer(data=data)
        serializer.is_valid(raise_exception=True)
        self.perform_create(serializer)
        return Response(serializer.data, status=status.HTTP_201_CREATED)

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def page_allowed(request, page_name):
    try:
        permission = PagePermission.objects.get(page_name=page_name)
        user_role = request.user.role
        if ROLE_LEVELS.get(user_role, 0) >= ROLE_LEVELS.get(permission.min_role, 0):
            return Response({"allowed": True})
        else:
            return Response({"allowed": False, "reason": f"Requires {permission.min_role} role"})
    except PagePermission.DoesNotExist:
        return Response({"allowed": False, "reason": "page_not_configured"})

@api_view(["GET"])
@permission_classes([IsAuthenticated])
def action_allowed(request, action_name: str):
    try:
        action_perm = ActionPermission.objects.get(action_name=action_name)
    except ActionPermission.DoesNotExist:
        return Response({"allowed": False, "reason": "action_not_configured"})
    user_role = getattr(request.user, "role", "staff")
    user_level = ROLE_LEVELS.get(user_role.lower(), 0)
    required_level = ROLE_LEVELS.get(action_perm.min_role.lower(), 999)
    return Response({"allowed": user_level >= required_level})

class ForgotPasswordView(APIView):
    permission_classes = [AllowAny]
    def post(self, request):
        serializer = ForgotPasswordSerializer(data=request.data)
        if serializer.is_valid():
            email = serializer.validated_data['email']
            try:
                user = User.objects.get(email=email)
                token_generator = PasswordResetTokenGenerator()
                token = token_generator.make_token(user)
                uid = urlsafe_base64_encode(force_bytes(user.pk))
                reset_url = f"{settings.FRONTEND_URL}/reset-password/{uid}/{token}/"
                webhook_data = {
                    "email": user.email,
                    "reset_url": reset_url,
                    "full_name": user.name or user.email.split('@')[0]
                }
                try:
                    response = requests.post(settings.MAKE_WEBHOOK_URL, json=webhook_data)
                    response.raise_for_status()
                    return Response({"detail": "Password reset email sent."}, status=status.HTTP_200_OK)
                except requests.RequestException as e:
                    return Response({"detail": f"Failed to send email: {str(e)}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
            except User.DoesNotExist:
                return Response({"detail": "Email not found."}, status=status.HTTP_404_NOT_FOUND)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

class ResetPasswordView(APIView):
    permission_classes = [AllowAny]
    def post(self, request):
        serializer = ResetPasswordSerializer(data=request.data)
        if serializer.is_valid():
            try:
                uid = force_str(urlsafe_base64_decode(serializer.validated_data['uid']))
                user = User.objects.get(pk=uid)
                token = serializer.validated_data['token']
                token_generator = PasswordResetTokenGenerator()
                if token_generator.check_token(user, token):
                    user.set_password(serializer.validated_data['new_password'])
                    user.save()
                    return Response({"detail": "Password reset successfully."}, status=status.HTTP_200_OK)
                return Response({"detail": "Invalid or expired token."}, status=status.HTTP_400_BAD_REQUEST)
            except (User.DoesNotExist, ValueError):
                return Response({"detail": "Invalid user or token."}, status=status.HTTP_400_BAD_REQUEST)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)





class UpdateLocationView(APIView):
    permission_classes = [IsAuthenticated]
    def post(self, request):
        latitude = request.data.get('latitude')
        longitude = request.data.get('longitude')
        if not latitude or not longitude:
            return Response(
                {'error': 'Latitude and longitude are required'},
                status=400
            )
        try:
            response = requests.get(
                f'https://nominatim.openstreetmap.org/reverse?format=json&lat={latitude}&lon={longitude}',
                headers={'User-Agent': 'KenyonLTD/1.0 (contact@kenyonltd.com)'}
            )
            response.raise_for_status()
            data = response.json()
            logger.info(f"[UpdateLocationView] Nominatim response: {data}")
            state = data.get('address', {}).get('state', '') or data.get('address', {}).get('city', '')
            normalized_state = state.replace(' State', '').strip()
            matched_state = STATE_VARIATIONS.get(normalized_state, None) or STATE_VARIATIONS.get(state, None)
            if not matched_state:
                state_names = [short_name for short_name, _ in NIGERIAN_STATES]
                result = process.extractOne(normalized_state, state_names, score_cutoff=60)
                matched_state, score = result if result else ('Lagos', 0)
            else:
                score = 'exact'
            profile, _ = UserProfile.objects.get_or_create(user=request.user)
            profile.city = data.get('address', {}).get('city') or data.get('address', {}).get('town') or ''
            profile.state = matched_state
            profile.last_location_update = timezone.now()
            profile.save()
            logger.info(f"[UpdateLocationView] Updated location for user {request.user}: city={profile.city}, state={matched_state}, score={score}")
            return Response({'city': profile.city, 'state': profile.state}, status=200)
        except requests.RequestException as e:
            logger.error(f"[UpdateLocationView] Failed to fetch location data: {str(e)}")
            if response.status_code == 403:
                logger.warning("[UpdateLocationView] Nominatim 403 Forbidden: Check User-Agent or rate limits")
            return Response(
                {'error': f'Failed to fetch location data: {str(e)}'},
                status=500
            )





class AdminUpdateUserRoleView(APIView):
    permission_classes = [IsAuthenticated]

    def patch(self, request, user_id):
        if request.user.role != 'admin':
            return Response({"detail": "Only admin users can update roles."}, status=403)
        
        try:
            user = User.objects.get(id=user_id)
        except User.DoesNotExist:
            return Response({"detail": "User not found."}, status=404)

        new_role = request.data.get('role')
        if not new_role:
            return Response({"detail": "Role is required."}, status=400)

        # Get valid roles from the User model's 'role' field choices
        allowed_roles = [choice[0] for choice in User._meta.get_field('role').choices]
        if new_role not in allowed_roles:
            return Response({"detail": "Invalid role."}, status=400)

        user.role = new_role
        user.save(update_fields=['role'])
        return Response({"detail": f"Role updated to {new_role}."}, status=200)


class AdminResetUserPasswordView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, user_id):
        if request.user.role != 'admin':
            return Response({"detail": "Only admin users can reset passwords."}, status=403)
        
        try:
            user = User.objects.get(id=user_id)
        except User.DoesNotExist:
            return Response({"detail": "User not found."}, status=404)

        new_password = request.data.get('new_password')
        if not new_password or len(new_password) < 6:
            return Response({"detail": "Password must be at least 6 characters."}, status=400)

        user.set_password(new_password)
        user.save(update_fields=[])  # password is handled by set_password
        return Response({"detail": "Password reset successfully."}, status=200)




class ApiKeyViewSet(viewsets.ModelViewSet):
    queryset = ApiKey.objects.all()
    serializer_class = ApiKeySerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        logger.debug(f"[ApiKeyViewSet] Fetching API keys for user: {self.request.user.email}")
        return ApiKey.objects.filter(user=self.request.user)

    def create(self, request, *args, **kwargs):
        logger.debug(f"[ApiKeyViewSet] User {request.user.email} attempting to generate API key. Role: {request.user.role}")
        # Check permission
        try:
            action_perm = ActionPermission.objects.get(action_name='generate_api_key')
            user_level = ROLE_LEVELS.get(request.user.role.lower(), 0)
            required_level = ROLE_LEVELS.get(action_perm.min_role.lower(), 1)
            logger.debug(f"[ApiKeyViewSet] User level: {user_level}, Required level: {required_level}")
            if user_level < required_level:
                logger.warning(f"[ApiKeyViewSet] Permission denied for user {request.user.email}: requires {action_perm.min_role}")
                return Response(
                    {"error": f"Permission denied: requires {action_perm.min_role} role"},
                    status=status.HTTP_403_FORBIDDEN
                )
        except ActionPermission.DoesNotExist:
            logger.error(f"[ApiKeyViewSet] ActionPermission for 'generate_api_key' not found")
            return Response(
                {"error": "Action permission not configured for generate_api_key"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

        # Validate serializer
        serializer = self.get_serializer(data=request.data)
        try:
            serializer.is_valid(raise_exception=True)
        except serializers.ValidationError as e:
            logger.error(f"[ApiKeyViewSet] Serializer validation failed: {str(e)}")
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)

        # Create API key
        try:
            key = ''.join(secrets.choice(string.ascii_letters + string.digits) for _ in range(43))
            api_key = ApiKey.objects.create(
                user=request.user,
                name=serializer.validated_data.get('name', 'API Key'),
                key=key,
                created_by=request.user,
                is_active=True,
                is_viewed=False
            )
            logger.debug(f"[ApiKeyViewSet] Generated API key for user {request.user.email}: {api_key.name}")
            return Response(
                {"key": api_key.key, "name": api_key.name},
                status=status.HTTP_201_CREATED
            )
        except Exception as e:
            logger.error(f"[ApiKeyViewSet] Failed to create API key: {str(e)}")
            return Response(
                {"error": f"Failed to create API key: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    def destroy(self, request, *args, **kwargs):
        logger.debug(f"[ApiKeyViewSet] User {request.user.email} attempting to delete API key")
        try:
            action_perm = ActionPermission.objects.get(action_name='delete_api_key')
            user_level = ROLE_LEVELS.get(request.user.role.lower(), 0)
            required_level = ROLE_LEVELS.get(action_perm.min_role.lower(), 1)
            if user_level < required_level:
                logger.warning(f"[ApiKeyViewSet] Permission denied for user {request.user.email}: requires {action_perm.min_role}")
                return Response(
                    {"error": f"Permission denied: requires {action_perm.min_role} role"},
                    status=status.HTTP_403_FORBIDDEN
                )
        except ActionPermission.DoesNotExist:
            logger.error(f"[ApiKeyViewSet] ActionPermission for 'delete_api_key' not found")
            return Response(
                {"error": "Action permission not configured for delete_api_key"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
        return super().destroy(request, *args, **kwargs)

    def retrieve(self, request, *args, **kwargs):
        logger.debug(f"[ApiKeyViewSet] User {request.user.email} attempting to view API key")
        try:
            action_perm = ActionPermission.objects.get(action_name='view_api_key')
            user_level = ROLE_LEVELS.get(request.user.role.lower(), 0)
            required_level = ROLE_LEVELS.get(action_perm.min_role.lower(), 1)
            if user_level < required_level:
                logger.warning(f"[ApiKeyViewSet] Permission denied for user {request.user.email}: requires {action_perm.min_role}")
                return Response(
                    {"error": f"Permission denied: requires {action_perm.min_role} role"},
                    status=status.HTTP_403_FORBIDDEN
                )
        except ActionPermission.DoesNotExist:
            logger.error(f"[ApiKeyViewSet] ActionPermission for 'view_api_key' not found")
            return Response(
                {"error": "Action permission not configured for view_api_key"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
        return super().retrieve(request, *args, **kwargs)