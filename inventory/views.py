from rest_framework import viewsets, permissions, status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied
from django.db.models import Q, Sum, Count
from rest_framework.pagination import PageNumberPagination
from django.utils import timezone
from django.db import transaction
import logging
from .models import Warehouse, StorageBin, Item, StockRecord, StockMovement, InventoryAlert, ExpiryTrackedItem
from .serializers import (
    WarehouseSerializer, StorageBinSerializer, ItemSerializer, StockRecordSerializer, 
    StockMovementSerializer, InventoryAlertSerializer, ExpiryTrackedItemSerializer, 
    StockInSerializer, StockOutSerializer
)

from accounts.permissions import APIKeyPermission
from accounts.models import PagePermission, ActionPermission

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
        serializer.save(user=self.request.user)

    def perform_update(self, serializer):
        check_permission(self.request.user, action="update_item")
        serializer.save(user=self.request.user)

    def perform_destroy(self, instance):
        check_permission(self.request.user, action="delete_item")
        if instance.stock_records.exists():
            raise PermissionDenied("Cannot delete item with stock records.")
        instance.delete()

class StorageBinViewSet(viewsets.ModelViewSet):
    serializer_class = StorageBinSerializer
    permission_classes = [permissions.IsAuthenticated]
    pagination_class = StandardResultsSetPagination

    def get_queryset(self):
        check_permission(self.request.user, page="storage_bins")
        queryset = StorageBin.objects.select_related('warehouse').all().order_by('-created_at')
        
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
        
        # Check warehouse capacity if warehouse is assigned
        warehouse = serializer.validated_data.get('warehouse')
        if warehouse:
            if warehouse.bins.count() >= warehouse.capacity:
                raise PermissionDenied(f"Warehouse capacity exceeded. Maximum {warehouse.capacity} bins allowed.")
        
        serializer.save(user=self.request.user)

    def perform_update(self, serializer):
        check_permission(self.request.user, action="update_storage_bin")
        serializer.save()

    def perform_destroy(self, instance):
        check_permission(self.request.user, action="delete_storage_bin")
        if instance.current_load > 0:
            raise PermissionDenied("Cannot delete bin with stock.")
        instance.delete()

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
        serializer.save(user=self.request.user)

    def perform_update(self, serializer):
        check_permission(self.request.user, action="update_stock_record")
        serializer.save(user=self.request.user)

    def perform_destroy(self, instance):
        check_permission(self.request.user, action="delete_stock_record")
        instance.delete()

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
        serializer.save()

    def perform_destroy(self, instance):
        check_permission(self.request.user, action="delete_inventory_alert")
        instance.delete()

class ExpiryTrackedItemViewSet(viewsets.ModelViewSet):
    serializer_class = ExpiryTrackedItemSerializer
    permission_classes = [permissions.IsAuthenticated]
    pagination_class = StandardResultsSetPagination

    def get_queryset(self):
        check_permission(self.request.user, page="expired_items")
        
        # Only show EXPIRED items on this page
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
        serializer.save(user=self.request.user)

    def perform_update(self, serializer):
        check_permission(self.request.user, action="update_expiry_tracked_item")
        serializer.save(user=self.request.user)

    def perform_destroy(self, instance):
        check_permission(self.request.user, action="delete_expiry_tracked_item")
        instance.delete()

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
            serializer.save()
            return Response({"message": "Stock removed successfully"}, status=201)
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
        serializer.save(user=self.request.user)

    def perform_update(self, serializer):
        check_permission(self.request.user, action="update_warehouse")
        serializer.save()

    def perform_destroy(self, instance):
        check_permission(self.request.user, action="delete_warehouse")
        if instance.bins.exists():
            raise PermissionDenied("Cannot delete warehouse with assigned bins.")
        instance.delete()

    @action(detail=True, methods=['get'])
    def bins(self, request, pk=None):
        """Get all bins for a specific warehouse"""
        warehouse = self.get_object()
        bins = StorageBin.objects.filter(warehouse=warehouse).order_by('row', 'rack', 'shelf')
        serializer = StorageBinSerializer(bins, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=['post'])
    def add_bin(self, request, pk=None):
        """Add a new bin to this warehouse"""
        warehouse = self.get_object()
        check_permission(request.user, action="create_storage_bin")
        
        # Check warehouse capacity
        if warehouse.bins.count() >= warehouse.capacity:
            return Response(
                {"error": f"Warehouse capacity exceeded. Maximum {warehouse.capacity} bins allowed."},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        serializer = StorageBinSerializer(data=request.data, context={'request': request})
        if serializer.is_valid():
            serializer.save(warehouse=warehouse, user=request.user)
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)




class WarehouseAnalyticsView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, warehouse_id=None):
        try:
            # FIXED: Use 'aisle_rack_dashboard' to match React frontend
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
            
            # OPTIMIZED: Use database annotations instead of Python loop
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
            
            # Warehouse info
            if warehouse:
                warehouse_info = {
                    'name': warehouse.name,
                    'capacity': warehouse.capacity,
                    'used_capacity': warehouse.used_capacity,
                    'available_capacity': warehouse.available_capacity,
                    'usage_percentage': warehouse.usage_percentage
                }
            else:
                # OPTIMIZED: Use single query instead of Python sum
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