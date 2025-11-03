import csv
from django.conf import settings
from rest_framework import viewsets, permissions, status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.decorators import permission_classes, api_view, action
from rest_framework.exceptions import PermissionDenied
from django.db.models import Q, Sum, Count
from rest_framework.pagination import PageNumberPagination
from django.utils import timezone
from django.db import transaction
import logging
from .models import Warehouse, StorageBin, Item, StockRecord, StockMovement, InventoryAlert, ExpiryTrackedItem, InventoryActivityLog, WarehouseReceipt
from .serializers import (
    WarehouseSerializer, StorageBinSerializer, ItemSerializer, StockRecordSerializer,
    StockMovementSerializer, InventoryAlertSerializer, ExpiryTrackedItemSerializer,
    StockInSerializer, StockOutSerializer, InventoryActivityLogSerializer, WarehouseReceiptSerializer
)
from accounts.permissions import APIKeyPermission
from accounts.models import PagePermission, ActionPermission
from rest_framework.parsers import MultiPartParser, FormParser
from django.shortcuts import render, get_object_or_404
from django.contrib.auth.decorators import login_required
from io import BytesIO
from django.http import HttpResponse
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from rest_framework.permissions import IsAuthenticated

logger = logging.getLogger(__name__)

ROLE_LEVELS = {
    'staff': 1,
    'finance_manager': 2,
    'operations_manager': 3,
    'md': 4,
    'admin': 99,
}

def get_user_role_level(user):
    return ROLE_LEVELS.get(user.role, 0)

def get_page_required_level(page):
    perm = PagePermission.objects.filter(page_name=page).first()
    return ROLE_LEVELS.get(perm.min_role, 1) if perm else 1

def get_action_required_level(action_name):
    perm = ActionPermission.objects.filter(action_name=action_name).first()
    return ROLE_LEVELS.get(perm.min_role, 1) if perm else 1

def check_permission(user, page=None, action=None):
    user_level = get_user_role_level(user)
    if page:
        required = get_page_required_level(page)
        if user_level < required:
            raise PermissionDenied(f"Access denied: {page} requires role level {required}")
    if action:
        required = get_action_required_level(action)
        if user_level < required:
            raise PermissionDenied(f"Access denied: {action} requires role level {required}")

def log_activity(user, action, model_name, object_id, object_name, details=None):
    try:
        InventoryActivityLog.objects.create(
            user=user,
            action=action,
            model_name=model_name,
            object_id=object_id,
            object_name=object_name,
            details=details or {}
        )
    except Exception as e:
        logger.error(f"Failed to create activity log: {e}")

class StandardResultsSetPagination(PageNumberPagination):
    page_size = 10
    page_size_query_param = 'page_size'
    max_page_size = 100

class InventoryMetricsView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        check_permission(request.user, page="inventory_metrics")
        search = request.query_params.get('search', '').strip()
        total_items = Item.objects.filter(Q(name__icontains=search) | Q(part_number__icontains=search)).count() if search else Item.objects.count()
        total_bins = StorageBin.objects.count()
        total_alerts = InventoryAlert.objects.filter(is_resolved=False).count()
        total_movements = StockMovement.objects.count()
        expired_items = Item.objects.filter(expiry_date__lte=timezone.now().date()).count()

        data = [
            {"id": 1, "title": "Total Items", "value": total_items, "change": "+0%", "trend": "neutral"},
            {"id": 2, "title": "Total Bins", "value": total_bins, "change": "+0%", "trend": "neutral"},
            {"id": 3, "title": "Active Alerts", "value": total_alerts, "change": "+0%", "trend": "neutral"},
            {"id": 4, "title": "Total Stock Movements", "value": total_movements, "change": "+0%", "trend": "neutral"},
            {"id": 5, "title": "Expired Items", "value": expired_items, "change": "+0%", "trend": "neutral"},
        ]
        return Response(data)

