from django.db import models
from django.conf import settings
from django.core.exceptions import ValidationError
import logging
from django.utils import timezone
from django.contrib.auth import get_user_model
from django.db.models import Sum
import random
import uuid

User = get_user_model()
logger = logging.getLogger(__name__)

def generate_material_id():
    # Generate a random 6-digit number (100000 to 999999)
    return str(random.randint(100000, 999999))

def generate_warehouse_uid():
    # Generate a random 6-digit number (100000 to 999999)
    return str(random.randint(100000, 999999))

class Item(models.Model):
    material_id = models.CharField(max_length=6, unique=True, editable=False, null=True)
    name = models.CharField(max_length=255)
    description = models.CharField(max_length=500, null=True, blank=True)
    part_number = models.CharField(max_length=100, unique=True)
    material_class = models.CharField(max_length=100, unique=True, null=True, blank=True)
    manufacturer = models.CharField(max_length=255)
    contact = models.CharField(max_length=255)
    batch = models.CharField(max_length=100, blank=True)
    expiry_date = models.DateField(null=True, blank=True)
    min_stock_level = models.PositiveIntegerField(default=0)
    reserved_quantity = models.PositiveIntegerField(default=0)
    custom_fields = models.JSONField(default=dict, blank=True)
    user = models.ForeignKey('accounts.User', on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)
    po_number = models.CharField(max_length=100, blank=True, null=True, help_text="Purchase Order number")

    def total_quantity(self):
        if self.pk:  # Only query stock_records if the item has been saved
            return self.stock_records.aggregate(total=Sum('quantity'))['total'] or 0
        return 0

    def available_quantity(self):
        if self.pk:
            return self.total_quantity() - self.reserved_quantity
        return 0

    def clean(self):
        if self.pk and self.reserved_quantity > self.total_quantity():
            raise ValidationError("Reserved quantity cannot exceed total quantity.")

    def save(self, *args, **kwargs):
        if not self.material_id:
            # Keep trying until we get a unique ID (unlikely to collide)
            for _ in range(10):
                candidate = generate_material_id()
                if not Item.objects.filter(material_id=candidate).exists():
                    self.material_id = candidate
                    break
            else:
                raise RuntimeError("Failed to generate a unique Material ID after 10 attempts")
        self.full_clean()  # Run validation before saving
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.name} ({self.material_id})"

    def check_alerts(self):
        """Generate alerts based on item stock levels."""
        total_qty = self.total_quantity()
        available_qty = self.available_quantity()
        
        # Low stock alert
        if total_qty <= self.min_stock_level:
            InventoryAlert.objects.create(
                user=self.user,
                alert_type='WARNING',
                message=f"Item {self.name} ({self.material_id}) is below minimum stock level ({total_qty}/{self.min_stock_level}).",
                related_item=self
            )
            logger.warning(f"Item {self.name} ({self.material_id}) low stock alert triggered.")
        
        # Critical low stock alert (below 10% of min level)
        if total_qty > 0 and total_qty <= (self.min_stock_level * 0.1):
            InventoryAlert.objects.create(
                user=self.user,
                alert_type='CRITICAL',
                message=f"Item {self.name} ({self.material_id}) is critically low ({total_qty}/{self.min_stock_level}).",
                related_item=self
            )
            logger.warning(f"Item {self.name} ({self.material_id}) critical low stock alert triggered.")
        
        # Expiry alert (if item has expiry date)
        if self.expiry_date:
            days_until_expiry = (self.expiry_date - timezone.now().date()).days
            if 0 <= days_until_expiry <= 7:  # Expiring within 7 days
                InventoryAlert.objects.create(
                    user=self.user,
                    alert_type='WARNING',
                    message=f"Item {self.name} ({self.material_id}) expires in {days_until_expiry} days ({self.expiry_date}).",
                    related_item=self
                )
                logger.warning(f"Item {self.name} ({self.material_id}) expiry alert triggered.")
            elif days_until_expiry < 0:  # Already expired
                InventoryAlert.objects.create(
                    user=self.user,
                    alert_type='CRITICAL',
                    message=f"Item {self.name} ({self.material_id}) has expired on {self.expiry_date}.",
                    related_item=self
                )
                logger.warning(f"Item {self.name} ({self.material_id}) expired alert triggered.")

class Warehouse(models.Model):
    name = models.CharField(max_length=255, unique=True)
    code = models.CharField(max_length=50, unique=True)
    description = models.TextField(blank=True)
    address = models.TextField(blank=True)
    city = models.CharField(max_length=100, blank=True)
    state = models.CharField(max_length=100, blank=True)
    country = models.CharField(max_length=100, blank=True, default="Nigeria")
    capacity = models.PositiveIntegerField(help_text="Total capacity in units")
    is_active = models.BooleanField(default=True)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    warehouse_uid = models.CharField(max_length=6, unique=True, editable=False, blank=True, null=True)

    def clean(self):
        if self.capacity <= 0:
            raise ValidationError("Capacity must be a positive number.")

    def save(self, *args, **kwargs):
        if not self.warehouse_uid:
            for _ in range(10):
                uid = generate_warehouse_uid()
                if not Warehouse.objects.filter(warehouse_uid=uid).exists():
                    self.warehouse_uid = uid
                    break
            else:
                raise RuntimeError("Failed to generate unique warehouse UID")
        self.full_clean()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.name} ({self.code})"

    @property
    def total_bins(self):
        return self.bins.count()

    @property
    def used_capacity(self):
        return self.bins.aggregate(total_used=Sum('current_load'))['total_used'] or 0

    @property
    def available_capacity(self):
        return self.capacity - self.used_capacity

    @property
    def usage_percentage(self):
        if self.capacity == 0:
            return 0
        return round((self.used_capacity / self.capacity) * 100, 2)

