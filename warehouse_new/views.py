from rest_framework import viewsets, permissions
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.exceptions import PermissionDenied
from django.db.models import Q
from rest_framework.pagination import PageNumberPagination
from .models import WarehouseItem
from .serializers import WarehouseItemSerializer, ItemSerializer
from inventory.models import Item
from accounts.models import PagePermission, ActionPermission, ROLE_LEVELS

class StandardResultsSetPagination(PageNumberPagination):
    page_size = 10
    page_size_query_param = 'page_size'
    max_page_size = 100

def get_user_role_level(user):
    return ROLE_LEVELS.get(user.role.lower(), 0)

def get_page_required_level(page):
    perm = PagePermission.objects.filter(page_name=page).first()
    return ROLE_LEVELS.get(perm.min_role.lower(), 1) if perm else 1

def get_action_required_level(action_name: str) -> int:
    try:
        perm = ActionPermission.objects.get(action_name=action_name)
        return ROLE_LEVELS.get(perm.min_role.lower(), 1)
    except ActionPermission.DoesNotExist:
        return 1

def check_permission(user, page=None, action=None):
    if not user.is_authenticated:
        raise PermissionDenied("User not authenticated")
    user_level = get_user_role_level(user)
    if page:
        required = get_page_required_level(page)
        if user_level < required:
            raise PermissionDenied(f"Access denied: {page} requires role level {required}")
    if action:
        required = get_action_required_level(action)
        if user_level < required:
            raise PermissionDenied(f"Access denied: {action} requires role level {required}")

class WarehouseItemViewSet(viewsets.ModelViewSet):
    serializer_class = WarehouseItemSerializer
    permission_classes = [permissions.IsAuthenticated]
    pagination_class = StandardResultsSetPagination

    def get_queryset(self):
        check_permission(self.request.user, page="warehouse_new")  # Updated page name
        queryset = WarehouseItem.objects.select_related('item', 'storage_bin').all()
        search = self.request.query_params.get('search', None)
        if search:
            queryset = queryset.filter(
                Q(item__name__icontains=search) |
                Q(item__part_number__icontains=search) |
                Q(item__manufacturer__icontains=search) |
                Q(item__batch__icontains=search) |
                Q(storage_bin__bin_id__icontains=search) |
                Q(status__icontains=search)
            )
        return queryset

    def perform_create(self, serializer):
        check_permission(self.request.user, action="create_warehouse_new_item")  # Updated action
        instance = serializer.save()
        instance.item.quantity -= instance.quantity
        instance.item.save()

    def perform_update(self, serializer):
        check_permission(self.request.user, action="update_warehouse_new_item")  # Updated action
        old_instance = self.get_object()
        instance = serializer.save()
        quantity_diff = instance.quantity - old_instance.quantity
        instance.item.quantity -= quantity_diff
        instance.item.save()

    def perform_destroy(self, instance):
        check_permission(self.request.user, action="delete_warehouse_new_item")  # Updated action
        instance.item.quantity += instance.quantity
        instance.item.save()
        instance.delete()

    @action(detail=False, methods=['get'], url_path='available_items')
    def available_items(self, request):
        check_permission(self.request.user, page="warehouse_new")  # Updated page name
        try:
            items = Item.objects.filter(quantity__gt=0)
            serializer = ItemSerializer(items, many=True)
            return Response(serializer.data)
        except Exception as e:
            return Response({"detail": f"Failed to fetch items: {str(e)}"}, status=400)