# rentals/views.py
from rest_framework.viewsets import ModelViewSet
from rest_framework.permissions import IsAuthenticated
from rest_framework.pagination import PageNumberPagination
from rest_framework.decorators import action
from rest_framework.response import Response
from django.db.models import Q
from .models import Equipment, Rental, RentalPayment, Branch
from .serializers import EquipmentSerializer, RentalSerializer, RentalPaymentSerializer, BranchSerializer

class StandardResultsSetPagination(PageNumberPagination):
    page_size = 10
    page_size_query_param = 'page_size'
    max_page_size = 100

class BranchViewSet(ModelViewSet):
    queryset = Branch.objects.all().order_by('name')
    serializer_class = BranchSerializer
    permission_classes = [IsAuthenticated]
    pagination_class = StandardResultsSetPagination

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)

class EquipmentViewSet(ModelViewSet):
    queryset = Equipment.objects.select_related('branch', 'created_by').all().order_by('-created_at')
    serializer_class = EquipmentSerializer
    permission_classes = [IsAuthenticated]
    pagination_class = StandardResultsSetPagination

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)

class RentalViewSet(ModelViewSet):
    queryset = Rental.objects.select_related(
        'renter', 'equipment', 'branch', 'approved_by', 'created_by'
    ).all().order_by('-created_at')
    serializer_class = RentalSerializer
    permission_classes = [IsAuthenticated]
    pagination_class = StandardResultsSetPagination

    def get_queryset(self):
        user = self.request.user
        return self.queryset.filter(
            Q(renter=user) | Q(created_by=user) | Q(approved_by=user)
        )

    @action(detail=False, methods=['post'])
    def bulk_return(self, request):
        rental_ids = request.data.get('ids', [])
        if not rental_ids:
            return Response({'error': 'No rental IDs provided'}, status=400)
        
        updated = 0
        for rental_id in rental_ids:
            try:
                rental = Rental.objects.get(id=rental_id, returned=False)
                rental.returned = True
                rental.returned_at = timezone.now()
                rental.save()
                updated += 1
            except Rental.DoesNotExist:
                continue
        
        return Response({'message': f'{updated} rentals marked as returned.'})

    @action(detail=False, methods=['post'])
    def bulk_delete(self, request):
        rental_ids = request.data.get('ids', [])
        if not rental_ids:
            return Response({'error': 'No rental IDs provided'}, status=400)
        
        deleted = 0
        for rental_id in rental_ids:
            try:
                rental = Rental.objects.get(id=rental_id)
                rental.delete()
                deleted += 1
            except Rental.DoesNotExist:
                continue
        
        return Response({'message': f'{deleted} rentals deleted.'})
        

class RentalPaymentViewSet(ModelViewSet):
    queryset = RentalPayment.objects.select_related('rental__renter', 'rental__equipment').all().order_by('-created_at')
    serializer_class = RentalPaymentSerializer
    permission_classes = [IsAuthenticated]
    pagination_class = StandardResultsSetPagination

    def get_queryset(self):
        user = self.request.user
        return self.queryset.filter(
            Q(rental__renter=user) | 
            Q(rental__created_by=user) | 
            Q(created_by=user)
        )