class StorageBin(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='bins')
    warehouse = models.ForeignKey(Warehouse, on_delete=models.CASCADE, related_name='bins', null=True, blank=True)
    bin_id = models.CharField(max_length=50, unique=True)
    row = models.CharField(max_length=50, db_index=True)
    rack = models.CharField(max_length=50, db_index=True)
    shelf = models.CharField(max_length=50, blank=True)
    type = models.CharField(max_length=100, blank=True)
    capacity = models.PositiveIntegerField()
    current_load = models.PositiveIntegerField(default=0)
    description = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ('warehouse', 'row', 'rack', 'shelf')
        indexes = [models.Index(fields=['row', 'rack'])]

    def __str__(self):
        return f"{self.bin_id} ({self.row}-{self.rack})"

    def free_space(self):
        """Calculate available space in the bin."""
        return max(0, self.capacity - self.current_load)

    @property
    def usage_percentage(self):
        if self.capacity == 0:
            return 0
        return round((self.current_load / self.capacity) * 100, 2)

    def clean(self):
        """Validate current_load doesn't exceed capacity."""
        if self.current_load > self.capacity:
            raise ValidationError(f"Current load ({self.current_load}) exceeds capacity ({self.capacity}).")
        if self.capacity < 0:
            raise ValidationError("Capacity cannot be negative.")

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)
        self.check_alerts()

    def check_alerts(self):
        """Generate alerts based on bin status."""
        free_space = self.free_space()
        threshold_full = self.capacity * 0.9  # 90% full
        threshold_empty = self.capacity * 0.1  # 10% full

        if self.current_load >= self.capacity:
            InventoryAlert.objects.create(
                user=self.user,
                alert_type='CRITICAL',
                message=f"Bin {self.bin_id} is at full capacity ({self.current_load}/{self.capacity}).",
                related_bin=self
            )
            logger.warning(f"Bin {self.bin_id} full capacity alert triggered.")
        elif self.current_load >= threshold_full:
            InventoryAlert.objects.create(
                user=self.user,
                alert_type='WARNING',
                message=f"Bin {self.bin_id} is nearly full ({self.current_load}/{self.capacity}).",
                related_bin=self
            )
            logger.warning(f"Bin {self.bin_id} nearly full alert triggered.")
        if self.current_load == 0:
            InventoryAlert.objects.create(
                user=self.user,
                alert_type='WARNING',
                message=f"Bin {self.bin_id} is empty.",
                related_bin=self
            )
            logger.warning(f"Bin {self.bin_id} empty alert triggered.")
        elif self.current_load <= threshold_empty:
            InventoryAlert.objects.create(
                user=self.user,
                alert_type='WARNING',
                message=f"Bin {self.bin_id} is nearly empty ({self.current_load}/{self.capacity}).",
                related_bin=self
            )
            logger.warning(f"Bin {self.bin_id} nearly empty alert triggered.")

class StockRecord(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='stock_records')
    item = models.ForeignKey(Item, on_delete=models.CASCADE, related_name='stock_records')
    storage_bin = models.ForeignKey(StorageBin, on_delete=models.CASCADE, related_name='stock_records')
    quantity = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('item', 'storage_bin')

    def __str__(self):
        return f"{self.item.name} ({self.item.material_id}) in {self.storage_bin.bin_id} ({self.quantity})"

    def clean(self):
        """Validate quantity constraints."""
        if self.quantity < 0:
            raise ValidationError("Quantity cannot be negative.")
        if self.storage_bin:
            new_load = self.storage_bin.current_load - (self.quantity or 0) + self.quantity
            if new_load > self.storage_bin.capacity:
                raise ValidationError(
                    f"Adding {self.quantity} to bin {self.storage_bin.bin_id} exceeds capacity "
                    f"({self.storage_bin.current_load}/{self.storage_bin.capacity})."
                )

    def save(self, *args, **kwargs):
        self.full_clean()
        old_quantity = self.quantity if self.pk else 0
        super().save(*args, **kwargs)
        if self.storage_bin:
            self.storage_bin.current_load = self.storage_bin.stock_records.aggregate(
                total=Sum('quantity')
            )['total'] or 0
            self.storage_bin.save()
        self.item.check_alerts()

