# procurement/urls.py
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    VendorViewSet, RequisitionViewSet, PurchaseOrderViewSet, 
    ReceivingViewSet, ApprovalBoardViewSet, ProcurementAuditLogViewSet
)

router = DefaultRouter()
router.register('vendors', VendorViewSet, basename='vendors')
router.register('requisitions', RequisitionViewSet, basename='requisitions')
router.register('purchase-orders', PurchaseOrderViewSet, basename='purchase-orders')
router.register('receivings', ReceivingViewSet, basename='receivings')
router.register('approval-board', ApprovalBoardViewSet, basename='approval-board')
router.register('audit-logs', ProcurementAuditLogViewSet, basename='audit-logs')

urlpatterns = [
    path('', include(router.urls)),
]