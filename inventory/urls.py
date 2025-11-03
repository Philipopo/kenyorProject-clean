from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    WarehouseViewSet, WarehouseAnalyticsView,
    StorageBinViewSet, ItemViewSet, StockRecordViewSet,
    StockMovementViewSet, InventoryAlertViewSet, ExpiryTrackedItemViewSet,
    StockInView, StockOutView, InventoryMetricsView, AnalyticsView,
    InventoryActivityLogViewSet, ImportCSVView, get_unique_states,
    get_unique_countries, warehouse_receipt_print, WarehouseReceiptPDFView,
    WarehouseReceiptViewSet, BulkDeleteItemsView
)
import logging

logger = logging.getLogger(__name__)

# Router
router = DefaultRouter()
router.register('warehouses', WarehouseViewSet, basename='warehouses')
router.register('bins', StorageBinViewSet, basename='bins')
router.register('items', ItemViewSet, basename='items')
router.register('stocks', StockRecordViewSet, basename='stocks')
router.register('movements', StockMovementViewSet, basename='movements')
router.register('alerts', InventoryAlertViewSet, basename='alerts')
router.register('expiry-tracked-items', ExpiryTrackedItemViewSet, basename='expiry-tracked-items')
router.register('activity-logs', InventoryActivityLogViewSet, basename='activity-logs')
router.register('receipts', WarehouseReceiptViewSet, basename='receipts')

# Log router URLs
logger.info(f"Registered router URLs: {router.urls}")

app_name = 'inventory'

urlpatterns = [
    path('', include(router.urls)),
    path('items/bulk-delete/', ItemViewSet.as_view({'post': 'bulk_delete'}), name='item-bulk-delete'),
    path('items/bulk-delete-alt/', BulkDeleteItemsView.as_view(), name='item-bulk-delete-alt'),
    path('items/import-csv/', ImportCSVView.as_view(), name='import-items-csv'),
    path('metrics/', InventoryMetricsView.as_view(), name='inventory-metrics'),
    path('stock-in/', StockInView.as_view(), name='stock-in'),
    path('stock-out/', StockOutView.as_view(), name='stock-out'),
    path('analytics/', AnalyticsView.as_view(), name='inventory-analytics'),
    path('warehouse-analytics/', WarehouseAnalyticsView.as_view(), name='warehouse-analytics'),
    path('warehouse-analytics/<int:warehouse_id>/', WarehouseAnalyticsView.as_view(), name='warehouse-analytics-detail'),
    path('warehouse-states/', get_unique_states, name='warehouse-states'),
    path('warehouse-countries/', get_unique_countries, name='warehouse-countries'),
    path('receipts/<int:receipt_id>/print/', warehouse_receipt_print, name='receipt-print'),
    path('receipts/<int:receipt_id>/pdf/', WarehouseReceiptPDFView.as_view(), name='warehouse-receipt-pdf'),
]