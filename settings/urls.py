# settings/urls.py
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views

router = DefaultRouter()
router.register(r'company-branding', views.CompanyBrandingViewSet, basename='company-branding')
router.register(r'announcements', views.AnnouncementViewSet, basename='announcement')  # ✅ ADDED

urlpatterns = [
    path('', include(router.urls)),  # This must come FIRST to include both ViewSets
    path('assets/', views.BrandAssetListCreateView.as_view(), name='brand-assets'),
    path('erp/', views.ERPIntegrationListCreateView.as_view(), name='erp'),
    path('tracker/', views.TrackerListCreateView.as_view(), name='tracker'),
]