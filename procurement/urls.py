# procurement/urls.py
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    RequisitionViewSet,
    PurchaseOrderViewSet,
    POItemViewSet,
    ReceivingViewSet,
    GoodsReceiptViewSet,
    VendorViewSet
)

router = DefaultRouter()
router.register('requisitions', RequisitionViewSet)
router.register('purchase-orders', PurchaseOrderViewSet)
router.register('po-items', POItemViewSet)
router.register('receivings', ReceivingViewSet, basename='receiving')
router.register('vendors', VendorViewSet)
router.register('goods-receipts', GoodsReceiptViewSet)

urlpatterns = [
    path('', include(router.urls)),
]