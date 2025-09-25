from django.contrib import admin
from .models import Item, StorageBin, StockRecord, StockMovement, InventoryAlert, ExpiryTrackedItem

@admin.register(Item)
class ItemAdmin(admin.ModelAdmin):
    list_display = ('name', 'part_number', 'total_quantity', 'available_quantity', 'created_at')
    search_fields = ('name', 'part_number')

@admin.register(StorageBin)
class StorageBinAdmin(admin.ModelAdmin):
    list_display = ('bin_id', 'row', 'rack', 'capacity', 'current_load')
    search_fields = ('bin_id', 'row', 'rack')

@admin.register(StockRecord)
class StockRecordAdmin(admin.ModelAdmin):
    list_display = ('item', 'storage_bin', 'quantity', 'created_at')
    search_fields = ('item__name', 'storage_bin__bin_id')

@admin.register(StockMovement)
class StockMovementAdmin(admin.ModelAdmin):
    list_display = ('item', 'storage_bin', 'movement_type', 'quantity', 'timestamp')
    search_fields = ('item__name', 'storage_bin__bin_id')

@admin.register(InventoryAlert)
class InventoryAlertAdmin(admin.ModelAdmin):
    list_display = ('alert_type', 'message', 'created_at', 'is_resolved')
    search_fields = ('message',)

@admin.register(ExpiryTrackedItem)
class ExpiryTrackedItemAdmin(admin.ModelAdmin):
    list_display = ('item', 'batch', 'quantity', 'expiry_date')
    search_fields = ('item__name', 'batch')