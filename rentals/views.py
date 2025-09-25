from rest_framework.viewsets import ModelViewSet
from rest_framework.permissions import IsAuthenticated
from rest_framework.pagination import PageNumberPagination
from django.db.models import Q
from .models import Equipment, Rental, RentalPayment
from .serializers import EquipmentSerializer, RentalSerializer, RentalPaymentSerializer
from accounts.permissions import DynamicPermission

class StandardResultsSetPagination(PageNumberPagination):
    page_size = 10
    page_size_query_param = 'page_size'
    max_page_size = 100

class EquipmentViewSet(ModelViewSet):
    queryset = Equipment.objects.all()
    serializer_class = EquipmentSerializer
    permission_classes = [IsAuthenticated, DynamicPermission]
    page_permission_name = 'rentals_equipment'
    required_permissions = {
        'create': 'create_equipment',
        'update': 'update_equipment',
        'partial_update': 'update_equipment',
        'destroy': 'delete_equipment',
    }
    pagination_class = StandardResultsSetPagination

    def get_queryset(self):
        queryset = Equipment.objects.filter(created_by=self.request.user)
        search = self.request.query_params.get('search', None)
        if search:
            queryset = queryset.filter(Q(name__icontains=search) | Q(category__icontains=search) | Q(location__icontains=search))
        return queryset.order_by('-created_at')

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)

    def perform_update(self, serializer):
        serializer.save(created_by=self.request.user)




class RentalViewSet(ModelViewSet):
    queryset = Rental.objects.select_related('renter', 'equipment').all()
    serializer_class = RentalSerializer
    permission_classes = [IsAuthenticated, DynamicPermission]
    page_permission_name = 'rentals_active'
    required_permissions = {
        'create': 'create_rental',
        'update': 'update_rental',
        'partial_update': 'update_rental',
        'destroy': 'delete_rental',
    }
    pagination_class = StandardResultsSetPagination

    def get_queryset(self):
        queryset = Rental.objects.filter(created_by=self.request.user).select_related('renter', 'equipment')
        search = self.request.query_params.get('search', None)
        if search:
            queryset = queryset.filter(
                Q(renter__full_name__icontains=search) |
                Q(equipment__name__icontains=search) |
                Q(code__icontains=search)
            )
        return queryset.order_by('-created_at')

    # ✅ Let the serializer handle renter/created_by
    def perform_create(self, serializer):
        try:
            serializer.save()
        except Exception as e:
            #logger.error(f"Error creating rental: {str(e)}")
            print(f"Error creating rental: {str(e)}")

            raise

        

class RentalPaymentViewSet(ModelViewSet):
    queryset = RentalPayment.objects.select_related('rental__renter', 'rental__equipment').all()
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
        queryset = RentalPayment.objects.filter(created_by=self.request.user).select_related('rental__renter', 'rental__equipment')
        search = self.request.query_params.get('search', None)
        if search:
            queryset = queryset.filter(
                Q(rental__renter__full_name__icontains=search) | Q(rental__equipment__name__icontains=search)
            )
        return queryset.order_by('-created_at')

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)

    def perform_update(self, serializer):
        serializer.save(created_by=self.request.user)