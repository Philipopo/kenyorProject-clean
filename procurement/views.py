# procurement/views.py
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.db.models import Q, Sum
from django.http import HttpResponse
from django.conf import settings
import io
from datetime import datetime

# ReportLab imports for PDF generation (no Cairo needed)
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
)
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from io import BytesIO

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
        """Export Purchase Order as PDF using reportlab (no Cairo or xhtml2pdf needed)"""
        po = self.get_object()
        
        # Create a bytes buffer for the PDF
        buffer = BytesIO()
        doc = SimpleDocTemplate(
            buffer,
            pagesize=letter,
            topMargin=0.5 * inch,
            bottomMargin=0.5 * inch,
            leftMargin=0.75 * inch,
            rightMargin=0.75 * inch
        )
        elements = []
        
        styles = getSampleStyleSheet()
        title_style = ParagraphStyle(
            'CustomTitle',
            parent=styles['Heading1'],
            fontSize=16,
            spaceAfter=12,
            alignment=1  # center
        )
        normal_style = styles['Normal']
        
        # === Company Information ===
        company_name = getattr(settings, 'COMPANY_NAME', 'Your Company')
        company_address = getattr(settings, 'COMPANY_ADDRESS', '')
        company_phone = getattr(settings, 'COMPANY_PHONE', '')
        company_email = getattr(settings, 'COMPANY_EMAIL', '')
        
        elements.append(Paragraph(company_name, title_style))
        if company_address:
            elements.append(Paragraph(company_address, normal_style))
        if company_phone:
            elements.append(Paragraph(f"Phone: {company_phone}", normal_style))
        if company_email:
            elements.append(Paragraph(f"Email: {company_email}", normal_style))
        elements.append(Spacer(1, 14))
        
        # === Purchase Order Header ===
        elements.append(Paragraph(f"Purchase Order #{po.code}", 
                                 ParagraphStyle('POHeader', parent=styles['Heading2'], fontSize=14)))
        elements.append(Spacer(1, 12))
        
        # === PO Details Table ===
        po_data = [
            ["Date:", po.created_at.strftime('%Y-%m-%d')],
            ["Department:", po.department or "N/A"],
            ["Vendor:", po.vendor.name if po.vendor else "N/A"],
            ["Status:", po.get_status_display()],
        ]
        if po.approved_at:
            po_data.append(["Approved At:", po.approved_at.strftime('%Y-%m-%d')])
        
        po_table = Table(po_data, colWidths=[1.8 * inch, 4.0 * inch])
        po_table.setStyle(TableStyle([
            ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('FONTSIZE', (0, 0), (-1, -1), 10),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
            ('TOPPADDING', (0, 0), (-1, -1), 3),
        ]))
        elements.append(po_table)
        elements.append(Spacer(1, 18))
        
        # === Items Section ===
        elements.append(Paragraph("Items", ParagraphStyle('ItemsHeader', parent=styles['Heading3'])))
        elements.append(Spacer(1, 6))
        
        # Table header
        item_data = [["Item", "Description", "Qty", "Unit Price", "Total"]]
        
        # Add each PO item
        for item in po.items.all():
            total = item.quantity * item.unit_price
            item_data.append([
                item.item.name if item.item else "N/A",
                item.description or "",
                str(item.quantity),
                f"{item.unit_price:.2f}",
                f"{total:.2f}"
            ])
        
        # Add total row
        total_amount = sum(item.quantity * item.unit_price for item in po.items.all())
        item_data.append(["", "", "", "Total:", f"{total_amount:.2f}"])
        
        # Create and style items table
        item_table = Table(
            item_data,
            colWidths=[1.2 * inch, 2.3 * inch, 0.6 * inch, 0.8 * inch, 0.8 * inch]
        )
        item_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.lightgrey),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.black),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('ALIGN', (-2, 1), (-1, -1), 'RIGHT'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 9),
            ('GRID', (0, 0), (-1, -2), 0.5, colors.grey),
            ('LINEABOVE', (0, -1), (-1, -1), 1, colors.black),
            ('FONTNAME', (0, -1), (-1, -1), 'Helvetica-Bold'),
            ('TOPPADDING', (0, 0), (-1, -1), 4),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
        ]))
        elements.append(item_table)
        elements.append(Spacer(1, 24))
        
        # Optional: Add notes or footer
        if po.notes:
            elements.append(Paragraph("<b>Notes:</b>", ParagraphStyle('NotesHeader', parent=styles['Normal'], fontName='Helvetica-Bold')))
            elements.append(Paragraph(po.notes, normal_style))
        
        # Build PDF
        doc.build(elements)
        
        # Prepare HTTP response
        buffer.seek(0)
        response = HttpResponse(buffer.getvalue(), content_type='application/pdf')
        response['Content-Disposition'] = f'attachment; filename="PO_{po.code}.pdf"'
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