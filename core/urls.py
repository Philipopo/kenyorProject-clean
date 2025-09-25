# core/urls.py

from django.urls import path
from .views import test_api
from .views import dashboard_metrics

urlpatterns = [
    path('test/', test_api),
    path('dashboard-metrics/', dashboard_metrics),
]

