# product_documentation/admin.py
from django.contrib import admin
from .models import ProductInflow, ProductSerialNumber, ProductOutflow

@admin.register(ProductInflow)
class ProductInflowAdmin(admin.ModelAdmin):
    list_display = ['get_item_name', 'batch', 'date_of_delivery', 'vendor', 'quantity', 'cost', 'created_by']
    list_filter = ['date_of_delivery', 'vendor', 'created_by']
    search_fields = ['item__name', 'batch', 'vendor']
    date_hierarchy = 'date_of_delivery'
    ordering = ['-date_of_delivery']

    def get_item_name(self, obj):
        return obj.item.name
    get_item_name.short_description = 'Item Name'

@admin.register(ProductSerialNumber)
class ProductSerialNumberAdmin(admin.ModelAdmin):
    list_display = ['serial_number', 'inflow', 'status', 'created_at']
    list_filter = ['status', 'created_at']
    search_fields = ['serial_number', 'inflow__item__name']

@admin.register(ProductOutflow)
class ProductOutflowAdmin(admin.ModelAdmin):
    list_display = ['get_product_name', 'customer_name', 'dispatch_date', 'quantity', 'responsible_staff']
    list_filter = ['dispatch_date', 'customer_name']
    search_fields = ['customer_name', 'sales_order', 'product__item__name']
    date_hierarchy = 'dispatch_date'

    def get_product_name(self, obj):
        return obj.product.item.name
    get_product_name.short_description = 'Product Name'