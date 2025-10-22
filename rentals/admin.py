# rentals/admin.py

from django.contrib import admin
from django.utils.html import format_html
from .models import Branch, Equipment, Rental, RentalPayment, Reservation, Notification, RentalReceipt


@admin.register(Branch)
class BranchAdmin(admin.ModelAdmin):
    list_display = ('name', 'code', 'address', 'created_by', 'created_at')
    list_filter = ('created_at',)
    search_fields = ('name', 'code', 'address')
    readonly_fields = ('created_by', 'created_at', 'updated_at')
    date_hierarchy = 'created_at'

    def save_model(self, request, obj, form, change):
        if not change:
            obj.created_by = request.user
        super().save_model(request, obj, form, change)


@admin.register(Equipment)
class EquipmentAdmin(admin.ModelAdmin):
    list_display = (
        'name', 'category', 'condition', 'location', 'branch',
        'total_quantity', 'available_quantity', 'created_by', 'created_at', 'image_preview'
    )
    list_filter = ('category', 'condition', 'branch', 'created_at')
    search_fields = ('name', 'category', 'location', 'description')
    readonly_fields = ('created_by', 'created_at', 'image_preview')
    date_hierarchy = 'created_at'

    def image_preview(self, obj):
        if obj.image:
            return format_html(
                '<img src="{}" style="max-height: 50px; max-width: 50px; border: 1px solid #ddd;" />',
                obj.image.url
            )
        return "No image"
    image_preview.short_description = "Image Preview"

    def save_model(self, request, obj, form, change):
        if not change:
            obj.created_by = request.user
        super().save_model(request, obj, form, change)


@admin.register(Reservation)
class ReservationAdmin(admin.ModelAdmin):
    list_display = (
        'equipment', 'start_date', 'end_date',
        'quantity', 'is_active', 'created_at'
    )
    list_filter = ('is_active', 'start_date', 'end_date', 'created_at')
    search_fields = (
        'equipment__name', 'reserved_for__email',
        'reserved_for__first_name', 'reserved_for__last_name'
    )
    
    date_hierarchy = 'created_at'


    def save_model(self, request, obj, form, change):
        if not change:
            obj.created_by = request.user
        super().save_model(request, obj, form, change)


@admin.register(Rental)
class RentalAdmin(admin.ModelAdmin):
    list_display = (
        'code', 'renter', 'equipment', 'branch', 'start_date',
        'effective_due_date', 'quantity', 'returned', 'created_at'
    )
    list_filter = ('returned', 'start_date', 'due_date', 'branch', 'created_at')
    search_fields = (
        'code', 'renter__email', 'renter__first_name',
        'renter__last_name', 'equipment__name'
    )
    readonly_fields = ('code', 'created_by', 'created_at', 'total_rental_cost', 'total_paid', 'balance_due')
    date_hierarchy = 'created_at'

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if db_field.name == "renter":
            kwargs["queryset"] = db_field.remote_field.model.objects.all()
        return super().formfield_for_foreignkey(db_field, request, **kwargs)

    def save_model(self, request, obj, form, change):
        if not change:
            obj.created_by = request.user
        super().save_model(request, obj, form, change)


@admin.register(RentalPayment)
class RentalPaymentAdmin(admin.ModelAdmin):
    list_display = (
        'rental', 'amount_paid', 'amount_in_words',
        'payment_date', 'status', 'created_by', 'created_at'
    )
    list_filter = ('status', 'payment_date', 'created_at')
    search_fields = (
        'rental__code', 'rental__equipment__name',
        'rental__renter__email', 'amount_in_words'
    )
    readonly_fields = ('created_by', 'created_at', 'payment_date')
    date_hierarchy = 'payment_date'

    def save_model(self, request, obj, form, change):
        if not change:
            obj.created_by = request.user
        super().save_model(request, obj, form, change)


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ('user', 'type', 'severity', 'title', 'is_read', 'created_at')
    list_filter = ('type', 'severity', 'is_read', 'created_at')
    search_fields = ('title', 'message', 'user__email')
    readonly_fields = ('created_at',)
    date_hierarchy = 'created_at'


@admin.register(RentalReceipt)
class RentalReceiptAdmin(admin.ModelAdmin):
    list_display = ('rental', 'generated_at', 'generated_by')
    list_filter = ('generated_at',)
    search_fields = ('rental__code', 'rental__renter__email')
    readonly_fields = ('generated_at', 'generated_by')
    date_hierarchy = 'generated_at'

    def save_model(self, request, obj, form, change):
        if not change:
            obj.generated_by = request.user
        super().save_model(request, obj, form, change)