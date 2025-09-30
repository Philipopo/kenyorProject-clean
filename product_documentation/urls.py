# product_documentation/urls.py

from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import ProductInflowViewSet, ProductOutflowViewSet
from .models import ProductDocumentationLog
from rest_framework.viewsets import ReadOnlyModelViewSet
from rest_framework.permissions import IsAuthenticated
from .serializers import ProductInflowSerializer, ProductOutflowSerializer

class LogViewSet(ReadOnlyModelViewSet):
    permission_classes = [IsAuthenticated]
    serializer_class = serializers.Serializer  # Minimal

    def get_queryset(self):
        return ProductDocumentationLog.objects.all().order_by('-timestamp')

    def list(self, request, *args, **kwargs):
        logs = self.get_queryset()
        data = [
            {
                "user": log.user.name if log.user else "Unknown",
                "action": log.action,
                "model": log.model_name,
                "object": log.object_repr,
                "timestamp": log.timestamp.strftime("%b %d, %Y %I:%M%p")
            }
            for log in logs
        ]
        return Response(data)

router = DefaultRouter()
router.register(r'inflows', ProductInflowViewSet, basename='inflow')
router.register(r'outflows', ProductOutflowViewSet, basename='outflow')
router.register(r'logs', LogViewSet, basename='product-doc-logs')

urlpatterns = [
    path('', include(router.urls)),
]