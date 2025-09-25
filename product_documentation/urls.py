# product_documentation/urls.py
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import ProductInflowViewSet, ProductOutflowViewSet

router = DefaultRouter()
router.register(r'inflows', ProductInflowViewSet, basename='inflow')
router.register(r'outflows', ProductOutflowViewSet, basename='outflow')

urlpatterns = [
    path('', include(router.urls)),
]