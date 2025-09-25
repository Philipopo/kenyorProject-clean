# receipts/urls.py
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import ReceiptViewSet, StockReceiptViewSet, SigningReceiptViewSet

router = DefaultRouter()
router.register(r'receipts', ReceiptViewSet, basename='receipt')
router.register(r'stock', StockReceiptViewSet, basename='stock-receipt')
router.register(r'signing', SigningReceiptViewSet, basename='signing-receipt')

urlpatterns = [
    path('', include(router.urls)),
]