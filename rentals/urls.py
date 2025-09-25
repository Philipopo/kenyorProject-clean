from rest_framework.routers import DefaultRouter
from .views import EquipmentViewSet, RentalViewSet, RentalPaymentViewSet

router = DefaultRouter()
router.register(r'equipment', EquipmentViewSet)
router.register(r'rentals', RentalViewSet)
router.register(r'payments', RentalPaymentViewSet)

urlpatterns = router.urls