from django.urls import path
from .views import AlertListCreateView

urlpatterns = [
    path('', AlertListCreateView.as_view(), name='alert-list-create'),
]
