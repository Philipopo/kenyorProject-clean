from django.contrib import admin
from django.utils.html import format_html
from .models import (
    Vendor, Requisition, RequisitionItem, PurchaseOrder, 
    POItem, Receiving, ReceivingItem, ProcurementAuditLog
)

@admin.register(Vendor)
class VendorAdmin(admin.ModelAdmin):
    list_display = ['name', 'contact_person', 'email', 'phone', 'ratings', 'status', 'lead_time', 'created_by']
    list_filter = ['status', 'ratings', 'created_at']
    search_fields = ['name', 'contact_person', 'email']
    readonly_fields = ['created_at', 'updated_at']
    fieldsets = (
        ('Vendor Information', {
            'fields': ('name', 'contact_person', 'email', 'phone', 'address', 'tax_id')
        }),
        ('Business Details', {
            'fields': ('details', 'lead_time', 'ratings', 'status', 'document')
        }),
        ('Audit', {
            'fields': ('created_by', 'created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )

class RequisitionItemInline(admin.TabularInline):
    model = RequisitionItem
    extra = 1
    readonly_fields = ['total_cost']

@admin.register(Requisition)
class RequisitionAdmin(admin.ModelAdmin):
    list_display = ['code', 'department', 'status', 'priority', 'requested_by', 'created_at']
    list_filter = ['status', 'priority', 'department', 'created_at']
    search_fields = ['code', 'department', 'purpose', 'requested_by__email']
    readonly_fields = ['code', 'approved_at', 'created_at', 'updated_at']
    inlines = [RequisitionItemInline]
    fieldsets = (
        ('Requisition Details', {
            'fields': ('code', 'department', 'purpose', 'priority')
        }),
        ('Status & Approval', {
            'fields': ('status', 'approved_by', 'approved_at')
        }),
        ('Audit', {
            'fields': ('requested_by', 'created_by', 'created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )

class POItemInline(admin.TabularInline):
    model = POItem
    extra = 1
    readonly_fields = ['total_price', 'received_quantity']

@admin.register(PurchaseOrder)
class PurchaseOrderAdmin(admin.ModelAdmin):
    list_display = ['code', 'vendor', 'department', 'status', 'total_amount', 'created_by', 'created_at']
    list_filter = ['status', 'department', 'created_at', 'vendor']
    search_fields = ['code', 'vendor__name', 'department', 'notes']
    readonly_fields = ['code', 'total_amount', 'approved_at', 'created_at', 'updated_at']
    inlines = [POItemInline]
    fieldsets = (
        ('PO Details', {
            'fields': ('code', 'requisition', 'vendor', 'department', 'delivery_address')
        }),
        ('Financial', {
            'fields': ('total_amount', 'tax_amount', 'discount_amount', 'payment_terms')
        }),
        ('Status & Approval', {
            'fields': ('status', 'expected_delivery_date', 'approved_by', 'approved_at')
        }),
        ('Notes', {
            'fields': ('notes',)
        }),
        ('Audit', {
            'fields': ('created_by', 'created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )

class ReceivingItemInline(admin.TabularInline):
    model = ReceivingItem
    extra = 1
    readonly_fields = ['rejected_quantity']

@admin.register(Receiving)
class ReceivingAdmin(admin.ModelAdmin):
    list_display = ['grn', 'po_code', 'vendor_name', 'status', 'received_by', 'created_at']
    list_filter = ['status', 'created_at', 'po__vendor']
    search_fields = ['grn', 'po__code', 'invoice_number', 'received_by__email']
    readonly_fields = ['grn', 'created_at', 'updated_at']
    inlines = [ReceivingItemInline]
    fieldsets = (
        ('Receiving Details', {
            'fields': ('po', 'grn', 'invoice_number', 'invoice_date')
        }),
        ('Status', {
            'fields': ('status', 'received_by')
        }),
        ('Documents', {
            'fields': ('document', 'notes')
        }),
        ('Audit', {
            'fields': ('created_by', 'created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )

    def po_code(self, obj):
        return obj.po.code if obj.po else '-'
    po_code.short_description = 'PO Code'

    def vendor_name(self, obj):
        return obj.po.vendor.name if obj.po and obj.po.vendor else '-'
    vendor_name.short_description = 'Vendor'

@admin.register(ProcurementAuditLog)
class ProcurementAuditLogAdmin(admin.ModelAdmin):
    list_display = ['user', 'action', 'model_name', 'object_id', 'created_at']
    list_filter = ['action', 'model_name', 'created_at']
    search_fields = ['user__email', 'model_name', 'details']
    readonly_fields = ['user', 'action', 'model_name', 'object_id', 'details', 'created_at']
    
    def has_add_permission(self, request):
        return False
    
    def has_change_permission(self, request, obj=None):
        return False