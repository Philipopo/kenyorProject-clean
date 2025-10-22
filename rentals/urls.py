# rentals/urls.py

from rest_framework.routers import DefaultRouter
from django.urls import path, include
from .views import BranchViewSet, EquipmentViewSet, RentalViewSet, RentalPaymentViewSet, ReservationViewSet, EquipmentReportPDFView, NotificationViewSet

router = DefaultRouter()
router.register(r'branches', BranchViewSet)
router.register(r'equipment', EquipmentViewSet)
router.register(r'rentals', RentalViewSet)
router.register(r'payments', RentalPaymentViewSet)
router.register(r'reservations', ReservationViewSet)
router.register(r'notifications', NotificationViewSet)

urlpatterns = [
    path('', include(router.urls)),
    path('reports/equipment-pdf/', EquipmentReportPDFView.as_view(), name='equipment-report-pdf'),
]