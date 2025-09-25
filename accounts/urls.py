from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    MeView, CustomTokenObtainPairView, RegisterView, UserView,
    ChangePasswordView, UserListView, AdminCreateUserView,
    AdminDeleteUserView, UserProfileView, ProfilePictureUploadView, LogoutView,
    PagePermissionViewSet, ActionPermissionViewSet, page_allowed, action_allowed,
    ForgotPasswordView, ResetPasswordView, UpdateLocationView, ApiKeyViewSet
)

router = DefaultRouter()
router.register(r'page-permissions', PagePermissionViewSet, basename='page-permissions')
router.register(r'action-permissions', ActionPermissionViewSet, basename='action-permissions')
router.register(r'api-keys', ApiKeyViewSet, basename='api-key')

urlpatterns = [
    path('me/', MeView.as_view(), name='me'),
    path('login/', CustomTokenObtainPairView.as_view(), name='login'),
    path('register/', RegisterView.as_view(), name='register'),
    path('user/', UserView.as_view(), name='user'),
    path('change-password/', ChangePasswordView.as_view(), name='change-password'),
    path('users/', UserListView.as_view(), name='users'),
    path('admin/create-user/', AdminCreateUserView.as_view(), name='admin-create-user'),
    path('admin/delete-user/<int:id>/', AdminDeleteUserView.as_view(), name='admin-delete-user'),
    path('profile/', UserProfileView.as_view(), name='profile'),  # Updated path
    path('profile/upload/', ProfilePictureUploadView.as_view(), name='profile-upload'),
    path('logout/', LogoutView.as_view(), name='logout'),
    path('forgot-password/', ForgotPasswordView.as_view(), name='forgot-password'),
    path('reset-password/', ResetPasswordView.as_view(), name='reset-password'),
    path('update_location/', UpdateLocationView.as_view(), name='update_location'),  # Updated path
    path('permissions/page/<str:page_name>/', page_allowed, name='page-allowed'),
    path('permissions/action/<str:action_name>/', action_allowed, name='action-allowed'),
    path('', include(router.urls)),
]