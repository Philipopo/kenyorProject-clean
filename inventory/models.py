from django.db import models
from django.conf import settings
from django.core.exceptions import ValidationError
import logging
from django.utils import timezone

logger = logging.getLogger(__name__)

class Item(models.Model):
    name = models.CharField(max_length=255)
    part_number = models.CharField(max_length=100, unique=True)
    manufacturer = models.CharField(max_length=255)
    contact = models.CharField(max_length=255)
    batch = models.CharField(max_length=100, blank=True)
    expiry_date = models.DateField(null=True, blank=True)
    min_stock_level = models.PositiveIntegerField(default=0)
    reserved_quantity = models.PositiveIntegerField(default=0)
    custom_fields = models.JSONField(default=dict, blank=True)
    user = models.ForeignKey('accounts.User', on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)

    def total_quantity(self):
        if self.pk:  # Only query stock_records if the item has been saved
            return self.stock_records.aggregate(total=models.Sum('quantity'))['total'] or 0
        return 0

    def available_quantity(self):
        if self.pk:
            return self.total_quantity() - self.reserved_quantity
        return 0

    def clean(self):
        if self.pk and self.reserved_quantity > self.total_quantity():
            raise ValidationError("Reserved quantity cannot exceed total quantity.")

    def save(self, *args, **kwargs):
        self.full_clean()  # Run validation before saving
        super().save(*args, **kwargs)

    def __str__(self):
        return self.name

    def check_alerts(self):
        """Generate alerts based on item stock levels."""
        total_qty = self.total_quantity()
        available_qty = self.available_quantity()
        
        # Low stock alert
        if total_qty <= self.min_stock_level:
            InventoryAlert.objects.create(
                user=self.user,
                alert_type='WARNING',
                message=f"Item {self.name} is below minimum stock level ({total_qty}/{self.min_stock_level}).",
                related_item=self
            )
            logger.warning(f"Item {self.name} low stock alert triggered.")
        
        # Critical low stock alert (below 10% of min level)
        if total_qty > 0 and total_qty <= (self.min_stock_level * 0.1):
            InventoryAlert.objects.create(
                user=self.user,
                alert_type='CRITICAL',
                message=f"Item {self.name} is critically low ({total_qty}/{self.min_stock_level}).",
                related_item=self
            )
            logger.warning(f"Item {self.name} critical low stock alert triggered.")
        
        # Expiry alert (if item has expiry date)
        if self.expiry_date:
            days_until_expiry = (self.expiry_date - timezone.now().date()).days
            if 0 <= days_until_expiry <= 7:  # Expiring within 7 days
                InventoryAlert.objects.create(
                    user=self.user,
                    alert_type='WARNING',
                    message=f"Item {self.name} expires in {days_until_expiry} days ({self.expiry_date}).",
                    related_item=self
                )
                logger.warning(f"Item {self.name} expiry alert triggered.")
            elif days_until_expiry < 0:  # Already expired
                InventoryAlert.objects.create(
                    user=self.user,
                    alert_type='CRITICAL',
                    message=f"Item {self.name} has expired on {self.expiry_date}.",
                    related_item=self
                )
                logger.warning(f"Item {self.name} expired alert triggered.")





class Warehouse(models.Model):
    name = models.CharField(max_length=255, unique=True)
    code = models.CharField(max_length=50, unique=True)
    description = models.TextField(blank=True)
    address = models.TextField(blank=True)
    capacity = models.PositiveIntegerField(help_text="Total capacity in units")
    is_active = models.BooleanField(default=True)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.name} ({self.code})"

    @property
    def total_bins(self):
        return self.bins.count()

    @property
    def used_capacity(self):
        return self.bins.aggregate(total_used=models.Sum('current_load'))['total_used'] or 0

    @property
    def available_capacity(self):
        return self.capacity - self.used_capacity

    @property
    def usage_percentage(self):
        if self.capacity == 0:
            return 0
        return round((self.used_capacity / self.capacity) * 100, 2)

    def clean(self):
        """Validate that capacity is positive"""
        if self.capacity <= 0:
            raise ValidationError("Capacity must be a positive number.")

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)

# Update the StorageBin model to include warehouse relationship
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
        # Check for alerts after saving
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
        return f"{self.item.name} in {self.storage_bin.bin_id} ({self.quantity})"

    def clean(self):
        """Validate quantity constraints."""
        if self.quantity < 0:
            raise ValidationError("Quantity cannot be negative.")
        # Ensure bin capacity isn't violated
        if self.storage_bin:
            new_load = self.storage_bin.current_load - (self.quantity or 0) + self.quantity
            if new_load > self.storage_bin.capacity:
                raise ValidationError(
                    f"Adding {self.quantity} to bin {self.storage_bin.bin_id} exceeds capacity "
                    f"({self.storage_bin.current_load}/{self.storage_bin.capacity})."
                )

    def save(self, *args, **kwargs):
        self.full_clean()
        # Update bin's current_load
        old_quantity = self.quantity if self.pk else 0
        super().save(*args, **kwargs)
        if self.storage_bin:
            self.storage_bin.current_load = self.storage_bin.stock_records.aggregate(
                total=models.Sum('quantity')
            )['total'] or 0
            self.storage_bin.save()
        # Check item-level alerts
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

    def __str__(self):
        return f"{self.movement_type} {self.quantity} of {self.item.name} in {self.storage_bin.bin_id}"

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
        return f"{self.item.name} ({self.batch})"

    def clean(self):
        if self.quantity < 0:
            raise ValidationError("Quantity cannot be negative.")

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)