# finance/urls.py
from django.urls import path
from rest_framework.routers import DefaultRouter
from .views import FinanceCategoryViewSet, FinanceTransactionViewSet, FinanceOverview

router = DefaultRouter()
router.register(r'categories', FinanceCategoryViewSet, basename='finance-categories')
router.register(r'transactions', FinanceTransactionViewSet, basename='finance-transactions')

urlpatterns = [
    path('overview/', FinanceOverview.as_view(), name='finance-overview'),
] + router.urls