class StockMovement(models.Model):
    MOVEMENT_TYPES = (
        ('IN', 'Stock In'),
        ('OUT', 'Stock Out'),
    )
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True)
    item = models.ForeignKey(Item, on_delete=models.CASCADE, related_name='movements')
    storage_bin = models.ForeignKey(StorageBin, on_delete=models.CASCADE, related_name='movements')
    movement_type = models.CharField(max_length=50, choices=MOVEMENT_TYPES)
    quantity = models.PositiveIntegerField()
    timestamp = models.DateTimeField(auto_now_add=True)
    notes = models.TextField(blank=True)
    warehouse_receipt = models.ForeignKey(
        'WarehouseReceipt',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='movements'
    )

    def __str__(self):
        return f"{self.movement_type} {self.quantity} of {self.item.name} ({self.item.material_id}) in {self.storage_bin.bin_id}"

    def clean(self):
        if self.quantity <= 0:
            raise ValidationError("Movement quantity must be positive.")

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)

class InventoryAlert(models.Model):
    ALERT_TYPES = (
        ('WARNING', 'Warning'),
        ('CRITICAL', 'Critical'),
    )
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='alerts')
    alert_type = models.CharField(max_length=50, choices=ALERT_TYPES)
    message = models.TextField()
    related_item = models.ForeignKey(Item, on_delete=models.CASCADE, null=True, blank=True, related_name='alerts')
    related_bin = models.ForeignKey(StorageBin, on_delete=models.CASCADE, null=True, blank=True, related_name='alerts')
    created_at = models.DateTimeField(auto_now_add=True)
    is_resolved = models.BooleanField(default=False)

    def __str__(self):
        return f"{self.alert_type}: {self.message}"

class ExpiryTrackedItem(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='expiry_items')
    item = models.ForeignKey(Item, on_delete=models.CASCADE, related_name='expiry_records')
    batch = models.CharField(max_length=50)
    quantity = models.PositiveIntegerField()
    expiry_date = models.DateField()
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.item.name} ({self.item.material_id}) - {self.batch}"

    def clean(self):
        if self.quantity < 0:
            raise ValidationError("Quantity cannot be negative.")

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)

class InventoryActivityLog(models.Model):
    ACTION_CHOICES = [
        ('create', 'Create'),
        ('update', 'Update'),
        ('delete', 'Delete'),
        ('stock_in', 'Stock In'),
        ('stock_out', 'Stock Out'),
    ]
    

    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='inventory_activities')
    action = models.CharField(max_length=20, choices=ACTION_CHOICES)
    model_name = models.CharField(max_length=50)
    object_id = models.PositiveIntegerField(null=True, blank=True)
    object_name = models.CharField(max_length=255, blank=True)
    details = models.JSONField(default=dict, blank=True)
    timestamp = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-timestamp']
        verbose_name = 'Inventory Activity Log'
        verbose_name_plural = 'Inventory Activity Logs'
    
    def __str__(self):
        user_name = self.user.name if self.user and self.user.name else (self.user.email if self.user else 'Unknown')
        return f"{user_name} {self.action} {self.model_name} {self.object_name} at {self.timestamp}"

def generate_receipt_number():
    date_str = timezone.now().strftime("%Y%m%d")
    return f"WR-{date_str}-{uuid.uuid4().hex[:6].upper()}"

class WarehouseReceipt(models.Model):
    receipt_number = models.CharField(max_length=50, unique=True)
    issued_from_warehouse = models.ForeignKey(Warehouse, on_delete=models.CASCADE)
    issued_from_bin = models.ForeignKey(StorageBin, on_delete=models.CASCADE)
    item = models.ForeignKey(Item, on_delete=models.CASCADE)
    quantity = models.PositiveIntegerField()
    recipient = models.CharField(max_length=255)  # "Delivery To"
    purpose = models.TextField(blank=True)
    created_by = models.ForeignKey('accounts.User', on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)
    stock_movement = models.ForeignKey(StockMovement, on_delete=models.CASCADE, null=True, blank=True)
    old_material_no = models.CharField(max_length=100, null=True, blank=True)
    delivery_to = models.CharField(max_length=255, blank=True)
    transfer_order_no = models.CharField(max_length=100, blank=True)
    plant_site = models.CharField(max_length=100, blank=True)
    bin_location = models.CharField(max_length=100, blank=True)
    qty_picked = models.PositiveIntegerField(default=0)
    qty_remaining = models.PositiveIntegerField(default=0)
    unloading_point = models.CharField(max_length=255, blank=True)
    original_document = models.CharField(max_length=100, blank=True)
    picker = models.CharField(max_length=255, blank=True)
    controller = models.CharField(max_length=255, blank=True)

    def save(self, *args, **kwargs):
        if not self.receipt_number:
            self.receipt_number = f"WR-{timezone.now().strftime('%Y%m%d')}-{uuid.uuid4().hex[:6].upper()}"
        if self.item:
            self.bin_location = self.issued_from_bin.bin_id
            self.plant_site = self.issued_from_warehouse.code
            self.qty_remaining = self.item.available_quantity()
        super().save(*args, **kwargs)