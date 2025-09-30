from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.db.models import Q, Sum
from django.http import HttpResponse
from django.conf import settings
from datetime import datetime
from io import BytesIO

# ReportLab imports for PDF generation
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
)
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch

from .models import (
    Requisition, RequisitionItem, PurchaseOrder, POItem, 
    Receiving, ReceivingItem, Vendor, ProcurementAuditLog, ApprovalBoard
)
from .serializers import (
    RequisitionSerializer, PurchaseOrderSerializer, 
    ReceivingSerializer, VendorSerializer, ProcurementAuditLogSerializer, ApprovalBoardSerializer
)
from accounts.permissions import DynamicPermission
from rest_framework.pagination import PageNumberPagination
from django.contrib.auth import get_user_model

User = get_user_model()

# Define pagination class FIRST, before any viewsets that use it
class StandardResultsSetPagination(PageNumberPagination):
    page_size = 10
    page_size_query_param = 'page_size'
    max_page_size = 100

# TEMPORARILY COMMENTED OUT - Audit logging disabled for deadline
# def log_procurement_action(user, action, model_name, object_id, details=None, instance=None):
#     """
#     Comprehensive audit logging function
#     """
#     from .models import ProcurementAuditLog
#     
#     log_details = details or {}
#     
#     # Add instance details if available
#     if instance:
#         if hasattr(instance, 'to_dict'):
#             log_details['object_data'] = instance.to_dict()
#         else:
#             # Generic serialization
#             try:
#                 from django.forms.models import model_to_dict
#                 log_details['object_data'] = model_to_dict(instance)
#             except:
#                 log_details['object_data'] = str(instance)
#     
#     # Create audit log
#     ProcurementAuditLog.objects.create(
#         user=user,
#         action=action,
#         model_name=model_name,
#         object_id=object_id,
#         details=log_details
#     )

