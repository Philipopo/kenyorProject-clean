import csv
from rest_framework import viewsets, permissions, status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.decorators import permission_classes
from rest_framework.decorators import api_view  # ← ADD THIS LINE
from rest_framework.decorators import action
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
    StockInSerializer, StockOutSerializer, InventoryActivityLogSerializer
)

from accounts.permissions import APIKeyPermission
from accounts.models import PagePermission, ActionPermission
from django.http import JsonResponse
from rest_framework.decorators import action
from rest_framework.parsers import MultiPartParser, FormParser
from django.shortcuts import render, get_object_or_404
from django.contrib.auth.decorators import login_required


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
            queryset = queryset.filter(Q(name__icontains=search) | Q(part_number__icontains=search))
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
            object_id=instance.id,
            object_name=item_name,
            details={'deleted_item': item_name}
        )


    def get_queryset(self):
        check_permission(self.request.user, page="items")
        queryset = Item.objects.all().order_by('-id')
        search = self.request.query_params.get('search', '').strip()
        if search:
            queryset = queryset.filter(
                Q(name__icontains=search) |
                Q(part_number__icontains=search) |
                Q(material_id__icontains=search)  # ← Add this
            )
        return queryset
    





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
            'stock_records__item',  # This ensures item data is loaded efficiently
            'stock_records__storage_bin'
        ).all().order_by('-created_at')
        # Filter by warehouse if provided
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
        serializer = StockOutSerializer(data=request.data, context={'request': request})
        if serializer.is_valid():
            # Save the stock movement
            movement = serializer.save()

            # Auto-create a warehouse receipt for Stock Out
            try:
                receipt = WarehouseReceipt.objects.create(
                    issued_from_warehouse=movement.storage_bin.warehouse,
                    issued_from_bin=movement.storage_bin,
                    item=movement.item,
                    quantity=movement.quantity,
                    recipient="N/A",  # Will be updated later via receipt edit
                    purpose=request.data.get('notes', ''),
                    created_by=request.user,
                    stock_movement=movement,
                    # Auto-filled fields
                    delivery_to="",
                    transfer_order_no="",
                    plant_site=movement.storage_bin.warehouse.code,
                    bin_location=movement.storage_bin.bin_id,
                    qty_picked=movement.quantity,
                    qty_remaining=movement.item.available_quantity(),
                    unloading_point="",
                    original_document="",
                    old_material_no="",
                    picker="",
                    controller=""
                )
            except Exception as e:
                logger.warning(f"Failed to create warehouse receipt: {e}")
                receipt = None

            response_data = {"message": "Stock removed successfully"}
            if receipt:
                response_data["receipt_id"] = receipt.id
                response_data["receipt_number"] = receipt.receipt_number

            return Response(response_data, status=201)

        logger.error(f"Stock Out failed: {serializer.errors}")
        return Response(serializer.errors, status=400)

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
        if instance.bins.exists():
            raise PermissionDenied("Cannot delete warehouse with assigned bins.")
        
        warehouse_name = instance.name
        instance.delete()
        log_activity(
            user=self.request.user,
            action='delete',
            model_name='Warehouse',
            object_id=instance.id,
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
    """Return list of unique non-empty countries from warehouses."""
    countries = Warehouse.objects.exclude(country='').values_list('country', flat=True).distinct().order_by('country')
    return Response(list(countries))



@login_required
def warehouse_receipt_print(request, receipt_id):
    receipt = get_object_or_404(WarehouseReceipt, id=receipt_id)
    return render(request, 'inventory/receipt_print.html', {'receipt': receipt})