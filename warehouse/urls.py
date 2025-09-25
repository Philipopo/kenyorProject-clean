# warehouse/urls.py
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import WarehouseItemViewSet

router = DefaultRouter()
router.register(r'items', WarehouseItemViewSet, basename='warehouse-item')

urlpatterns = [
    path('', include(router.urls)),
]