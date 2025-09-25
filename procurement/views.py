# procurement/views.py
from rest_framework import viewsets
from rest_framework.permissions import IsAuthenticated
from .models import Requisition, PurchaseOrder, POItem, Receiving, GoodsReceipt, Vendor
from .serializers import (
    RequisitionSerializer,
    PurchaseOrderSerializer,
    POItemSerializer,
    ReceivingSerializer,
    GoodsReceiptSerializer,
    VendorSerializer,
)
from accounts.permissions import DynamicPermission
from rest_framework.pagination import PageNumberPagination
from django.db.models import Q
from django.utils import timezone

class StandardResultsSetPagination(PageNumberPagination):
    page_size = 10
    page_size_query_param = 'page_size'
    max_page_size = 100

class RequisitionViewSet(viewsets.ModelViewSet):
    queryset = Requisition.objects.all()
    serializer_class = RequisitionSerializer
    permission_classes = [IsAuthenticated, DynamicPermission]
    page_permission_name = 'requisitions'
    pagination_class = StandardResultsSetPagination
    required_permissions = {
        'create': 'create_requisition',
        'update': 'update_requisition',
        'partial_update': 'update_requisition',
        'destroy': 'delete_requisition',
    }

    def get_queryset(self):
        queryset = super().get_queryset()
        search = self.request.query_params.get('search', None)
        if search:
            queryset = queryset.filter(
                Q(code__icontains=search) |
                Q(item__icontains=search) |
                Q(department__icontains=search)
            )
        return queryset

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)

    def perform_update(self, serializer):
        serializer.save(created_by=self.request.user)

class VendorViewSet(viewsets.ModelViewSet):
    queryset = Vendor.objects.all()
    serializer_class = VendorSerializer
    permission_classes = [IsAuthenticated, DynamicPermission]
    page_permission_name = 'vendors'
    pagination_class = StandardResultsSetPagination
    required_permissions = {
        'create': 'add_vendor',
        'update': 'update_vendor',
        'partial_update': 'update_vendor',
        'destroy': 'delete_vendor',
    }

    def get_queryset(self):
        queryset = super().get_queryset()
        search = self.request.query_params.get('search', None)
        if search:
            queryset = queryset.filter(Q(name__icontains=search))
        return queryset

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)

    def perform_update(self, serializer):
        serializer.save(created_by=self.request.user)

class PurchaseOrderViewSet(viewsets.ModelViewSet):
    queryset = PurchaseOrder.objects.all()
    serializer_class = PurchaseOrderSerializer
    permission_classes = [IsAuthenticated, DynamicPermission]
    page_permission_name = 'purchase_orders'
    pagination_class = StandardResultsSetPagination
    required_permissions = {
        'create': 'create_purchase_order',
        'update': 'update_purchase_order',
        'partial_update': 'update_purchase_order',
        'destroy': 'delete_purchase_order',
    }

    def get_queryset(self):
        queryset = super().get_queryset()
        search = self.request.query_params.get('search', None)
        if search:
            queryset = queryset.filter(Q(item_name__icontains=search))
        return queryset

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)

    def perform_update(self, serializer):
        serializer.save(created_by=self.request.user)

class POItemViewSet(viewsets.ModelViewSet):
    queryset = POItem.objects.all()
    serializer_class = POItemSerializer
    permission_classes = [IsAuthenticated, DynamicPermission]
    page_permission_name = 'po_items'
    pagination_class = StandardResultsSetPagination
    required_permissions = {
        'create': 'create_po_item',
        'update': 'update_po_item',
        'partial_update': 'update_po_item',
        'destroy': 'delete_po_item',
    }

    def get_queryset(self):
        queryset = super().get_queryset()
        search = self.request.query_params.get('search', None)
        if search:
            queryset = queryset.filter(
                Q(name__icontains=search) |
                Q(po__code__icontains=search)
            )
        return queryset

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)

    def perform_update(self, serializer):
        serializer.save(created_by=self.request.user)

class ReceivingViewSet(viewsets.ModelViewSet):
    queryset = Receiving.objects.all()
    serializer_class = ReceivingSerializer
    permission_classes = [IsAuthenticated, DynamicPermission]
    page_permission_name = 'receiving'
    pagination_class = StandardResultsSetPagination
    required_permissions = {
        'create': 'create_receiving',
        'update': 'update Receiving',
        'partial_update': 'update_receiving',
        'destroy': 'delete_receiving',
    }

    def get_queryset(self):
        queryset = super().get_queryset()
        search = self.request.query_params.get('search', None)
        if search:
            queryset = queryset.filter(Q(grn__icontains=search))
        return queryset

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)

    def perform_update(self, serializer):
        serializer.save(created_by=self.request.user)

class GoodsReceiptViewSet(viewsets.ModelViewSet):
    queryset = GoodsReceipt.objects.all()
    serializer_class = GoodsReceiptSerializer
    permission_classes = [IsAuthenticated, DynamicPermission]
    page_permission_name = 'goods_receipts'
    pagination_class = StandardResultsSetPagination
    required_permissions = {
        'create': 'create_goods_receipt',
        'update': 'update_goods_receipt',
        'partial_update': 'update_goods_receipt',
        'destroy': 'delete_goods_receipt',
    }

    def get_queryset(self):
        queryset = super().get_queryset()
        search = self.request.query_params.get('search', None)
        if search:
            queryset = queryset.filter(
                Q(po_code__icontains=search) |
                Q(grn_code__icontains=search) |
                Q(invoice_code__icontains=search)
            )
        return queryset

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)

    def perform_update(self, serializer):
        serializer.save(created_by=self.request.user)