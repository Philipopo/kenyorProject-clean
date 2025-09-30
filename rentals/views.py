from rest_framework.viewsets import ModelViewSet
from rest_framework.permissions import IsAuthenticated
from rest_framework.pagination import PageNumberPagination
from django.db.models import Q
from .models import Equipment, Rental, RentalPayment, Branch
from .serializers import EquipmentSerializer, RentalSerializer, RentalPaymentSerializer, BranchSerializer
from accounts.permissions import DynamicPermission

class StandardResultsSetPagination(PageNumberPagination):
    page_size = 10
    page_size_query_param = 'page_size'
    max_page_size = 100

class BranchViewSet(ModelViewSet):
    queryset = Branch.objects.all().order_by('name')
    serializer_class = BranchSerializer
    permission_classes = [IsAuthenticated, DynamicPermission]
    page_permission_name = 'branches'
    pagination_class = StandardResultsSetPagination

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)

class EquipmentViewSet(ModelViewSet):
    queryset = Equipment.objects.select_related('branch', 'created_by').all().order_by('-created_at')
    serializer_class = EquipmentSerializer
    permission_classes = [IsAuthenticated, DynamicPermission]
    page_permission_name = 'rentals_equipment'
    pagination_class = StandardResultsSetPagination

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)

class RentalViewSet(ModelViewSet):
    queryset = Rental.objects.select_related(
        'renter', 'equipment', 'branch', 'approved_by', 'created_by'
    ).all().order_by('-created_at')
    serializer_class = RentalSerializer
    permission_classes = [IsAuthenticated, DynamicPermission]
    page_permission_name = 'rentals_active'
    pagination_class = StandardResultsSetPagination

    def get_queryset(self):
        user = self.request.user
        return self.queryset.filter(
            Q(renter=user) | Q(created_by=user) | Q(approved_by=user)
        )

class RentalPaymentViewSet(ModelViewSet):
    queryset = RentalPayment.objects.select_related('rental__renter', 'rental__equipment').all().order_by('-created_at')
    serializer_class = RentalPaymentSerializer
    permission_classes = [IsAuthenticated, DynamicPermission]
    page_permission_name = 'rentals_payments'
    required_permissions = {
        'create': 'create_payment',
        'update': 'update_payment',
        'partial_update': 'update_payment',
        'destroy': 'delete_payment',
    }
    pagination_class = StandardResultsSetPagination

    def get_queryset(self):
        user = self.request.user
        return self.queryset.filter(
            Q(rental__renter=user) | 
            Q(rental__created_by=user) | 
            Q(created_by=user)
        )