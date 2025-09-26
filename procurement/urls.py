# procurement/urls.py
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    RequisitionViewSet,
    PurchaseOrderViewSet,
    ReceivingViewSet,
    VendorViewSet,
    ProcurementAuditLogViewSet,
    ApprovalBoardViewSet
)

router = DefaultRouter()
router.register('requisitions', RequisitionViewSet)
router.register('purchase-orders', PurchaseOrderViewSet)
router.register('receivings', ReceivingViewSet, basename='receiving')
router.register('vendors', VendorViewSet)
router.register('audit-logs', ProcurementAuditLogViewSet, basename='audit-logs')
router.register('approval-board', ApprovalBoardViewSet, basename='approval-board')

urlpatterns = [
    path('', include(router.urls)),
]