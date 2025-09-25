from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import DashboardMetricsView, UserDwellTimeListView, UserEOQReportListView, UserStockAnalyticsListView, EOQReportV2ViewSet

router = DefaultRouter()
router.register(r'eoq-v2', EOQReportV2ViewSet, basename='eoq-v2')

urlpatterns = [
    path('dashboard/', DashboardMetricsView.as_view(), name='dashboard-metrics'),
    path('dwell/', UserDwellTimeListView.as_view(), name='dwell-time-list'),
    path('eoq/', UserEOQReportListView.as_view(), name='eoq-report-list'),
    path('stock/', UserStockAnalyticsListView.as_view(), name='stock-analytics'),
    path('', include(router.urls)),
]