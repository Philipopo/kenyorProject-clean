from django.contrib import admin
from .models import ProductInflow, ProductOutflow, SerialNumber

@admin.register(ProductInflow)
class ProductInflowAdmin(admin.ModelAdmin):
    list_display = ('item_name', 'batch', 'vendor', 'date_of_delivery', 'quantity', 'cost', 'created_at')
    list_filter = ('vendor', 'date_of_delivery', 'created_at')
    search_fields = ('item__name', 'batch', 'vendor')
    date_hierarchy = 'date_of_delivery'
    ordering = ('-created_at',)

    def item_name(self, obj):
        return obj.item.name
    item_name.short_description = 'Item Name'

    def get_queryset(self, request):
        return super().get_queryset(request).select_related('item')

@admin.register(ProductOutflow)
class ProductOutflowAdmin(admin.ModelAdmin):
    list_display = ('product_item_name', 'customer_name', 'sales_order', 'dispatch_date', 'quantity', 'created_at', 'updated_at')
    list_filter = ('customer_name', 'dispatch_date', 'created_at')
    search_fields = ('product__item__name', 'customer_name', 'sales_order')
    date_hierarchy = 'dispatch_date'
    ordering = ('-created_at',)

    def product_item_name(self, obj):
        return obj.product.item.name
    product_item_name.short_description = 'Product Item Name'

    def get_queryset(self, request):
        return super().get_queryset(request).select_related('product__item')

@admin.register(SerialNumber)
class SerialNumberAdmin(admin.ModelAdmin):
    list_display = ('serial_number', 'product_inflow', 'product_outflow', 'status', 'created_at', 'updated_at')
    list_filter = ('status', 'created_at')
    search_fields = ('serial_number', 'product_inflow__item__name', 'product_inflow__batch')
    ordering = ('-created_at',)

    def get_queryset(self, request):
        return super().get_queryset(request).select_related('product_inflow__item', 'product_outflow')