class ItemViewSet(viewsets.ModelViewSet):
    serializer_class = ItemSerializer
    permission_classes = [permissions.IsAuthenticated]
    pagination_class = StandardResultsSetPagination

    def get_queryset(self):
        check_permission(self.request.user, page="items")
        queryset = Item.objects.all().order_by('-id')
        search = self.request.query_params.get('search', '').strip()
        if search:
            queryset = queryset.filter(
                Q(name__icontains=search) |
                Q(part_number__icontains=search) |
                Q(material_id__icontains=search)
            )
        return queryset

    def perform_create(self, serializer):
        check_permission(self.request.user, action="create_item")
        item = serializer.save(user=self.request.user)
        log_activity(
            user=self.request.user,
            action='create',
            model_name='Item',
            object_id=item.id,
            object_name=item.name,
            details={'part_number': item.part_number, 'manufacturer': item.manufacturer}
        )

    def perform_update(self, serializer):
        check_permission(self.request.user, action="update_item")
        item = serializer.save(user=self.request.user)
        log_activity(
            user=self.request.user,
            action='update',
            model_name='Item',
            object_id=item.id,
            object_name=item.name,
            details={'changes': 'Item updated'}
        )

    def perform_destroy(self, instance):
        check_permission(self.request.user, action="delete_item")
        if instance.stock_records.exists():
            raise PermissionDenied("Cannot delete item with stock records.")
        item_name = instance.name
        instance.delete()
        log_activity(
            user=self.request.user,
            action='delete',
            model_name='Item',
            object_id=None,  # Already deleted
            object_name=item_name,
            details={'deleted_item': item_name}
        )

    @action(detail=False, methods=['post'], url_path='bulk-delete')
    def bulk_delete(self, request):
        logger.info(f"Bulk delete action called with data: {request.data}")
        try:
            check_permission(request.user, action="delete_item")
            item_ids = request.data.get('item_ids', [])

            if not isinstance(item_ids, list) or not item_ids:
                logger.error(f"Bulk delete failed: item_ids is {item_ids}")
                return Response({'error': 'item_ids must be a non-empty list'}, status=status.HTTP_400_BAD_REQUEST)

            items = Item.objects.filter(id__in=item_ids)
            found_ids = set(items.values_list('id', flat=True))
            logger.info(f"Bulk delete: Requested IDs {item_ids}, Found IDs {found_ids}")

            missing = set(item_ids) - found_ids
            if missing:
                logger.warning(f"Bulk delete: Items not found: {missing}")
                return Response({'error': f'Items not found: {missing}'}, status=status.HTTP_400_BAD_REQUEST)

            items_with_stock = [item.id for item in items if item.stock_records.exists()]
            if items_with_stock:
                logger.warning(f"Bulk delete: Items with stock records: {items_with_stock}")
                return Response({
                    'error': 'Cannot delete items with stock records.',
                    'items_with_stock': items_with_stock
                }, status=status.HTTP_400_BAD_REQUEST)

            with transaction.atomic():
                deleted_names = []
                deleted_count = 0
                for item in items:
                    deleted_names.append(item.name)
                    item.delete()
                    deleted_count += 1

                for name in deleted_names:
                    try:
                        log_activity(
                            user=request.user,
                            action='delete',
                            model_name='Item',
                            object_id=None,  # Explicitly allow None
                            object_name=name,
                            details={'bulk_deleted_item': name}
                        )
                    except Exception as log_error:
                        logger.error(f"Failed to log activity for {name}: {str(log_error)}")
                        # Continue despite logging error

            logger.info(f"Bulk delete: Successfully deleted {deleted_count} items")
            return Response({'message': f'{deleted_count} items deleted successfully'}, status=status.HTTP_200_OK)
        except Exception as e:
            logger.error(f"Bulk delete failed: {str(e)}")
            return Response({'error': f'Operation failed: {str(e)}'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


    @action(detail=False, methods=['get'], url_path='export-pdf')
    def export_pdf(self, request):
        logger.info("Export PDF action called")
        try:
            check_permission(request.user, action="view_item")
            items = Item.objects.all().order_by('id')
            if not items.exists():
                return Response({'error': 'No items found'}, status=status.HTTP_404_NOT_FOUND)

            buffer = BytesIO()
            doc = SimpleDocTemplate(
                buffer,
                pagesize=letter,
                topMargin=0.75 * inch,
                bottomMargin=0.75 * inch,
                leftMargin=0.75 * inch,
                rightMargin=0.75 * inch
            )
            elements = []
            styles = getSampleStyleSheet()

            # Define styles
            title_style = ParagraphStyle(
                'ReportTitle', parent=styles['Heading1'],
                fontSize=16, alignment=1, spaceAfter=8, leading=20,
                textColor=colors.HexColor("#333333")
            )
            section_heading = ParagraphStyle(
                'SectionHeading', parent=styles['Heading3'],
                fontSize=10.5, spaceBefore=6, spaceAfter=6,
                textColor=colors.HexColor("#2b2b2b"), leading=13
            )
            small_info = ParagraphStyle(
                'SmallInfo', parent=styles['Normal'],
                fontSize=9, leading=12, textColor=colors.black
            )

            # Header with logo (if available), company name, and date
            from datetime import datetime
            current_date = datetime.now().strftime('%d/%m/%Y %H:%M')
            if hasattr(settings, 'COMPANY_LOGO_PATH'):
                try:
                    logo_img = Image(settings.COMPANY_LOGO_PATH, width=1.5*inch, height=0.8*inch)
                    header_table = Table([[
                        logo_img,
                        Paragraph(f"<b>{getattr(settings, 'COMPANY_NAME', 'Kenyon Inventory')}</b><br/><span>{getattr(settings, 'COMPANY_TAGLINE', '')}</span>", styles['Title']),
                        Paragraph(f"<b>Date</b><br/>{current_date}", small_info)
                    ]], colWidths=[1.5*inch, 3.8*inch, 2.2*inch])
                    header_table.setStyle(TableStyle([
                        ('BACKGROUND', (0, 0), (0, 0), colors.HexColor("#B2B2B2")),
                        ('BACKGROUND', (1, 0), (1, 0), colors.white),
                        ('BACKGROUND', (2, 0), (2, 0), colors.HexColor("#F6F6F6")),
                        ('TEXTCOLOR', (0, 0), (-1, -1), colors.black),
                        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                        ('ALIGN', (2, 0), (2, 0), 'RIGHT'),
                        ('LEFTPADDING', (0, 0), (-1, -1), 8),
                        ('RIGHTPADDING', (0, 0), (-1, -1), 8),
                        ('TOPPADDING', (0, 0), (-1, -1), 10),
                        ('BOTTOMPADDING', (0, 0), (-1, -1), 10),
                        ('BOX', (0, 0), (-1, -1), 0.5, colors.HexColor("#D0D0D0")),
                    ]))
                    elements.append(header_table)
                except Exception as e:
                    logger.warning(f"Logo not found or failed to load: {str(e)}")
                    header_table = Table([[
                        Paragraph(f"<b>{getattr(settings, 'COMPANY_NAME', 'Kenyon Inventory')}</b>", styles['Title']),
                        Paragraph(f"<b>Date</b><br/>{current_date}", small_info)
                    ]], colWidths=[5.0*inch, 2.2*inch])
                    header_table.setStyle(TableStyle([
                        ('BACKGROUND', (0, 0), (0, 0), colors.HexColor("#B2B2B2")),
                        ('BACKGROUND', (1, 0), (1, 0), colors.HexColor("#F6F6F6")),
                        ('TEXTCOLOR', (0, 0), (-1, -1), colors.black),
                        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                        ('ALIGN', (1, 0), (1, 0), 'RIGHT'),
                        ('LEFTPADDING', (0, 0), (-1, -1), 8),
                        ('RIGHTPADDING', (0, 0), (-1, -1), 8),
                        ('TOPPADDING', (0, 0), (-1, -1), 10),
                        ('BOTTOMPADDING', (0, 0), (-1, -1), 10),
                        ('BOX', (0, 0), (-1, -1), 0.5, colors.HexColor("#D0D0D0")),
                    ]))
                    elements.append(header_table)
            else:
                header_table = Table([[
                    Paragraph(f"<b>{getattr(settings, 'COMPANY_NAME', 'Kenyon Inventory')}</b>", styles['Title']),
                    Paragraph(f"<b>Date</b><br/>{current_date}", small_info)
                ]], colWidths=[5.0*inch, 2.2*inch])
                header_table.setStyle(TableStyle([
                    ('BACKGROUND', (0, 0), (0, 0), colors.HexColor("#B2B2B2")),
                    ('BACKGROUND', (1, 0), (1, 0), colors.HexColor("#F6F6F6")),
                    ('TEXTCOLOR', (0, 0), (-1, -1), colors.black),
                    ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                    ('ALIGN', (1, 0), (1, 0), 'RIGHT'),
                    ('LEFTPADDING', (0, 0), (-1, -1), 8),
                    ('RIGHTPADDING', (0, 0), (-1, -1), 8),
                    ('TOPPADING', (0, 0), (-1, -1), 10),
                    ('BOTTOMPADDING', (0, 0), (-1, -1), 10),
                    ('BOX', (0, 0), (-1, -1), 0.5, colors.HexColor("#D0D0D0")),
                ]))
                elements.append(header_table)

            elements.append(Spacer(1, 12))
            elements.append(Paragraph("INVENTORY ITEMS REPORT", title_style))
            elements.append(Spacer(1, 8))

            # Item table
            elements.append(Paragraph("<b>ITEMS</b>", section_heading))
            elements.append(Spacer(1, 6))
            item_data = [["ID", "Material ID", "Name", "po_number", "min_stock"]]
            for item in items:
                item_data.append([
                    str(item.id),
                    item.material_id or "—",
                    item.name or "—",
                    item.po_number or "—",
                    item.min_stock_level or "—"
                ])
            item_table = Table(item_data, colWidths=[0.5*inch, 1.0*inch, 1.5*inch, 1.0*inch, 1.5*inch, 2.0*inch])
            item_table.setStyle(TableStyle([
                ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
                ('FONTSIZE', (0, 0), (-1, -1), 9),
                ('VALIGN', (0, 0), (-1, -1), 'TOP'),
                ('GRID', (0, 0), (-1, -1), 0.35, colors.HexColor("#E0E0E0")),
                ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor("#F3F3F3")),  # Header row
                ('BACKGROUND', (0, 1), (-1, -1), colors.HexColor("#FAFAFA")),  # Data rows
                ('LEFTPADDING', (0, 0), (-1, -1), 8),
                ('RIGHTPADDING', (0, 0), (-1, -1), 8),
                ('TOPPADDING', (0, 0), (-1, -1), 6),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
            ]))
            elements.append(item_table)
            elements.append(Spacer(1, 18))

            # Footer
            footer_table = Table([[
                Paragraph("<i>This document is auto-generated.</i>", styles['Italic']),
                Paragraph(f"{getattr(settings, 'COMPANY_NAME', 'Kenyon Inventory')}", small_info)
            ]], colWidths=[4.6*inch, 2.0*inch])
            footer_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor("#333333")),
                ('TEXTCOLOR', (0, 0), (-1, -1), colors.whitesmoke),
                ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                ('ALIGN', (1, 0), (1, 0), 'RIGHT'),
                ('LEFTPADDING', (0, 0), (-1, -1), 10),
                ('RIGHTPADDING', (0, 0), (-1, -1), 10),
                ('TOPPADDING', (0, 0), (-1, -1), 8),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
            ]))
            elements.append(footer_table)

            doc.build(elements)
            buffer.seek(0)
            response = HttpResponse(buffer.getvalue(), content_type='application/pdf')
            response['Content-Disposition'] = 'attachment; filename="inventory_items_report.pdf"'
            return response
        except Exception as e:
            logger.error(f"PDF export error: {str(e)}")
            return Response({'error': 'Failed to generate PDF'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)



class BulkDeleteItemsView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        logger.info(f"Standalone BulkDeleteItemsView called with data: {request.data}")
        try:
            check_permission(request.user, action="delete_item")
            item_ids = request.data.get('item_ids', [])

            if not isinstance(item_ids, list) or not item_ids:
                logger.error(f"Bulk delete failed: item_ids is {item_ids}")
                return Response({'error': 'item_ids must be a non-empty list'}, status=status.HTTP_400_BAD_REQUEST)

            items = Item.objects.filter(id__in=item_ids)
            found_ids = set(items.values_list('id', flat=True))
            logger.info(f"Bulk delete: Requested IDs {item_ids}, Found IDs {found_ids}")

            missing = set(item_ids) - found_ids
            if missing:
                logger.warning(f"Bulk delete: Items not found: {missing}")
                return Response({'error': f'Items not found: {missing}'}, status=status.HTTP_400_BAD_REQUEST)

            items_with_stock = [item.id for item in items if item.stock_records.exists()]
            if items_with_stock:
                logger.warning(f"Bulk delete: Items with stock records: {items_with_stock}")
                return Response({
                    'error': 'Cannot delete items with stock records.',
                    'items_with_stock': items_with_stock
                }, status=status.HTTP_400_BAD_REQUEST)

            with transaction.atomic():
                deleted_names = []
                deleted_count = 0
                for item in items:
                    deleted_names.append(item.name)
                    item.delete()
                    deleted_count += 1

                for name in deleted_names:
                    try:
                        log_activity(
                            user=request.user,
                            action='delete',
                            model_name='Item',
                            object_id=None,
                            object_name=name,
                            details={'bulk_deleted_item': name}
                        )
                    except Exception as log_error:
                        logger.error(f"Failed to log activity for {name}: {str(log_error)}")
                        # Continue despite logging error

            logger.info(f"Bulk delete: Successfully deleted {deleted_count} items")
            return Response({'message': f'{deleted_count} items deleted successfully'}, status=status.HTTP_200_OK)
        except Exception as e:
            logger.error(f"Bulk delete failed: {str(e)}")
            return Response({'error': f'Operation failed: {str(e)}'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)



class ImportCSVView(APIView):
    permission_classes = [permissions.IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser]

    def post(self, request):
        """Import items from CSV file"""
        try:
            check_permission(request.user, action="create_item")
            check_permission(request.user, action="import_items_csv")

            if 'file' not in request.FILES:
                return Response({'error': 'No file provided'}, status=400)

            file = request.FILES['file']

            # Validate file type
            if not file.name.endswith('.csv'):
                return Response({'error': 'Only CSV files are allowed'}, status=400)

            try:
                # Decode and read CSV
                decoded_file = file.read().decode('utf-8').splitlines()
                csv_reader = csv.DictReader(decoded_file)

                created_items = []
                errors = []

                # Required fields (adjust based on your Item model)
                required_fields = ['name', 'part_number', 'manufacturer', 'contact', 'material', 'grade']

                for row_num, row in enumerate(csv_reader, start=2):  # Start at 2 (header is row 1)
                    try:
                        # Validate required fields
                        missing_fields = [field for field in required_fields if not row.get(field, '').strip()]
                        if missing_fields:
                            errors.append(f"Row {row_num}: Missing required fields: {', '.join(missing_fields)}")
                            continue

                        # Create item
                        item_data = {
                            'name': row['name'].strip(),
                            'description': row.get('description', '').strip(),
                            'part_number': row['part_number'].strip(),
                            'manufacturer': row['manufacturer'].strip(),
                            'contact': row['contact'].strip(),
                            'min_stock_level': int(row.get('min_stock_level', 0)) if row.get('min_stock_level') else 0,
                            'reserved_quantity': int(row.get('reserved_quantity', 0)) if row.get('reserved_quantity') else 0,
                            'custom_fields': {
                                'Material': row.get('material', '').strip(),
                                'Grade': row.get('grade', '').strip()
                            }
                        }

                        # Handle optional fields
                        if row.get('batch'):
                            item_data['batch'] = row['batch'].strip()
                        if row.get('expiry_date'):
                            item_data['expiry_date'] = row['expiry_date'].strip()
                        if row.get('po_number'):
                            item_data['po_number'] = row['po_number'].strip()

                        # Create the item
                        item = Item.objects.create(
                            user=request.user,
                            **item_data
                        )
                        created_items.append(item.name)

                        # Log activity
                        log_activity(
                            user=request.user,
                            action='create',
                            model_name='Item',
                            object_id=item.id,
                            object_name=item.name,
                            details={'source': 'CSV import', 'part_number': item.part_number}
                        )

                    except Exception as e:
                        errors.append(f"Row {row_num}: {str(e)}")

                result = {
                    'success': f'Successfully imported {len(created_items)} items',
                    'created_items': created_items,
                    'errors': errors
                }

                if errors:
                    return Response(result, status=207)  # Partial success
                return Response(result, status=201)

            except UnicodeDecodeError:
                return Response({'error': 'Invalid file encoding. Please use UTF-8 encoded CSV file.'}, status=400)
            except csv.Error as e:
                return Response({'error': f'Invalid CSV format: {str(e)}'}, status=400)
            except Exception as e:
                return Response({'error': f'Unexpected error: {str(e)}'}, status=500)

        except PermissionDenied as e:
            return Response({'error': str(e)}, status=403)
        except Exception as e:
            logger.error(f"Import CSV error: {str(e)}")
            return Response({'error': f'Unexpected error: {str(e)}'}, status=500)

class StorageBinViewSet(viewsets.ModelViewSet):
    serializer_class = StorageBinSerializer
    permission_classes = [permissions.IsAuthenticated]
    pagination_class = StandardResultsSetPagination

    def get_queryset(self):
        check_permission(self.request.user, page="storage_bins")
        queryset = StorageBin.objects.select_related('warehouse').prefetch_related(
            'stock_records__item',
            'stock_records__storage_bin'
        ).all().order_by('-created_at')
        warehouse_id = self.request.query_params.get('warehouse_id')
        if warehouse_id:
            queryset = queryset.filter(warehouse_id=warehouse_id)

        search = self.request.query_params.get('search', '').strip()
        if search:
            queryset = queryset.filter(
                Q(bin_id__icontains=search) |
                Q(description__icontains=search) |
                Q(warehouse__name__icontains=search)
            )
        return queryset

    def perform_create(self, serializer):
        check_permission(self.request.user, action="create_storage_bin")
        warehouse = serializer.validated_data.get('warehouse')
        if warehouse:
            if warehouse.bins.count() >= warehouse.capacity:
                raise PermissionDenied(f"Warehouse capacity exceeded. Maximum {warehouse.capacity} bins allowed.")
        storage_bin = serializer.save(user=self.request.user)
        log_activity(
            user=self.request.user,
            action='create',
            model_name='StorageBin',
            object_id=storage_bin.id,
            object_name=storage_bin.bin_id,
            details={'warehouse': storage_bin.warehouse.name if storage_bin.warehouse else 'None'}
        )

    def perform_update(self, serializer):
        check_permission(self.request.user, action="update_storage_bin")
        storage_bin = serializer.save()
        log_activity(
            user=self.request.user,
            action='update',
            model_name='StorageBin',
            object_id=storage_bin.id,
            object_name=storage_bin.bin_id,
            details={'changes': 'Storage bin updated'}
        )

    def perform_destroy(self, instance):
        check_permission(self.request.user, action="delete_storage_bin")
        if instance.current_load > 0:
            raise PermissionDenied("Cannot delete bin with stock.")
        bin_id = instance.bin_id
        instance.delete()
        log_activity(
            user=self.request.user,
            action='delete',
            model_name='StorageBin',
            object_id=instance.id,
            object_name=bin_id,
            details={'deleted_bin': bin_id}
        )

    @action(detail=True, methods=['post'], url_path='sync')
    def sync_bin(self, request, pk=None):
        try:
            check_permission(request.user, action="update_storage_bin")
            bin = get_object_or_404(StorageBin, id=pk, user=request.user)
            valid_stock_records = StockRecord.objects.filter(
                storage_bin=bin,
                item__isnull=False
            )
            new_load = valid_stock_records.aggregate(total=Sum('quantity'))['total'] or 0

            if bin.current_load != new_load:
                bin.current_load = new_load
                bin.save()
                return Response({
                    'message': 'Bin synced',
                    'old_load': bin.current_load,
                    'new_load': new_load
                })
            else:
                return Response({'message': 'Bin already in sync'})
        except Exception as e:
            logger.error(f"Sync bin failed: {str(e)}")
            return Response({'error': 'Operation failed'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=True, methods=['post'], url_path='move-to-warehouse')
    def move_to_warehouse(self, request, pk=None):
        try:
            check_permission(request.user, action="update_storage_bin")
            bin = self.get_object()
            warehouse_id = request.data.get('warehouse_id')

            if not warehouse_id:
                return Response({'error': 'warehouse_id required'}, status=400)

            try:
                new_warehouse = Warehouse.objects.get(id=warehouse_id, user=request.user)
            except Warehouse.DoesNotExist:
                return Response({'error': 'Warehouse not found or not owned'}, status=404)

            if new_warehouse.bins.count() >= new_warehouse.capacity:
                return Response({'error': 'Target warehouse capacity exceeded'}, status=400)

            with transaction.atomic():
                bin.warehouse = new_warehouse
                bin.save()
                log_activity(
                    user=request.user,
                    action='update',
                    model_name='StorageBin',
                    object_id=bin.id,
                    object_name=bin.bin_id,
                    details={'moved_to_warehouse': new_warehouse.name}
                )

            return Response({'message': 'Bin moved successfully'})
        except Exception as e:
            logger.error(f"Move bin to warehouse failed: {str(e)}")
            return Response({'error': 'Operation failed'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

class StockRecordViewSet(viewsets.ModelViewSet):
    serializer_class = StockRecordSerializer
    permission_classes = [permissions.IsAuthenticated]
    pagination_class = StandardResultsSetPagination

    def get_queryset(self):
        check_permission(self.request.user, page="stock_records")
        queryset = StockRecord.objects.select_related('item', 'storage_bin').order_by('-created_at')
        search = self.request.query_params.get('search', '').strip()
        if search:
            queryset = queryset.filter(Q(item__name__icontains=search) | Q(storage_bin__bin_id__icontains=search))
        return queryset

    def perform_create(self, serializer):
        check_permission(self.request.user, action="create_stock_record")
        stock_record = serializer.save(user=self.request.user)
        item = stock_record.item
        storage_bin = stock_record.storage_bin
        storage_bin.current_load = (storage_bin.current_load or 0) + stock_record.quantity
        storage_bin.save()
        log_activity(
            user=self.request.user,
            action='create',
            model_name='StockRecord',
            object_id=stock_record.id,
            object_name=f"{item.name} in {storage_bin.bin_id}",
            details={
                'item_id': item.id,
                'item_name': item.name,
                'storage_bin_id': storage_bin.id,
                'storage_bin_name': storage_bin.bin_id,
                'quantity': stock_record.quantity
            }
        )

    def perform_destroy(self, instance):
        check_permission(self.request.user, action="delete_stock_record")
        item = instance.item
        storage_bin = instance.storage_bin
        quantity = instance.quantity
        record_id = instance.id
        item_name = item.name if item else 'Unknown Item'
        bin_id = storage_bin.bin_id if storage_bin else 'Unknown Bin'
        if storage_bin:
            storage_bin.current_load = max(0, (storage_bin.current_load or 0) - quantity)
            storage_bin.save()
        instance.delete()
        log_activity(
            user=self.request.user,
            action='delete',
            model_name='StockRecord',
            object_id=record_id,
            object_name=f"{item_name} in {bin_id}",
            details={
                'item_id': item.id if item else None,
                'item_name': item_name,
                'storage_bin_id': storage_bin.id if storage_bin else None,
                'storage_bin_name': bin_id,
                'quantity': quantity
            }
        )

class StockMovementViewSet(viewsets.ModelViewSet):
    serializer_class = StockMovementSerializer
    permission_classes = [permissions.IsAuthenticated]
    pagination_class = StandardResultsSetPagination

    def get_queryset(self):
        check_permission(self.request.user, page="stock_movements")
        queryset = StockMovement.objects.select_related('item', 'storage_bin').order_by('-timestamp')
        search = self.request.query_params.get('search', '').strip()
        if search:
            queryset = queryset.filter(
                Q(item__name__icontains=search) | Q(storage_bin__bin_id__icontains=search)
            )
        return queryset

    def perform_create(self, serializer):
        movement = serializer.save(user=self.request.user)
        log_activity(
            user=self.request.user,
            action=movement.movement_type.lower(),
            model_name='StockMovement',
            object_id=movement.id,
            object_name=f"{movement.item.name} ({movement.movement_type})",
            details={
                'item_id': movement.item.id,
                'item_name': movement.item.name,
                'storage_bin_id': movement.storage_bin.id,
                'storage_bin_name': movement.storage_bin.bin_id,
                'quantity': movement.quantity,
                'movement_type': movement.movement_type
            }
        )

class InventoryAlertViewSet(viewsets.ModelViewSet):
    serializer_class = InventoryAlertSerializer
    permission_classes = [permissions.IsAuthenticated]
    pagination_class = StandardResultsSetPagination

    def get_queryset(self):
        check_permission(self.request.user, page="inventory_alerts")
        queryset = InventoryAlert.objects.select_related('related_item', 'related_bin').order_by('-created_at')
        return queryset

    def perform_update(self, serializer):
        check_permission(self.request.user, action="update_inventory_alert")
        alert = serializer.save()
        log_activity(
            user=self.request.user,
            action='update',
            model_name='InventoryAlert',
            object_id=alert.id,
            object_name=f"Alert {alert.alert_type}",
            details={'alert_type': alert.alert_type, 'is_resolved': alert.is_resolved}
        )

    def perform_destroy(self, instance):
        check_permission(self.request.user, action="delete_inventory_alert")
        alert_id = instance.id
        alert_type = instance.alert_type
        instance.delete()
        log_activity(
            user=self.request.user,
            action='delete',
            model_name='InventoryAlert',
            object_id=alert_id,
            object_name=f"Alert {alert_type}",
            details={'deleted_alert': alert_type}
        )

class ExpiryTrackedItemViewSet(viewsets.ModelViewSet):
    serializer_class = ExpiryTrackedItemSerializer
    permission_classes = [permissions.IsAuthenticated]
    pagination_class = StandardResultsSetPagination

    def get_queryset(self):
        check_permission(self.request.user, page="expired_items")
        queryset = ExpiryTrackedItem.objects.filter(
            expiry_date__lt=timezone.now().date()
        ).select_related('item', 'user').order_by('-expiry_date')
        search = self.request.query_params.get('search', '').strip()
        if search:
            queryset = queryset.filter(
                Q(item__name__icontains=search) |
                Q(item__part_number__icontains=search) |
                Q(batch__icontains=search)
            )
        return queryset

    def perform_create(self, serializer):
        check_permission(self.request.user, action="create_expiry_tracked_item")
        expiry_item = serializer.save(user=self.request.user)
        log_activity(
            user=self.request.user,
            action='create',
            model_name='ExpiryTrackedItem',
            object_id=expiry_item.id,
            object_name=f"{expiry_item.item.name} - {expiry_item.batch}",
            details={
                'item_id': expiry_item.item.id,
                'item_name': expiry_item.item.name,
                'batch': expiry_item.batch,
                'expiry_date': expiry_item.expiry_date.isoformat()
            }
        )

    def perform_update(self, serializer):
        check_permission(self.request.user, action="update_expiry_tracked_item")
        expiry_item = serializer.save(user=self.request.user)
        log_activity(
            user=self.request.user,
            action='update',
            model_name='ExpiryTrackedItem',
            object_id=expiry_item.id,
            object_name=f"{expiry_item.item.name} - {expiry_item.batch}",
            details={'changes': 'Expiry tracked item updated'}
        )

    def perform_destroy(self, instance):
        check_permission(self.request.user, action="delete_expiry_tracked_item")
        item_name = instance.item.name if instance.item else 'Unknown Item'
        batch = instance.batch
        instance.delete()
        log_activity(
            user=self.request.user,
            action='delete',
            model_name='ExpiryTrackedItem',
            object_id=instance.id,
            object_name=f"{item_name} - {batch}",
            details={'deleted_item': item_name, 'batch': batch}
        )

class StockInView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        check_permission(request.user, action="stock_in")
        serializer = StockInSerializer(data=request.data, context={'request': request})
        if serializer.is_valid():
            serializer.save()
            return Response({"message": "Stock added successfully"}, status=201)
        logger.error(f"Stock In failed: {serializer.errors}")
        return Response(serializer.errors, status=400)

class StockOutView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        check_permission(request.user, action="stock_out")
        check_permission(request.user, action="create_warehouse_receipt")
        serializer = StockOutSerializer(data=request.data, context={'request': request})
        if serializer.is_valid():
            stock_movement = serializer.save()
            receipt = stock_movement.warehouse_receipt
            if not receipt:
                logger.error(
                    f"No WarehouseReceipt linked to StockMovement {stock_movement.id} "
                    f"by {request.user.email}"
                )
                return Response({
                    "message": "Stock removed successfully, but receipt creation failed",
                    "stock_movement_id": stock_movement.id
                }, status=status.HTTP_201_CREATED)
            return Response({
                "message": "Stock removed successfully",
                "stock_movement_id": stock_movement.id,
                "receipt_id": receipt.id,
                "receipt_number": receipt.receipt_number
            }, status=status.HTTP_201_CREATED)
        logger.error(f"Stock Out failed: {serializer.errors}")
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

class AnalyticsView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        check_permission(request.user, page="inventory_analytics")
        movements = StockMovement.objects.filter(
            timestamp__gte=timezone.now() - timezone.timedelta(days=30)
        ).aggregate(
            total_in=Sum('quantity', filter=Q(movement_type='IN')),
            total_out=Sum('quantity', filter=Q(movement_type='OUT'))
        )
        total_stock = StockRecord.objects.aggregate(total=Sum('quantity'))['total'] or 0
        turnover_rate = (movements['total_out'] or 0) / (total_stock or 1)
        bin_usage = StorageBin.objects.annotate(
            movement_count=Count('movements')
        ).order_by('-movement_count')[:5].values('bin_id', 'movement_count')
        alerts_over_time = InventoryAlert.objects.filter(
            created_at__gte=timezone.now() - timezone.timedelta(days=30)
        ).values('alert_type').annotate(count=Count('id'))
        data = {
            "turnover_rate": round(turnover_rate, 2),
            "most_used_bins": list(bin_usage),
            "alerts_over_time": list(alerts_over_time)
        }
        return Response(data)

class WarehouseViewSet(viewsets.ModelViewSet):
    serializer_class = WarehouseSerializer
    permission_classes = [permissions.IsAuthenticated]
    pagination_class = StandardResultsSetPagination

    def get_queryset(self):
        check_permission(self.request.user, page="warehouses")
        queryset = Warehouse.objects.all().order_by('-created_at')
        search = self.request.query_params.get('search', '').strip()
        if search:
            queryset = queryset.filter(
                Q(name__icontains=search) | Q(code__icontains=search) | Q(description__icontains=search)
            )
        return queryset

    def perform_create(self, serializer):
        check_permission(self.request.user, action="create_warehouse")
        warehouse = serializer.save(user=self.request.user)
        log_activity(
            user=self.request.user,
            action='create',
            model_name='Warehouse',
            object_id=warehouse.id,
            object_name=warehouse.name,
            details={'code': warehouse.code, 'capacity': warehouse.capacity}
        )

    def perform_update(self, serializer):
        check_permission(self.request.user, action="update_warehouse")
        warehouse = serializer.save()
        log_activity(
            user=self.request.user,
            action='update',
            model_name='Warehouse',
            object_id=warehouse.id,
            object_name=warehouse.name,
            details={'changes': 'Warehouse updated'}
        )

    def perform_destroy(self, instance):
        check_permission(self.request.user, action="delete_warehouse")
        bins = instance.bins.all()
        if bins.exists():
            return Response({
                'error': 'Cannot delete warehouse with bins.',
                'bin_count': bins.count(),
                'bin_ids': list(bins.values_list('id', flat=True))
            }, status=status.HTTP_400_BAD_REQUEST)
        warehouse_name = instance.name
        instance.delete()
        log_activity(
            user=self.request.user,
            action='delete',
            model_name='Warehouse',
            object_id=None,  # Already deleted
            object_name=warehouse_name,
            details={'deleted_warehouse': warehouse_name}
        )

    @action(detail=True, methods=['get'])
    def bins(self, request, pk=None):
        warehouse = self.get_object()
        bins = StorageBin.objects.filter(warehouse=warehouse).order_by('row', 'rack', 'shelf')
        serializer = StorageBinSerializer(bins, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=['post'])
    def add_bin(self, request, pk=None):
        warehouse = self.get_object()
        check_permission(request.user, action="create_storage_bin")
        if warehouse.bins.count() >= warehouse.capacity:
            return Response(
                {"error": f"Warehouse capacity exceeded. Maximum {warehouse.capacity} bins allowed."},
                status=status.HTTP_400_BAD_REQUEST
            )
        serializer = StorageBinSerializer(data=request.data, context={'request': request})
        if serializer.is_valid():
            storage_bin = serializer.save(warehouse=warehouse, user=request.user)
            log_activity(
                user=request.user,
                action='create',
                model_name='StorageBin',
                object_id=storage_bin.id,
                object_name=storage_bin.bin_id,
                details={
                    'warehouse_id': warehouse.id,
                    'warehouse_name': warehouse.name,
                    'bin_id': storage_bin.bin_id
                }
            )
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

class WarehouseAnalyticsView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, warehouse_id=None):
        try:
            check_permission(request.user, page="aisle_rack_dashboard")
            bins = StorageBin.objects.select_related('warehouse')
            if warehouse_id:
                bins = bins.filter(warehouse_id=warehouse_id)
                warehouse = Warehouse.objects.get(id=warehouse_id)
            else:
                warehouse = None
            total_bins = bins.count()
            if total_bins == 0:
                return Response({
                    'total_bins': 0,
                    'total_capacity': 0,
                    'total_used': 0,
                    'empty_bins': 0,
                    'loaded_bins': 0,
                    'utilization_percentage': 0,
                    'warehouse_info': {
                        'name': warehouse.name if warehouse else 'All Warehouses',
                        'capacity': warehouse.capacity if warehouse else Warehouse.objects.aggregate(Sum('capacity'))['capacity__sum'] or 0,
                        'used_capacity': warehouse.used_capacity if warehouse else 0,
                        'available_capacity': warehouse.available_capacity if warehouse else Warehouse.objects.aggregate(Sum('capacity'))['capacity__sum'] or 0,
                        'usage_percentage': warehouse.usage_percentage if warehouse else 0,
                    },
                    'usage_distribution': {
                        'empty': 0,
                        'low_usage': 0,
                        'medium_usage': 0,
                        'high_usage': 0
                    },
                    'message': 'No storage bins found'
                })
            from django.db.models import Case, When, FloatField, F, Q
            bins = bins.annotate(
                usage_pct=Case(
                    When(capacity=0, then=0),
                    default=(F('current_load') * 100.0 / F('capacity')),
                    output_field=FloatField()
                )
            )
            aggregation = bins.aggregate(
                total_capacity=Sum('capacity'),
                total_used=Sum('current_load'),
                empty=Count('id', filter=Q(current_load=0)),
                low_usage=Count('id', filter=Q(usage_pct__gt=0, usage_pct__lt=20)),
                medium_usage=Count('id', filter=Q(usage_pct__gte=20, usage_pct__lt=80)),
                high_usage=Count('id', filter=Q(usage_pct__gte=80))
            )
            total_capacity = aggregation['total_capacity'] or 0
            total_used = aggregation['total_used'] or 0
            empty_bins = aggregation['empty']
            loaded_bins = total_bins - empty_bins
            usage_distribution = {
                'empty': empty_bins,
                'low_usage': aggregation['low_usage'],
                'medium_usage': aggregation['medium_usage'],
                'high_usage': aggregation['high_usage']
            }
            utilization_percentage = 0
            if total_capacity > 0:
                utilization_percentage = round((total_used / total_capacity) * 100, 2)
            if warehouse:
                warehouse_info = {
                    'name': warehouse.name,
                    'capacity': warehouse.capacity,
                    'used_capacity': warehouse.used_capacity,
                    'available_capacity': warehouse.available_capacity,
                    'usage_percentage': warehouse.usage_percentage
                }
            else:
                total_warehouse_used = Warehouse.objects.aggregate(
                    total_used=Sum('bins__current_load')
                )['total_used'] or 0
                total_warehouse_capacity = Warehouse.objects.aggregate(
                    total_capacity=Sum('capacity')
                )['total_capacity'] or 0
                warehouse_info = {
                    'name': 'All Warehouses',
                    'capacity': total_warehouse_capacity,
                    'used_capacity': total_warehouse_used,
                    'available_capacity': total_warehouse_capacity - total_warehouse_used,
                    'usage_percentage': round((total_warehouse_used / total_warehouse_capacity * 100), 2) if total_warehouse_capacity > 0 else 0
                }
            analytics_data = {
                'total_bins': total_bins,
                'total_capacity': total_capacity,
                'total_used': total_used,
                'empty_bins': empty_bins,
                'loaded_bins': loaded_bins,
                'utilization_percentage': utilization_percentage,
                'warehouse_info': warehouse_info,
                'usage_distribution': usage_distribution,
                'warehouse_id': warehouse_id
            }
            return Response(analytics_data)
        except Exception as e:
            logger.error(f"Error in WarehouseAnalyticsView: {str(e)}")
            return Response({
                'error': 'Failed to fetch warehouse analytics',
                'details': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

class InventoryActivityLogViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = InventoryActivityLogSerializer
    permission_classes = [permissions.IsAuthenticated]
    pagination_class = StandardResultsSetPagination

    def get_queryset(self):
        check_permission(self.request.user, page="inventory_activity_logs")
        queryset = InventoryActivityLog.objects.select_related('user').order_by('-timestamp')
        return queryset

@api_view(['GET'])
@permission_classes([permissions.IsAuthenticated])
def get_unique_states(request):
    states = Warehouse.objects.exclude(state='').values_list('state', flat=True).distinct().order_by('state')
    return Response(list(states))

@api_view(['GET'])
@permission_classes([permissions.IsAuthenticated])
def get_unique_countries(request):
    countries = Warehouse.objects.exclude(country='').values_list('country', flat=True).distinct().order_by('country')
    return Response(list(countries))

@login_required
def warehouse_receipt_print(request, receipt_id):
    receipt = get_object_or_404(WarehouseReceipt, id=receipt_id)
    return render(request, 'inventory/receipt_print.html', {'receipt': receipt})

class WarehouseReceiptPDFView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, receipt_id):
        try:
            receipt = WarehouseReceipt.objects.select_related(
                'issued_from_warehouse',
                'issued_from_bin',
                'item',
                'created_by'
            ).get(id=receipt_id, created_by=request.user)
            buffer = BytesIO()
            doc = SimpleDocTemplate(
                buffer,
                pagesize=letter,
                topMargin=0.75 * inch,
                bottomMargin=0.75 * inch,
                leftMargin=0.75 * inch,
                rightMargin=0.75 * inch
            )
            elements = []
            styles = getSampleStyleSheet()
            title_style = ParagraphStyle(
                'ReceiptTitle', parent=styles['Heading1'],
                fontSize=16, alignment=1, spaceAfter=8, leading=20,
                textColor=colors.HexColor("#333333")
            )
            section_heading = ParagraphStyle(
                'SectionHeading', parent=styles['Heading3'],
                fontSize=10.5, spaceBefore=6, spaceAfter=6,
                textColor=colors.HexColor("#2b2b2b"), leading=13
            )
            small_info = ParagraphStyle(
                'SmallInfo', parent=styles['Normal'],
                fontSize=9, leading=12, textColor=colors.black
            )
            if hasattr(settings, 'COMPANY_LOGO_PATH'):
                try:
                    from reportlab.platypus import Image
                    logo_img = Image(settings.COMPANY_LOGO_PATH, width=1.5*inch, height=0.8*inch)
                    header_table = Table([[
                        logo_img,
                        Paragraph(f"<b>{getattr(settings, 'COMPANY_NAME', '')}</b><br/><span>{getattr(settings, 'COMPANY_TAGLINE', '')}</span>", styles['Title']),
                        Paragraph(
                            f"<b>Receipt No.</b><br/>{receipt.receipt_number}<br/><br/>"
                            f"<b>Date</b><br/>{receipt.created_at.strftime('%d/%m/%Y %H:%M')}",
                            small_info
                        )
                    ]], colWidths=[1.5*inch, 3.8*inch, 2.2*inch])
                    header_table.setStyle(TableStyle([
                        ('BACKGROUND', (0, 0), (0, 0), colors.HexColor("#B2B2B2")),
                        ('BACKGROUND', (1, 0), (1, 0), colors.white),
                        ('BACKGROUND', (2, 0), (2, 0), colors.HexColor("#F6F6F6")),
                        ('TEXTCOLOR', (0, 0), (-1, -1), colors.black),
                        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                        ('ALIGN', (2, 0), (2, 0), 'RIGHT'),
                        ('LEFTPADDING', (0, 0), (-1, -1), 8),
                        ('RIGHTPADDING', (0, 0), (-1, -1), 8),
                        ('TOPPADDING', (0, 0), (-1, -1), 10),
                        ('BOTTOMPADDING', (0, 0), (-1, -1), 10),
                        ('BOX', (0, 0), (-1, -1), 0.5, colors.HexColor("#D0D0D0")),
                    ]))
                    elements.append(header_table)
                    elements.append(Spacer(1, 12))
                except Exception as e:
                    logger.warning(f"Logo not found or failed to load: {str(e)}")
                    header_table = Table([[
                        Paragraph(f"<b>{getattr(settings, 'COMPANY_NAME', '')}</b>", styles['Title']),
                        Paragraph(
                            f"<b>Receipt No.</b><br/>{receipt.receipt_number}<br/><br/>"
                            f"<b>Date</b><br/>{receipt.created_at.strftime('%d/%m/%Y %H:%M')}",
                            small_info
                        )
                    ]], colWidths=[5.0*inch, 2.2*inch])
                    header_table.setStyle(TableStyle([
                        ('BACKGROUND', (0, 0), (0, 0), colors.HexColor("#B2B2B2")),
                        ('BACKGROUND', (1, 0), (1, 0), colors.HexColor("#F6F6F6")),
                        ('TEXTCOLOR', (0, 0), (-1, -1), colors.black),
                        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                        ('ALIGN', (1, 0), (1, 0), 'RIGHT'),
                        ('LEFTPADDING', (0, 0), (-1, -1), 8),
                        ('RIGHTPADDING', (0, 0), (-1, -1), 8),
                        ('TOPPADDING', (0, 0), (-1, -1), 10),
                        ('BOTTOMPADDING', (0, 0), (-1, -1), 10),
                        ('BOX', (0, 0), (-1, -1), 0.5, colors.HexColor("#D0D0D0")),
                    ]))
                    elements.append(header_table)
                    elements.append(Spacer(1, 12))
            else:
                header_table = Table([[
                    Paragraph(f"<b>{getattr(settings, 'COMPANY_NAME', '')}</b>", styles['Title']),
                    Paragraph(
                        f"<b>Receipt No.</b><br/>{receipt.receipt_number}<br/><br/>"
                        f"<b>Date</b><br/>{receipt.created_at.strftime('%d/%m/%Y %H:%M')}",
                        small_info
                    )
                ]], colWidths=[5.0*inch, 2.2*inch])
                header_table.setStyle(TableStyle([
                    ('BACKGROUND', (0, 0), (0, 0), colors.HexColor("#B2B2B2")),
                    ('BACKGROUND', (1, 0), (1, 0), colors.HexColor("#F6F6F6")),
                    ('TEXTCOLOR', (0, 0), (-1, -1), colors.black),
                    ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                    ('ALIGN', (1, 0), (1, 0), 'RIGHT'),
                    ('LEFTPADDING', (0, 0), (-1, -1), 8),
                    ('RIGHTPADDING', (0, 0), (-1, -1), 8),
                    ('TOPPADDING', (0, 0), (-1, -1), 10),
                    ('BOTTOMPADDING', (0, 0), (-1, -1), 10),
                    ('BOX', (0, 0), (-1, -1), 0.5, colors.HexColor("#D0D0D0")),
                ]))
                elements.append(header_table)
                elements.append(Spacer(1, 12))
            elements.append(Paragraph("WAREHOUSE STOCK OUT RECEIPT", title_style))
            elements.append(Spacer(1, 8))
            header_data = [
                ["Receipt No.", receipt.receipt_number],
                ["Date", receipt.created_at.strftime('%d/%m/%Y %H:%M')],
            ]
            header_table = Table(header_data, colWidths=[2.0*inch, 4.1*inch])
            header_table.setStyle(TableStyle([
                ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
                ('FONTSIZE', (0, 0), (-1, -1), 9),
                ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                ('GRID', (0, 0), (-1, -1), 0.4, colors.HexColor("#D7D7D7")),
                ('BACKGROUND', (0, 0), (0, -1), colors.HexColor("#F3F3F3")),
                ('BACKGROUND', (1, 0), (1, -1), colors.white),
                ('LEFTPADDING', (0, 0), (-1, -1), 6),
                ('RIGHTPADDING', (0, 0), (-1, -1), 6),
                ('TOPPADDING', (0, 0), (-1, -1), 6),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
            ]))
            elements.append(header_table)
            elements.append(Spacer(1, 12))
            elements.append(Paragraph("<b>ITEM DETAILS</b>", section_heading))
            elements.append(Spacer(1, 6))
            item_data = [
                ["Material ID", receipt.item.material_id if receipt.item else "—"],
                ["Description", receipt.item.name if receipt.item else "—"],
                ["Batch", receipt.item.batch if receipt.item else "—"],
                ["Quantity", str(receipt.quantity)],
            ]
            item_table = Table(item_data, colWidths=[2.0*inch, 4.1*inch])
            item_table.setStyle(TableStyle([
                ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
                ('FONTSIZE', (0, 0), (-1, -1), 9),
                ('VALIGN', (0, 0), (-1, -1), 'TOP'),
                ('GRID', (0, 0), (-1, -1), 0.35, colors.HexColor("#E0E0E0")),
                ('BACKGROUND', (0, 0), (0, -1), colors.HexColor("#FAFAFA")),
                ('LEFTPADDING', (0, 0), (-1, -1), 8),
                ('RIGHTPADDING', (0, 0), (-1, -1), 8),
                ('TOPPADING', (0, 0), (-1, -1), 6),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
            ]))
            elements.append(item_table)
            elements.append(Spacer(1, 12))
            elements.append(Paragraph("<b>LOCATION & DELIVERY</b>", section_heading))
            elements.append(Spacer(1, 6))
            location_data = [
                ["Plant / Site", receipt.plant_site or "—"],
                ["Bin", receipt.bin_location or "—"],
                ["Delivery To", receipt.delivery_to or "—"],
                ["Unloading Point", receipt.unloading_point or "—"],
                ["Recipient", receipt.recipient or "—"],
                ["Purpose", receipt.purpose or "—"],
            ]
            location_table = Table(location_data, colWidths=[2.0*inch, 4.1*inch])
            location_table.setStyle(TableStyle([
                ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
                ('FONTSIZE', (0, 0), (-1, -1), 9),
                ('VALIGN', (0, 0), (-1, -1), 'TOP'),
                ('GRID', (0, 0), (-1, -1), 0.35, colors.HexColor("#E0E0E0")),
                ('BACKGROUND', (0, 0), (0, -1), colors.HexColor("#FAFAFA")),
                ('LEFTPADDING', (0, 0), (-1, -1), 8),
                ('RIGHTPADDING', (0, 0), (-1, -1), 8),
                ('TOPPADDING', (0, 0), (-1, -1), 6),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
            ]))
            elements.append(location_table)
            elements.append(Spacer(1, 12))
            elements.append(Paragraph("<b>QUANTITIES</b>", section_heading))
            elements.append(Spacer(1, 6))
            qty_data = [
                ["Qty Picked", str(receipt.qty_picked)],
                ["Qty Remaining", str(receipt.qty_remaining)],
            ]
            qty_table = Table(qty_data, colWidths=[2.0*inch, 4.1*inch])
            qty_table.setStyle(TableStyle([
                ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
                ('FONTSIZE', (0, 0), (-1, -1), 9),
                ('VALIGN', (0, 0), (-1, -1), 'TOP'),
                ('GRID', (0, 0), (-1, -1), 0.35, colors.HexColor("#E0E0E0")),
                ('BACKGROUND', (0, 0), (0, -1), colors.HexColor("#FAFAFA")),
                ('LEFTPADDING', (0, 0), (-1, -1), 8),
                ('RIGHTPADDING', (0, 0), (-1, -1), 8),
                ('TOPPADDING', (0, 0), (-1, -1), 6),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
            ]))
            elements.append(qty_table)
            elements.append(Spacer(1, 12))
            elements.append(Paragraph("<b>SIGNATURES</b>", section_heading))
            elements.append(Spacer(1, 6))
            signature_data = [
                ["Picker", receipt.picker or "—"],
                ["Controller", receipt.controller or "—"],
            ]
            signature_table = Table(signature_data, colWidths=[2.0*inch, 4.1*inch])
            signature_table.setStyle(TableStyle([
                ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
                ('FONTSIZE', (0, 0), (-1, -1), 9),
                ('VALIGN', (0, 0), (-1, -1), 'TOP'),
                ('GRID', (0, 0), (-1, -1), 0.35, colors.HexColor("#E0E0E0")),
                ('BACKGROUND', (0, 0), (0, -1), colors.HexColor("#FAFAFA")),
                ('LEFTPADDING', (0, 0), (-1, -1), 8),
                ('RIGHTPADDING', (0, 0), (-1, -1), 8),
                ('TOPPADDING', (0, 0), (-1, -1), 14),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 14),
            ]))
            elements.append(signature_table)
            elements.append(Spacer(1, 18))
            footer_table = Table([[
                Paragraph("<i>This document is auto-generated. Signatures are required for validation.</i>", styles['Italic']),
                Paragraph(f"{getattr(settings, 'COMPANY_NAME', '')}", small_info)
            ]], colWidths=[4.6*inch, 2.0*inch])
            footer_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor("#333333")),
                ('TEXTCOLOR', (0, 0), (-1, -1), colors.whitesmoke),
                ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                ('ALIGN', (1, 0), (1, 0), 'RIGHT'),
                ('LEFTPADDING', (0, 0), (-1, -1), 10),
                ('RIGHTPADDING', (0, 0), (-1, -1), 10),
                ('TOPPADDING', (0, 0), (-1, -1), 8),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
            ]))
            elements.append(footer_table)
            doc.build(elements)
            item_name_safe = receipt.item.name.replace(' ', '_').replace('/', '-') if receipt.item else "Item"
            filename = f"{item_name_safe}_kenyon_receipt.pdf"
            buffer.seek(0)
            response = HttpResponse(buffer.getvalue(), content_type='application/pdf')
            response['Content-Disposition'] = f'attachment; filename="{filename}"'
            return response
        except WarehouseReceipt.DoesNotExist:
            return Response({'error': 'Receipt not found'}, status=404)
        except Exception as e:
            logger.error(f"PDF generation error: {str(e)}")
            return Response({'error': 'Failed to generate PDF'}, status=500)

class WarehouseReceiptViewSet(viewsets.ModelViewSet):
    serializer_class = WarehouseReceiptSerializer
    permission_classes = [permissions.IsAuthenticated]
    pagination_class = StandardResultsSetPagination

    def get_queryset(self):
        return WarehouseReceipt.objects.filter(created_by=self.request.user)

    def perform_update(self, serializer):
        check_permission(self.request.user, action="update_warehouse_receipt")
        serializer.save()

    def perform_destroy(self, instance):
        check_permission(self.request.user, action="delete_warehouse_receipt")
        instance.delete()


