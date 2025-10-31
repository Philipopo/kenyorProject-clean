from django.urls import path
from .views import (
    InventoryAnalyticsView,
    ProcurementAnalyticsView,
    RentalsAnalyticsView,
    UnifiedAnalyticsView,
    ExportAnalyticsPDFView,
)

urlpatterns = [
    path('inventory/', InventoryAnalyticsView.as_view(), name='analytics-inventory'),
    path('procurement/', ProcurementAnalyticsView.as_view(), name='analytics-procurement'),
    path('rentals/', RentalsAnalyticsView.as_view(), name='analytics-rentals'),
    path('unified/', UnifiedAnalyticsView.as_view(), name='analytics-unified'),
    path('export-pdf/', ExportAnalyticsPDFView.as_view(), name='analytics-export-pdf'),
]