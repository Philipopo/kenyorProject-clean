from django.contrib import admin
from .models import WarehouseItem

@admin.register(WarehouseItem)
class WarehouseItemAdmin(admin.ModelAdmin):
    list_display = ['id', 'item', 'storage_bin', 'quantity', 'status', 'last_updated']
    list_filter = ['status', 'storage_bin']
    search_fields = ['item__name', 'item__part_number', 'item__manufacturer', 'item__batch', 'storage_bin__bin_id']

    def get_queryset(self, request):
        return super().get_queryset(request).select_related('item', 'storage_bin')