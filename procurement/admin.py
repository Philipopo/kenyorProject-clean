from django.contrib import admin
from .models import Requisition, PurchaseOrder, POItem, Receiving, Vendor
from .models import GoodsReceipt


admin.site.register(Requisition)
admin.site.register(POItem)
admin.site.register(Receiving)

@admin.register(GoodsReceipt)
class GoodsReceiptAdmin(admin.ModelAdmin):
    list_display = ('po_code', 'grn_code', 'invoice_code', 'match_success', 'timestamp')
    list_filter = ('match_success',)
    search_fields = ('po_code', 'grn_code', 'invoice_code')

@admin.register(Vendor)
class VendorAdmin(admin.ModelAdmin):
    list_display = ('name', 'lead_time', 'ratings')
    search_fields = ('name',)

@admin.register(PurchaseOrder)
class PurchaseOrderAdmin(admin.ModelAdmin):
    list_display = ('id', 'vendor', 'item_name', 'amount', 'status', 'date')
    list_filter = ('status', 'vendor')
    search_fields = ('item_name',)
