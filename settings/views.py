from django.shortcuts import render
from django.db.models import Q
from rest_framework import generics, permissions, viewsets
from rest_framework.pagination import PageNumberPagination
from rest_framework.permissions import IsAuthenticated

from .models import BrandAsset, ERPIntegration, CompanyBranding, Tracker, Announcement
from .serializers import (
    BrandAssetSerializer, ERPIntegrationSerializer, TrackerSerializer,
    CompanyBrandingSerializer, AnnouncementSerializer
)

from accounts.permissions import DynamicPermission
from activity_log.utils import log_activity

class BrandAssetListCreateView(generics.ListCreateAPIView):
    queryset = BrandAsset.objects.all()
    serializer_class = BrandAssetSerializer
    permission_classes = [IsAuthenticated, DynamicPermission]
    page_permission_name = 'branding'

    def perform_create(self, serializer):
        serializer.save(uploaded_by=self.request.user)


class ERPIntegrationListCreateView(generics.ListCreateAPIView):
    queryset = ERPIntegration.objects.all()
    serializer_class = ERPIntegrationSerializer
    permission_classes = [IsAuthenticated, DynamicPermission]
    page_permission_name = 'erp_integration'

    def perform_create(self, serializer):
        serializer.save(synced_by=self.request.user)


class TrackerListCreateView(generics.ListCreateAPIView):
    queryset = Tracker.objects.all()
    serializer_class = TrackerSerializer
    permission_classes = [IsAuthenticated, DynamicPermission]
    page_permission_name = 'trackers'

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)


class StandardResultsSetPagination(PageNumberPagination):
    page_size = 10
    page_size_query_param = 'page_size'
    max_page_size = 100


class CompanyBrandingViewSet(viewsets.ModelViewSet):
    queryset = CompanyBranding.objects.all()
    serializer_class = CompanyBrandingSerializer
    permission_classes = [IsAuthenticated, DynamicPermission]
    page_permission_name = 'branding'
    pagination_class = StandardResultsSetPagination

    def get_action_permission_name(self):
        # Map view actions to permission names
        action_map = {
            'create': 'create_branding',
            'update': 'update_branding',
        }
        return action_map.get(self.action)

    def get_queryset(self):
        queryset = super().get_queryset()
        search = self.request.query_params.get('search')
        if search:
            queryset = queryset.filter(
                Q(name__icontains=search) | Q(tagline__icontains=search)
            )
        return queryset

    def perform_create(self, serializer):
        instance = serializer.save(created_by=self.request.user)
        log_activity(
            user=self.request.user,
            app="settings",
            table="company_branding",
            action="create",
            description=f"Created company branding: {instance.name}"
        )

    def perform_update(self, serializer):
        instance = serializer.save(created_by=self.request.user)
        log_activity(
            user=self.request.user,
            app="settings",
            table="company_branding",
            action="update",
            description=f"Updated company branding: {instance.name}"
        )

    def perform_destroy(self, instance):
        log_activity(
            user=self.request.user,
            app="settings",
            table="company_branding",
            action="delete",
            description=f"Deleted company branding: {instance.name}"
        )
        instance.delete()


class AnnouncementViewSet(viewsets.ModelViewSet):
    queryset = Announcement.objects.all().order_by("-created_at")
    serializer_class = AnnouncementSerializer
    permission_classes = [IsAuthenticated, DynamicPermission]
    page_permission_name = 'announcement'

    def get_queryset(self):
        queryset = super().get_queryset()
        search = self.request.query_params.get('search')
        if search:
            queryset = queryset.filter(Q(title__icontains=search) | Q(message__icontains=search))
        return queryset

    def get_action_permission_name(self):
        # Map view actions to permission names
        action_map = {
            'create': 'create_announcement',
            'update': 'update_announcement',
            'partial_update': 'update_announcement',
            'destroy': 'delete_announcement',
        }
        return action_map.get(self.action)

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context['action'] = self.action
        return context

    def perform_create(self, serializer):
        instance = serializer.save(created_by=self.request.user)
        log_activity(
            user=self.request.user,
            app="settings",
            table="announcement",
            action="create",
            description=f"Created announcement: {instance.title}"
        )

    def perform_update(self, serializer):
        instance = serializer.save()
        log_activity(
            user=self.request.user,
            app="settings",
            table="announcement",
            action="update",
            description=f"Updated announcement: {instance.title}"
        )

    def perform_destroy(self, instance):
        log_activity(
            user=self.request.user,
            app="settings",
            table="announcement",
            action="delete",
            description=f"Deleted announcement: {instance.title}"
        )
        instance.delete()