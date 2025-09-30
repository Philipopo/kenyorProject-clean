# product_documentation/models.py

from django.db import models
from django.conf import settings
from inventory.models import Item

# --- KEEP EXISTING MODELS AS-IS ---

class ProductInflow(models.Model):
    item = models.ForeignKey(Item, on_delete=models.CASCADE, related_name='inflows')
    batch = models.CharField(max_length=255)
    vendor = models.CharField(max_length=255)
    date_of_delivery = models.DateField()
    quantity = models.PositiveIntegerField()
    cost = models.DecimalField(max_digits=10, decimal_places=2)
    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='product_inflows_created'
    )
    user = models.ForeignKey('accounts.User', on_delete=models.CASCADE)

    class Meta:
        ordering = ['-date_of_delivery']
        indexes = [models.Index(fields=['batch'])]

    def __str__(self):
        return f"{self.item.name} (Batch: {self.batch}) from {self.vendor}"


class ProductSerialNumber(models.Model):
    inflow = models.ForeignKey(ProductInflow, on_delete=models.CASCADE, related_name='serial_numbers')
    serial_number = models.CharField(max_length=100, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)
    status = models.CharField(
        max_length=20,
        choices=(('in_stock', 'In Stock'), ('dispatched', 'Dispatched'), ('returned', 'Returned')),
        default='in_stock'
    )

    class Meta:
        ordering = ['serial_number']

    def __str__(self):
        return self.serial_number


class ProductOutflow(models.Model):
    product = models.ForeignKey(ProductInflow, on_delete=models.CASCADE, related_name='outflows')
    serial_numbers = models.ManyToManyField(ProductSerialNumber, related_name='outflows')
    customer_name = models.CharField(max_length=255)
    sales_order = models.CharField(max_length=50, blank=True)
    dispatch_date = models.DateField()
    quantity = models.PositiveIntegerField()
    responsible_staff = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='product_outflows_created'
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-dispatch_date']

    def __str__(self):
        return f"{self.product.item.name} to {self.customer_name}"


# ✅ NEW: Activity Log Model (Non-destructive)
class ProductDocumentationLog(models.Model):
    ACTION_CHOICES = [
        ('create', 'Create'),
        ('update', 'Update'),
        ('delete', 'Delete'),
    ]
    
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True)
    action = models.CharField(max_length=10, choices=ACTION_CHOICES)
    model_name = models.CharField(max_length=50)  # 'ProductInflow', 'ProductOutflow'
    object_id = models.PositiveIntegerField()
    object_repr = models.CharField(max_length=255)  # e.g., "Item X (Batch Y)"
    timestamp = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-timestamp']
        verbose_name = 'Product Documentation Log'
        verbose_name_plural = 'Product Documentation Logs'

    def __str__(self):
        user_name = self.user.name if self.user and self.user.name else (self.user.email if self.user else 'Unknown')
        return f"{user_name} {self.action} {self.model_name} '{self.object_repr}' on {self.timestamp.strftime('%b %d, %Y %I:%M%p')}"