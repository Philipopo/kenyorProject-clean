from rest_framework import viewsets
from .models import ProductInflow, ProductOutflow
from .serializers import ProductInflowSerializer, ProductOutflowSerializer
from accounts.permissions import DynamicPermission
from rest_framework.pagination import PageNumberPagination

class ProductInflowViewSet(viewsets.ModelViewSet):
    serializer_class = ProductInflowSerializer
    permission_classes = [DynamicPermission]
    page_permission_name = "product_documentation_new"

    def get_queryset(self):
        return ProductInflow.objects.select_related(
            'item', 
            'created_by',
            'created_by__profile'
        ).prefetch_related('serial_numbers').order_by('-id')  # Newest first

    def get_serializer_context(self):
        return {'request': self.request}

class StandardResultsSetPagination(PageNumberPagination):
    page_size = 10
    page_size_query_param = 'page_size'
    max_page_size = 100

class ProductOutflowViewSet(viewsets.ModelViewSet):
    serializer_class = ProductOutflowSerializer
    permission_classes = [DynamicPermission]
    page_permission_name = "product_documentation_new"
    pagination_class = StandardResultsSetPagination  # ✅ ADD THIS

    def get_queryset(self):
        return ProductOutflow.objects.select_related(
            'product__item',
            'responsible_staff',
            'responsible_staff__profile'
        ).order_by('-id')