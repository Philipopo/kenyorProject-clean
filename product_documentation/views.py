# product_documentation/views.py

from rest_framework import viewsets, permissions
from rest_framework.pagination import PageNumberPagination
from django.db.models import Q
from .models import ProductInflow, ProductOutflow, ProductDocumentationLog
from .serializers import ProductInflowSerializer, ProductOutflowSerializer
from accounts.permissions import DynamicPermission  # ✅ Use consistent permission system

class StandardResultsSetPagination(PageNumberPagination):
    page_size = 10
    page_size_query_param = 'page_size'
    max_page_size = 100

def log_activity(user, action, model_name, object_id, object_repr):
    ProductDocumentationLog.objects.create(
        user=user,
        action=action,
        model_name=model_name,
        object_id=object_id,
        object_repr=object_repr
    )

class ProductInflowViewSet(viewsets.ModelViewSet):
    serializer_class = ProductInflowSerializer
    permission_classes = [permissions.IsAuthenticated, DynamicPermission]
    page_permission_name = "product_documentation_new"

    def get_queryset(self):
        return ProductInflow.objects.select_related(
            'item', 
            'created_by',
            'created_by__profile'  # ✅ Required for full_name
        ).prefetch_related('serial_numbers').order_by('-id')  # ✅ Newest first

    def get_serializer_context(self):
        return {'request': self.request}

    def perform_create(self, serializer):
        inflow = serializer.save()
        ProductDocumentationLog.objects.create(
            user=self.request.user,
            action='create',
            model_name='ProductInflow',
            object_id=inflow.id,
            object_repr=f"{inflow.item.name} (Batch: {inflow.batch})"
        )

    def perform_update(self, serializer):
        inflow = serializer.save()
        ProductDocumentationLog.objects.create(
            user=self.request.user,
            action='update',
            model_name='ProductInflow',
            object_id=inflow.id,
            object_repr=f"{inflow.item.name} (Batch: {inflow.batch})"
        )

    def perform_destroy(self, instance):
        ProductDocumentationLog.objects.create(
            user=self.request.user,
            action='delete',
            model_name='ProductInflow',
            object_id=instance.id,
            object_repr=f"{instance.item.name} (Batch: {instance.batch})"
        )
        instance.delete()

class ProductOutflowViewSet(viewsets.ModelViewSet):
    serializer_class = ProductOutflowSerializer
    permission_classes = [permissions.IsAuthenticated, DynamicPermission]
    page_permission_name = "product_documentation"
    pagination_class = StandardResultsSetPagination

    def get_queryset(self):
        return ProductOutflow.objects.select_related('product__item', 'responsible_staff').all()

    def get_serializer_context(self):
        return {'request': self.request}

    def perform_create(self, serializer):
        outflow = serializer.save()
        log_activity(
            self.request.user,
            'create',
            'ProductOutflow',
            outflow.id,
            f"{outflow.product.item.name} to {outflow.customer_name}"
        )

    def perform_update(self, serializer):
        outflow = serializer.save()
        log_activity(
            self.request.user,
            'update',
            'ProductOutflow',
            outflow.id,
            f"{outflow.product.item.name} to {outflow.customer_name}"
        )

    def perform_destroy(self, instance):
        repr_str = f"{instance.product.item.name} to {instance.customer_name}"
        instance_id = instance.id
        instance.delete()
        log_activity(
            self.request.user,
            'delete',
            'ProductOutflow',
            instance_id,
            repr_str
        )