from django.db import models
from django.core.exceptions import ValidationError
from inventory.models import Item, StorageBin

def validate_quantity(value):
    if value <= 0:
        raise ValidationError('Quantity must be greater than zero.')

class WarehouseItem(models.Model):
    item = models.ForeignKey(
        Item, 
        on_delete=models.CASCADE, 
        related_name='warehouse_new_items'  # Changed to avoid conflict with old app
    )
    storage_bin = models.ForeignKey(
        StorageBin, 
        on_delete=models.SET_NULL, 
        null=True, 
        related_name='warehouse_new_items'  # Changed to avoid conflict
    )
    quantity = models.PositiveIntegerField(validators=[validate_quantity])
    status = models.CharField(
        max_length=20,
        choices=(('in_stock', 'In Stock'), ('reserved', 'Reserved'), ('dispatched', 'Dispatched')),
        default='in_stock'
    )
    last_updated = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-last_updated']
        constraints = [
            models.UniqueConstraint(fields=['item', 'storage_bin'], name='unique_warehouse_new_item_bin')
        ]

    def __str__(self):
        return f"{self.item.name} at {self.storage_bin.bin_id if self.storage_bin else 'No Bin'} ({self.quantity})"

    def clean(self):
        if self.storage_bin:
            total_used = self.storage_bin.warehouse_new_items.exclude(id=self.id).aggregate(
                total=models.Sum('quantity')
            )['total'] or 0
            if total_used + self.quantity > self.storage_bin.capacity:
                raise ValidationError(
                    f"Storage bin {self.storage_bin.bin_id} capacity exceeded: "
                    f"{total_used + self.quantity} > {self.storage_bin.capacity}"
                )

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)
        if self.storage_bin:
            self.storage_bin.update_used()