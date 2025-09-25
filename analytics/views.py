from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework.generics import ListAPIView
from rest_framework import status, viewsets
from accounts.views import check_permission
from accounts.permissions import DynamicPermission
from .models import DwellTime, EOQReport, EOQReportV2, StockAnalytics
from .serializers import DwellTimeSerializer, EOQReportSerializer, EOQReportV2Serializer, StockAnalyticsSerializer

class DashboardMetricsView(APIView):
    permission_classes = [IsAuthenticated, DynamicPermission]
    page_permission_name = 'analytics_dashboard'

    def get(self, request):
        user = request.user
        total_stock_items = StockAnalytics.objects.filter(user=user).count()
        low_stock_items = StockAnalytics.objects.filter(user=user, category='C').count()
        dwell_items = DwellTime.objects.filter(user=user).count()
        eoq_reports = EOQReportV2.objects.filter(user=user).count()  # Updated to V2
        receipt_count = 0  # Placeholder for Receipt model

        metrics = [
            {"id": 1, "title": "Total Stock Items", "value": total_stock_items, "trend": "up", "change": "+12%"},
            {"id": 2, "title": "Low Stock Items", "value": low_stock_items, "trend": "down", "change": "-4%"},
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