class ApprovalBoardViewSet(viewsets.ModelViewSet):
    queryset = ApprovalBoard.objects.select_related('user', 'added_by')
    serializer_class = ApprovalBoardSerializer
    permission_classes = [IsAuthenticated, DynamicPermission]
    page_permission_name = 'approval_board'
    pagination_class = StandardResultsSetPagination
    required_permissions = {
        'create': 'add_approval_board_member',
        'update': 'update_approval_board_member',
        'partial_update': 'update_approval_board_member',
        'destroy': 'delete_approval_board_member',
    }

    def get_queryset(self):
        queryset = ApprovalBoard.objects.select_related('user', 'added_by').filter(is_active=True)
        search = self.request.query_params.get('search', None)
        if search:
            queryset = queryset.filter(
                Q(user__email__icontains=search) | 
                Q(user__name__icontains=search)
            )
        return queryset

    def perform_create(self, serializer):
        instance = serializer.save(added_by=self.request.user)
        # TEMPORARILY COMMENTED OUT - Audit logging disabled
        # log_procurement_action(
        #     user=self.request.user,
        #     action='create',
        #     model_name='ApprovalBoard',
        #     object_id=instance.id,
        #     instance=instance,
        #     details={'operation': 'Added approval board member'}
        # )

    def perform_update(self, serializer):
        instance = serializer.save(added_by=self.request.user)
        # TEMPORARILY COMMENTED OUT - Audit logging disabled
        # log_procurement_action(
        #     user=self.request.user,
        #     action='update',
        #     model_name='ApprovalBoard',
        #     object_id=instance.id,
        #     instance=instance,
        #     details={'operation': 'Updated approval board member'}
        # )

    def perform_destroy(self, instance):
        instance_id = instance.id
        instance_data = instance.to_dict() if hasattr(instance, 'to_dict') else str(instance)
        instance.delete()
        # TEMPORARILY COMMENTED OUT - Audit logging disabled
        # log_procurement_action(
        #     user=self.request.user,
        #     action='delete',
        #     model_name='ApprovalBoard',
        #     object_id=instance_id,
        #     details={'operation': 'Deleted approval board member', 'deleted_data': instance_data}
        # )

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
        instance = serializer.save(created_by=self.request.user)
        # TEMPORARILY COMMENTED OUT - Audit logging disabled
        # log_procurement_action(
        #     user=self.request.user,
        #     action='create',
        #     model_name='Vendor',
        #     object_id=instance.id,
        #     instance=instance
        # )

    def perform_update(self, serializer):
        instance = serializer.save(created_by=self.request.user)
        # TEMPORARILY COMMENTED OUT - Audit logging disabled
        # log_procurement_action(
        #     user=self.request.user,
        #     action='update',
        #     model_name='Vendor',
        #     object_id=instance.id,
        #     instance=instance
        # )

    def perform_destroy(self, instance):
        instance_id = instance.id
        instance_data = instance.to_dict() if hasattr(instance, 'to_dict') else {
            'name': instance.name,
            'email': instance.email
        }
        instance.delete()
        # TEMPORARILY COMMENTED OUT - Audit logging disabled
        # log_procurement_action(
        #     user=self.request.user,
        #     action='delete',
        #     model_name='Vendor',
        #     object_id=instance_id,
        #     details={'deleted_vendor': instance_data}
        # )

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
        queryset = Requisition.objects.select_related(
            'requested_by', 'created_by', 'approved_by'
        ).prefetch_related('items__item')
        search = self.request.query_params.get('search', None)
        if search:
            queryset = queryset.filter(
                Q(code__icontains=search) |
                Q(department__icontains=search) |
                Q(purpose__icontains=search)
            )
        return queryset

    @action(detail=False, methods=['get'])
    def approval_board(self, request):
        """Get comprehensive approval board information for frontend workflow"""
        user = request.user
        
        # Get user's approval capabilities
        try:
            user_approval = ApprovalBoard.objects.get(user=user, is_active=True)
            can_approve_requisitions = user_approval.can_approve_requisitions
            can_approve_pos = user_approval.can_approve_purchase_orders
        except ApprovalBoard.DoesNotExist:
            can_approve_requisitions = False
            can_approve_pos = False
        
        # Get all active approval board members
        approval_board = ApprovalBoard.objects.filter(
            is_active=True
        ).select_related('user')
        
        # Count pending items for the current user
        pending_requisitions = 0
        pending_pos = 0
        
        if can_approve_requisitions:
            pending_requisitions = Requisition.objects.filter(
                status='submitted'
            ).count()
        
        if can_approve_pos:
            pending_pos = PurchaseOrder.objects.filter(
                status='submitted'
            ).count()
        
        # Serialize approval board members
        board_members = []
        for member in approval_board:
            board_members.append({
                'id': member.id,
                'user_id': member.user.id,
                'user_email': member.user.email,
                'user_name': member.user.name,
                'can_approve_requisitions': member.can_approve_requisitions,
                'can_approve_purchase_orders': member.can_approve_purchase_orders,
                'is_active': member.is_active,
                'date_added': member.added_at.isoformat() if member.added_at else None
            })
        
        return Response({
            'current_user': {
                'can_approve_requisitions': can_approve_requisitions,
                'can_approve_purchase_orders': can_approve_pos,
                'pending_requisitions': pending_requisitions,
                'pending_purchase_orders': pending_pos
            },
            'approval_board_members': board_members,
            'total_approvers': len(board_members)
        })

    def perform_create(self, serializer):
        instance = serializer.save(
            created_by=self.request.user,
            requested_by=self.request.user
        )
        # TEMPORARILY COMMENTED OUT - Audit logging disabled
        # log_procurement_action(
        #     user=self.request.user,
        #     action='create',
        #     model_name='Requisition',
        #     object_id=instance.id,
        #     instance=instance,
        #     details={'status': 'draft'}
        # )

    def perform_update(self, serializer):
        old_status = self.get_object().status
        instance = serializer.save(created_by=self.request.user)
        new_status = instance.status
        
        # Log status changes specifically
        if old_status != new_status:
            # TEMPORARILY COMMENTED OUT - Audit logging disabled
            # log_procurement_action(
            #     user=self.request.user,
            #     action='update',
            #     model_name='Requisition',
            #     object_id=instance.id,
            #     instance=instance,
            #     details={'status_change': f'{old_status} -> {new_status}'}
            # )
            pass
        else:
            # TEMPORARILY COMMENTED OUT - Audit logging disabled
            # log_procurement_action(
            #     user=self.request.user,
            #     action='update',
            #     model_name='Requisition',
            #     object_id=instance.id,
            #     instance=instance
            # )
            pass

    def perform_destroy(self, instance):
        instance_id = instance.id
        instance_data = instance.to_dict() if hasattr(instance, 'to_dict') else {
            'code': instance.code,
            'department': instance.department
        }
        instance.delete()
        # TEMPORARILY COMMENTED OUT - Audit logging disabled
        # log_procurement_action(
        #     user=self.request.user,
        #     action='delete',
        #     model_name='Requisition',
        #     object_id=instance_id,
        #     details={'deleted_requisition': instance_data}
        # )

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
        
        # TEMPORARILY COMMENTED OUT - Manual audit log creation disabled
        # Convert datetime to string for JSON serialization
        # approved_at_str = requisition.approved_at.isoformat() if requisition.approved_at else None
        # 
        # ProcurementAuditLog.objects.create(
        #     user=request.user,
        #     action='approve',
        #     model_name='Requisition',
        #     object_id=requisition.id,
        #     details={
        #         'status': 'approved',
        #         'approved_at': approved_at_str,
        #         'requisition_code': requisition.code
        #     }
        # )
        
        return Response({'status': 'approved'})

    @action(detail=True, methods=['post'])
    def reject(self, request, pk=None):
        requisition = self.get_object()
        if not requisition.can_approve(request.user):
            return Response({'error': 'You do not have permission to reject this requisition.'}, 
                          status=status.HTTP_403_FORBIDDEN)
        
        old_status = requisition.status
        requisition.status = 'rejected'
        requisition.save()
        
        # TEMPORARILY COMMENTED OUT - Audit logging disabled
        # log_procurement_action(
        #     user=request.user,
        #     action='reject',
        #     model_name='Requisition',
        #     object_id=requisition.id,
        #     instance=requisition,
        #     details={'status_change': f'{old_status} -> rejected'}
        # )
        
        return Response({'status': 'rejected'})

    @action(detail=True, methods=['post'])
    def submit(self, request, pk=None):
        """Submit requisition for approval"""
        requisition = self.get_object()
        if requisition.status != 'draft':
            return Response({'error': 'Only draft requisitions can be submitted.'}, 
                          status=status.HTTP_400_BAD_REQUEST)
        
        old_status = requisition.status
        requisition.status = 'submitted'
        requisition.save()
        
        # TEMPORARILY COMMENTED OUT - Audit logging disabled
        # log_procurement_action(
        #     user=request.user,
        #     action='submit',
        #     model_name='Requisition',
        #     object_id=requisition.id,
        #     instance=requisition,
        #     details={'status_change': f'{old_status} -> submitted'}
        # )
        
        return Response({'status': 'submitted'})

    @action(detail=True, methods=['post'])
    def cancel(self, request, pk=None):
        """Cancel requisition"""
        requisition = self.get_object()
        if requisition.status in ['approved', 'completed']:
            return Response({'error': 'Cannot cancel approved or completed requisitions.'}, 
                          status=status.HTTP_400_BAD_REQUEST)
        
        old_status = requisition.status
        requisition.status = 'cancelled'
        requisition.save()
        
        # TEMPORARILY COMMENTED OUT - Audit logging disabled
        # log_procurement_action(
        #     user=request.user,
        #     action='cancel',
        #     model_name='Requisition',
        #     object_id=requisition.id,
        #     instance=requisition,
        #     details={'status_change': f'{old_status} -> cancelled'}
        # )
        
        return Response({'status': 'cancelled'})

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
        instance = serializer.save(created_by=self.request.user)
        # TEMPORARILY COMMENTED OUT - Audit logging disabled
        # log_procurement_action(
        #     user=self.request.user,
        #     action='create',
        #     model_name='PurchaseOrder',
        #     object_id=instance.id,
        #     instance=instance,
        #     details={'status': 'draft'}
        # )

    def perform_update(self, serializer):
        old_status = self.get_object().status
        instance = serializer.save(created_by=self.request.user)
        new_status = instance.status
        
        if old_status != new_status:
            # TEMPORARILY COMMENTED OUT - Audit logging disabled
            # log_procurement_action(
            #     user=self.request.user,
            #     action='update',
            #     model_name='PurchaseOrder',
            #     object_id=instance.id,
            #     instance=instance,
            #     details={'status_change': f'{old_status} -> {new_status}'}
            # )
            pass
        else:
            # TEMPORARILY COMMENTED OUT - Audit logging disabled
            # log_procurement_action(
            #     user=self.request.user,
            #     action='update',
            #     model_name='PurchaseOrder',
            #     object_id=instance.id,
            #     instance=instance
            # )
            pass

    def perform_destroy(self, instance):
        instance_id = instance.id
        instance_data = instance.to_dict() if hasattr(instance, 'to_dict') else {
            'code': instance.code,
            'vendor': instance.vendor.name if instance.vendor else None
        }
        instance.delete()
        # TEMPORARILY COMMENTED OUT - Audit logging disabled
        # log_procurement_action(
        #     user=self.request.user,
        #     action='delete',
        #     model_name='PurchaseOrder',
        #     object_id=instance_id,
        #     details={'deleted_po': instance_data}
        # )

    @action(detail=True, methods=['post'])
    def approve(self, request, pk=None):
        po = self.get_object()
        if not po.can_approve(request.user):
            return Response({'error': 'You do not have permission to approve this purchase order.'}, 
                          status=status.HTTP_403_FORBIDDEN)
        
        old_status = po.status
        po.status = 'approved'
        po.approved_by = request.user
        po.approved_at = datetime.now()
        po.save()
        
        # TEMPORARILY COMMENTED OUT - Audit logging disabled
        # log_procurement_action(
        #     user=request.user,
        #     action='approve',
        #     model_name='PurchaseOrder',
        #     object_id=po.id,
        #     instance=po,
        #     details={'status_change': f'{old_status} -> approved'}
        # )
        
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
                getattr(item, 'description', "") or "",
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

    @action(detail=True, methods=['post'])
    def submit(self, request, pk=None):
        """Submit PO for approval"""
        po = self.get_object()
        if po.status != 'draft':
            return Response({'error': 'Only draft POs can be submitted.'}, 
                          status=status.HTTP_400_BAD_REQUEST)
        
        old_status = po.status
        po.status = 'submitted'
        po.save()
        
        # TEMPORARILY COMMENTED OUT - Audit logging disabled
        # log_procurement_action(
        #     user=request.user,
        #     action='submit',
        #     model_name='PurchaseOrder',
        #     object_id=po.id,
        #     instance=po,
        #     details={'status_change': f'{old_status} -> submitted'}
        # )
        
        return Response({'status': 'submitted'})

    @action(detail=True, methods=['post'])
    def cancel(self, request, pk=None):
        """Cancel PO"""
        po = self.get_object()
        if po.status in ['approved', 'received']:
            return Response({'error': 'Cannot cancel approved or received POs.'}, 
                          status=status.HTTP_400_BAD_REQUEST)
        
        old_status = po.status
        po.status = 'cancelled'
        po.save()
        
        # TEMPORARILY COMMENTED OUT - Audit logging disabled
        # log_procurement_action(
        #     user=request.user,
        #     action='cancel',
        #     model_name='PurchaseOrder',
        #     object_id=po.id,
        #     instance=po,
        #     details={'status_change': f'{old_status} -> cancelled'}
        # )
        
        return Response({'status': 'cancelled'})

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
        instance = serializer.save(
            created_by=self.request.user,
            received_by=self.request.user
        )
        # TEMPORARILY COMMENTED OUT - Audit logging disabled
        # log_procurement_action(
        #     user=self.request.user,
        #     action='create',
        #     model_name='Receiving',
        #     object_id=instance.id,
        #     instance=instance,
        #     details={'status': instance.status}
        # )
        # Update PO status is already handled in model

    def perform_update(self, serializer):
        old_status = self.get_object().status
        instance = serializer.save(created_by=self.request.user)
        new_status = instance.status
        
        if old_status != new_status:
            # TEMPORARILY COMMENTED OUT - Audit logging disabled
            # log_procurement_action(
            #     user=self.request.user,
            #     action='update',
            #     model_name='Receiving',
            #     object_id=instance.id,
            #     instance=instance,
            #     details={'status_change': f'{old_status} -> {new_status}'}
            # )
            pass
        else:
            # TEMPORARILY COMMENTED OUT - Audit logging disabled
            # log_procurement_action(
            #     user=self.request.user,
            #     action='update',
            #     model_name='Receiving',
            #     object_id=instance.id,
            #     instance=instance
            # )
            pass

    def perform_destroy(self, instance):
        instance_id = instance.id
        instance_data = instance.to_dict() if hasattr(instance, 'to_dict') else {
            'grn': instance.grn,
            'po_code': instance.po.code if instance.po else None
        }
        instance.delete()
        # TEMPORARILY COMMENTED OUT - Audit logging disabled
        # log_procurement_action(
        #     user=self.request.user,
        #     action='delete',
        #     model_name='Receiving',
        #     object_id=instance_id,
        #     details={'deleted_receiving': instance_data}
        # )

class ProcurementAuditLogViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = ProcurementAuditLog.objects.all()
    serializer_class = ProcurementAuditLogSerializer
    permission_classes = [IsAuthenticated, DynamicPermission]
    page_permission_name = 'procurement_audit_logs'
    pagination_class = StandardResultsSetPagination

    def get_queryset(self):
        queryset = ProcurementAuditLog.objects.select_related('user')
        # Add filtering capabilities
        model_name = self.request.query_params.get('model_name', None)
        action = self.request.query_params.get('action', None)
        user_id = self.request.query_params.get('user_id', None)
        
        if model_name:
            queryset = queryset.filter(model_name__icontains=model_name)
        if action:
            queryset = queryset.filter(action=action)
        if user_id:
            queryset = queryset.filter(user_id=user_id)
            
        return queryset.order_by('-created_at')