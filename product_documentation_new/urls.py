from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import ProductInflowViewSet, ProductOutflowViewSet

router = DefaultRouter()
router.register(r'inflows', ProductInflowViewSet, basename='inflows')
router.register(r'outflows', ProductOutflowViewSet, basename='outflows')

urlpatterns = [
    path('', include(router.urls)),
]