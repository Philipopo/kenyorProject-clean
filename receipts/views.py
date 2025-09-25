# receipts/views.py
from rest_framework.viewsets import ModelViewSet
from rest_framework.permissions import IsAuthenticated
from rest_framework.pagination import PageNumberPagination
from django.db.models import Q
from .models import Receipt, StockReceipt, SigningReceipt
from .serializers import ReceiptSerializer, StockReceiptSerializer, SigningReceiptSerializer
from accounts.permissions import DynamicPermission

class StandardResultsSetPagination(PageNumberPagination):
    page_size = 10
    page_size_query_param = 'page_size'
    max_page_size = 100

class ReceiptViewSet(ModelViewSet):
    queryset = Receipt.objects.all()
    serializer_class = ReceiptSerializer
    permission_classes = [IsAuthenticated, DynamicPermission]
    page_permission_name = 'receipt_archive'
    required_permissions = {
        'create': 'create_receipt',
        'update': 'update_receipt',
        'partial_update': 'update_receipt',
        'destroy': 'delete_receipt',
    }
    pagination_class = StandardResultsSetPagination

    def get_queryset(self):
        queryset = Receipt.objects.filter(created_by=self.request.user)
        search = self.request.query_params.get('search', None)
        if search:
            queryset = queryset.filter(Q(reference__icontains=search) | Q(issued_by__icontains=search))
        return queryset.order_by('-created_at')

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)

    def perform_update(self, serializer):
        serializer.save(created_by=self.request.user)

class StockReceiptViewSet(ModelViewSet):
    queryset = StockReceipt.objects.all()
    serializer_class = StockReceiptSerializer
    permission_classes = [IsAuthenticated, DynamicPermission]
    page_permission_name = 'stock_receipts'
    required_permissions = {
        'create': 'create_stock_receipt',
        'update': 'update_stock_receipt',
        'partial_update': 'update_stock_receipt',
        'destroy': 'delete_stock_receipt',
    }
    pagination_class = StandardResultsSetPagination

    def get_queryset(self):
        queryset = StockReceipt.objects.filter(created_by=self.request.user)
        search = self.request.query_params.get('search', None)
        if search:
            queryset = queryset.filter(Q(item__icontains=search) | Q(location__icontains=search))
        return queryset.order_by('-created_at')

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)

    def perform_update(self, serializer):
        serializer.save(created_by=self.request.user)

class SigningReceiptViewSet(ModelViewSet):
    queryset = SigningReceipt.objects.all()
    serializer_class = SigningReceiptSerializer
    permission_classes = [IsAuthenticated, DynamicPermission]
    page_permission_name = 'signing_receipts'
    required_permissions = {
        'create': 'create_signing_receipt',
        'update': 'update_signing_receipt',
        'partial_update': 'update_signing_receipt',
        'destroy': 'delete_signing_receipt',
    }
    pagination_class = StandardResultsSetPagination

    def get_queryset(self):
        queryset = SigningReceipt.objects.filter(created_by=self.request.user)
        search = self.request.query_params.get('search', None)
        if search:
            queryset = queryset.filter(Q(recipient__icontains=search) | Q(signed_by__icontains=search))
        return queryset.order_by('-created_at')

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)

    def perform_update(self, serializer):
        serializer.save(created_by=self.request.user)