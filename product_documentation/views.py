# product_documentation/views.py
from rest_framework import viewsets, permissions
from rest_framework.pagination import PageNumberPagination
from django.db.models import Q
from .models import ProductInflow, ProductOutflow
from .serializers import ProductInflowSerializer, ProductOutflowSerializer
from accounts.permissions import HasMinimumRole

class StandardResultsSetPagination(PageNumberPagination):
    page_size = 10
    page_size_query_param = 'page_size'
    max_page_size = 100

class ProductInflowViewSet(viewsets.ModelViewSet):
    queryset = ProductInflow.objects.all()
    serializer_class = ProductInflowSerializer
    permission_classes = [permissions.IsAuthenticated, HasMinimumRole]
    required_role_level = 2  # finance_manager or higher
    pagination_class = StandardResultsSetPagination

    def get_queryset(self):
        queryset = super().get_queryset()
        search = self.request.query_params.get('search', None)
        if search:
            queryset = queryset.filter(
                Q(item__name__icontains=search) |
                Q(batch__icontains=search) |
                Q(vendor__icontains=search)
            )
        return queryset

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)

    def perform_update(self, serializer):
        serializer.save(created_by=self.request.user)

class ProductOutflowViewSet(viewsets.ModelViewSet):
    queryset = ProductOutflow.objects.all()
    serializer_class = ProductOutflowSerializer
    permission_classes = [permissions.IsAuthenticated, HasMinimumRole]
    required_role_level = 2  # finance_manager or higher
    pagination_class = StandardResultsSetPagination

    def get_queryset(self):
        queryset = super().get_queryset()
        search = self.request.query_params.get('search', None)
        if search:
            queryset = queryset.filter(
                Q(customer_name__icontains=search) |
                Q(sales_order__icontains=search)
            )
        return queryset

    def perform_create(self, serializer):
        serializer.save(responsible_staff=self.request.user)

    def perform_update(self, serializer):
        serializer.save(responsible_staff=self.request.user)