from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import WarehouseItemViewSet

router = DefaultRouter()
router.register(r'items', WarehouseItemViewSet, basename='warehouse-items')  # Added basename

app_name = 'warehouse_new'

urlpatterns = [
    path('', include(router.urls)),
]