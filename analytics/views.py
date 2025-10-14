from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework.generics import ListAPIView
from rest_framework import status, viewsets
from accounts.views import check_permission
from accounts.permissions import DynamicPermission
from .models import DwellTime, EOQReport, EOQReportV2, StockAnalytics, ReorderQueue, Supplier
from .serializers import DwellTimeSerializer, EOQReportSerializer, EOQReportV2Serializer, StockAnalyticsSerializer, ReorderQueueSerializer, SupplierSerializer
from inventory.models import StockMovement, Item
from django.utils import timezone
from django.db.models import Sum
import math

class DashboardMetricsView(APIView):
    permission_classes = [IsAuthenticated, DynamicPermission]
    page_permission_name = 'analytics_dashboard'

    def get(self, request):
        user = request.user
        total_stock_items = Item.objects.filter(created_by=user).count()
        low_stock_items = Item.objects.filter(created_by=user, total_quantity__lte=Item._meta.get_field('min_stock_level').default).count()
        dwell_items = DwellTime.objects.filter(user=user).count()
        eoq_reports = EOQReportV2.objects.filter(user=user).count()
        reorder_queue = ReorderQueue.objects.filter(user=user, status='Pending').count()
        receipt_count = 0  # Placeholder for Receipt model

        metrics = [
            {"id": 1, "title": "Total Stock Items", "value": total_stock_items, "trend": "up", "change": "+12%"},
            {"id": 2, "title": "Low Stock Items", "value": low_stock_items, "trend": "down", "change": "-4%"},
            {"id": 3, "title": "Reorder Queue", "value": reorder_queue, "trend": "up", "change": "+8%"},
            {"id": 4, "title": "Dwell Records", "value": dwell_items, "trend": "neutral", "change": "0%"},
            {"id": 5, "title": "EOQ Reports", "value": eoq_reports, "trend": "up", "change": "+5%"},
            {"id": 6, "title": "Receipts Logged", "value": receipt_count, "trend": "up", "change": "+3%"},
        ]
        return Response({"metrics": metrics, "activities": []})

class UserDwellTimeListView(ListAPIView):
    serializer_class = DwellTimeSerializer
    permission_classes = [IsAuthenticated, DynamicPermission]
    page_permission_name = 'analytics_dwell'

    def get_queryset(self):
        return DwellTime.objects.filter(user=self.request.user)

    def post(self, request):
        check_permission(self.request.user, action='create_dwell')
        serializer = DwellTimeSerializer(data=request.data, context={'request': request})
        if serializer.is_valid():
            serializer.save(user=request.user)
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

class UserEOQReportListView(ListAPIView):
    serializer_class = EOQReportSerializer
    permission_classes = [IsAuthenticated, DynamicPermission]
    page_permission_name = 'analytics_eoq'

    def get_queryset(self):
        return EOQReport.objects.filter(user=self.request.user)

    def post(self, request):
        check_permission(self.request.user, action='create_eoq')
        serializer = EOQReportSerializer(data=request.data, context={'request': request})
        if serializer.is_valid():
            serializer.save(user=request.user)
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

class EOQReportV2ViewSet(viewsets.ModelViewSet):
    queryset = EOQReportV2.objects.all()
    serializer_class = EOQReportV2Serializer
    permission_classes = [IsAuthenticated, DynamicPermission]
    page_permission_name = 'analytics_eoq'

    def get_action_permission_name(self, action):
        return {
            'create': 'create_eoq',
            'update': 'update_eoq',
            'destroy': 'delete_eoq',
        }.get(action, None)

    def get_queryset(self):
        return EOQReportV2.objects.filter(user=self.request.user)

    def perform_create(self, serializer):
        check_permission(self.request.user, page=self.page_permission_name, action='create_eoq')
        serializer.save(user=self.request.user)

    def perform_update(self, serializer):
        check_permission(self.request.user, page=self.page_permission_name, action='update_eoq')
        serializer.save()

    def perform_destroy(self, instance):
        check_permission(self.request.user, page=self.page_permission_name, action='delete_eoq')
        instance.delete()

class UserStockAnalyticsListView(APIView):
    permission_classes = [IsAuthenticated, DynamicPermission]
    page_permission_name = 'analytics_stock'

    def get(self, request):
        data = StockAnalytics.objects.filter(user=request.user)
        serializer = StockAnalyticsSerializer(data, many=True)
        return Response(serializer.data)

    def post(self, request):
        check_permission(self.request.user, action='create_stock_analytics')
        serializer = StockAnalyticsSerializer(data=request.data, context={'request': request})
        if serializer.is_valid():
            serializer.save(user=request.user)
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

class ReorderQueueViewSet(viewsets.ModelViewSet):
    queryset = ReorderQueue.objects.all()
    serializer_class = ReorderQueueSerializer
    permission_classes = [IsAuthenticated, DynamicPermission]
    page_permission_name = 'analytics_reorder'

    def get_action_permission_name(self, action):
        return {
            'create': 'create_reorder',
            'update': 'update_reorder',
            'destroy': 'delete_reorder',
        }.get(action, None)

    def get_queryset(self):
        return ReorderQueue.objects.filter(user=self.request.user)

    def perform_create(self, serializer):
        check_permission(self.request.user, page=self.page_permission_name, action='create_reorder')
        serializer.save(user=self.request.user)

    def perform_update(self, serializer):
        check_permission(self.request.user, page=self.page_permission_name, action='update_reorder')
        serializer.save()

    def perform_destroy(self, instance):
        check_permission(self.request.user, page=self.page_permission_name, action='delete_reorder')
        instance.delete()

class SupplierViewSet(viewsets.ModelViewSet):
    queryset = Supplier.objects.all()
    serializer_class = SupplierSerializer
    permission_classes = [IsAuthenticated, DynamicPermission]
    page_permission_name = 'analytics_supplier'

    def get_action_permission_name(self, action):
        return {
            'create': 'create_supplier',
            'update': 'update_supplier',
            'destroy': 'delete_supplier',
        }.get(action, None)

    def get_queryset(self):
        return Supplier.objects.all()  # Shared across users for simplicity

    def perform_create(self, serializer):
        check_permission(self.request.user, page=self.page_permission_name, action='create_supplier')
        serializer.save()

    def perform_update(self, serializer):
        check_permission(self.request.user, page=self.page_permission_name, action='update_supplier')
        serializer.save()

    def perform_destroy(self, instance):
        check_permission(self.request.user, page=self.page_permission_name, action='delete_supplier')
        instance.delete()

class DemandForecastView(APIView):
    permission_classes = [IsAuthenticated, DynamicPermission]
    page_permission_name = 'analytics_forecast'

    def get(self, request):
        item_id = request.query_params.get('item_id')
        if not item_id:
            return Response({"error": "Item ID is required"}, status=status.HTTP_400_BAD_REQUEST)

        try:
            item = Item.objects.get(id=item_id, created_by=request.user)
        except Item.DoesNotExist:
            return Response({"error": "Item not found"}, status=status.HTTP_404_NOT_FOUND)

        # Calculate demand from last 6 months of StockMovement
        six_months_ago = timezone.now() - timezone.timedelta(days=180)
        movements = StockMovement.objects.filter(
            item=item,
            timestamp__gte=six_months_ago,
            movement_type='OUT'
        ).aggregate(total_demand=Sum('quantity'))

        total_demand = movements['total_demand'] or 0
        annualized_demand = round(total_demand * (365 / 180))  # Scale to yearly
        return Response({
            "item_id": item.id,
            "item_name": item.name,
            "forecasted_demand": annualized_demand,
            "period_days": 180
        })