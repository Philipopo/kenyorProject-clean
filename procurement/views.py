# procurement/views.py
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.db.models import Q, Sum
from django.http import HttpResponse
from django.template.loader import get_template
from django.conf import settings
import io
from xhtml2pdf import pisa
from datetime import datetime

from .models import (
    Requisition, RequisitionItem, PurchaseOrder, POItem, 
    Receiving, ReceivingItem, Vendor, ProcurementAuditLog
)
from .serializers import (
    RequisitionSerializer, PurchaseOrderSerializer, 
    ReceivingSerializer, VendorSerializer, ProcurementAuditLogSerializer
)
from accounts.permissions import DynamicPermission
from rest_framework.pagination import PageNumberPagination

class StandardResultsSetPagination(PageNumberPagination):
    page_size = 10
    page_size_query_param = 'page_size'
    max_page_size = 100

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
        queryset = Vendor.objects.all()
        search = self.request.query_params.get('search', None)
        if search:
            queryset = queryset.filter(Q(name__icontains=search) | Q(contact_person__icontains=search))
        return queryset

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)

    def perform_update(self, serializer):
        serializer.save(created_by=self.request.user)

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
        queryset = Requisition.objects.select_related('requested_by', 'created_by', 'approved_by')
        search = self.request.query_params.get('search', None)
        if search:
            queryset = queryset.filter(
                Q(code__icontains=search) |
                Q(department__icontains=search) |
                Q(purpose__icontains=search)
            )
        return queryset

    def perform_create(self, serializer):
        serializer.save(
            created_by=self.request.user,
            requested_by=self.request.user
        )

    def perform_update(self, serializer):
        serializer.save(created_by=self.request.user)

    @action(detail=True, methods=['post'])
    def approve(self, request, pk=None):
        requisition = self.get_object()
        if not requisition.can_approve(request.user):
            return Response({'error': 'You do not have permission to approve this requisition.'}, 
                          status=status.HTTP_403_FORBIDDEN)
        
        requisition.status = 'approved'
        requisition.approved_by = request.user
        requisition.approved_at = datetime.now()
        requisition.save()
        
        # Create audit log
        ProcurementAuditLog.objects.create(
            user=request.user,
            action='approve',
            model_name='Requisition',
            object_id=requisition.id,
            details={'status': 'approved'}
        )
        
        return Response({'status': 'approved'})

    @action(detail=True, methods=['post'])
    def reject(self, request, pk=None):
        requisition = self.get_object()
        if not requisition.can_approve(request.user):
            return Response({'error': 'You do not have permission to reject this requisition.'}, 
                          status=status.HTTP_403_FORBIDDEN)
        
        requisition.status = 'rejected'
        requisition.save()
        
        ProcurementAuditLog.objects.create(
            user=request.user,
            action='reject',
            model_name='Requisition',
            object_id=requisition.id,
            details={'status': 'rejected'}
        )
        
        return Response({'status': 'rejected'})

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
        queryset = PurchaseOrder.objects.select_related(
            'vendor', 'created_by', 'approved_by', 'requisition'
        ).prefetch_related('items__item')
        search = self.request.query_params.get('search', None)
        if search:
            queryset = queryset.filter(
                Q(code__icontains=search) |
                Q(vendor__name__icontains=search) |
                Q(department__icontains=search)
            )
        return queryset

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)

    def perform_update(self, serializer):
        serializer.save(created_by=self.request.user)

    @action(detail=True, methods=['post'])
    def approve(self, request, pk=None):
        po = self.get_object()
        if not po.can_approve(request.user):
            return Response({'error': 'You do not have permission to approve this purchase order.'}, 
                          status=status.HTTP_403_FORBIDDEN)
        
        po.status = 'approved'
        po.approved_by = request.user
        po.approved_at = datetime.now()
        po.save()
        
        ProcurementAuditLog.objects.create(
            user=request.user,
            action='approve',
            model_name='PurchaseOrder',
            object_id=po.id,
            details={'status': 'approved'}
        )
        
        return Response({'status': 'approved'})

    @action(detail=True, methods=['get'])
    def export_pdf(self, request, pk=None):
        """Export Purchase Order as PDF"""
        po = self.get_object()
        
        # Render HTML template
        template = get_template('procurement/po_pdf.html')
        context = {
            'po': po,
            'company_name': getattr(settings, 'COMPANY_NAME', 'Your Company'),
            'company_address': getattr(settings, 'COMPANY_ADDRESS', ''),
            'company_phone': getattr(settings, 'COMPANY_PHONE', ''),
            'company_email': getattr(settings, 'COMPANY_EMAIL', ''),
        }
        html = template.render(context)
        
        # Generate PDF
        response = HttpResponse(content_type='application/pdf')
        response['Content-Disposition'] = f'attachment; filename="PO_{po.code}.pdf"'
        
        pisa_status = pisa.CreatePDF(html, dest=response)
        if pisa_status.err:
            return Response({'error': 'Error generating PDF'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        
        return response

class ReceivingViewSet(viewsets.ModelViewSet):
    queryset = Receiving.objects.all()
    serializer_class = ReceivingSerializer
    permission_classes = [IsAuthenticated, DynamicPermission]
    page_permission_name = 'receiving'
    pagination_class = StandardResultsSetPagination
    required_permissions = {
        'create': 'create_receiving',
        'update': 'update_receiving',
        'partial_update': 'update_receiving',
        'destroy': 'delete_receiving',
    }

    def get_queryset(self):
        queryset = Receiving.objects.select_related(
            'po', 'po__vendor', 'received_by', 'created_by'
        ).prefetch_related('items__po_item__item')
        search = self.request.query_params.get('search', None)
        if search:
            queryset = queryset.filter(
                Q(grn__icontains=search) |
                Q(po__code__icontains=search) |
                Q(invoice_number__icontains=search)
            )
        return queryset

    def perform_create(self, serializer):
        serializer.save(
            created_by=self.request.user,
            received_by=self.request.user
        )

    def perform_update(self, serializer):
        serializer.save(created_by=self.request.user)

class ProcurementAuditLogViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = ProcurementAuditLog.objects.all()
    serializer_class = ProcurementAuditLogSerializer
    permission_classes = [IsAuthenticated, DynamicPermission]
    page_permission_name = 'procurement_audit_logs'
    pagination_class = StandardResultsSetPagination

    def get_queryset(self):
        queryset = ProcurementAuditLog.objects.select_related('user')
        return queryset