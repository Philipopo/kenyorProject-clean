from rest_framework.routers import DefaultRouter
from .views import BranchViewSet, EquipmentViewSet, RentalViewSet, RentalPaymentViewSet

router = DefaultRouter()
router.register(r'branches', BranchViewSet)
router.register(r'equipment', EquipmentViewSet)
router.register(r'rentals', RentalViewSet)
router.register(r'payments', RentalPaymentViewSet)

urlpatterns = router.urls