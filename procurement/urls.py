# procurement/urls.py
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    RequisitionViewSet,
    PurchaseOrderViewSet,
    ReceivingViewSet,
    VendorViewSet,
    ProcurementAuditLogViewSet
)

router = DefaultRouter()
router.register('requisitions', RequisitionViewSet)
router.register('purchase-orders', PurchaseOrderViewSet)
router.register('receivings', ReceivingViewSet, basename='receiving')
router.register('vendors', VendorViewSet)
router.register('audit-logs', ProcurementAuditLogViewSet, basename='audit-logs')

urlpatterns = [
    path('', include(router.urls)),
]