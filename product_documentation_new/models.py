from django.db import models
from django.conf import settings
from inventory.models import Item

class ProductInflow(models.Model):
    item = models.ForeignKey(
        Item,
        on_delete=models.CASCADE,
        related_name='new_inflows'
    )
    batch = models.CharField(max_length=255, db_index=True)
    vendor = models.CharField(max_length=255, db_index=True)
    date_of_delivery = models.DateField(db_index=True)
    quantity = models.PositiveIntegerField()
    cost = models.DecimalField(max_digits=10, decimal_places=2)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='new_product_inflows_created'
    )
    updated_at = models.DateTimeField(auto_now=True, db_index=True)

    def __str__(self):
        return f"{self.item.name} (Batch: {self.batch}) from {self.vendor}"

    class Meta:
        ordering = ['-created_at']  # ✅ Newest first
        indexes = [
            models.Index(fields=['-created_at']),
            models.Index(fields=['vendor', 'date_of_delivery']),
        ]


class ProductOutflow(models.Model):
    product = models.ForeignKey(ProductInflow, on_delete=models.CASCADE, related_name='new_outflows')
    customer_name = models.CharField(max_length=255)
    sales_order = models.CharField(max_length=100, blank=True, null=True)
    dispatch_date = models.DateField()
    quantity = models.PositiveIntegerField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    # ✅ ADD THIS FIELD:
    responsible_staff = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='new_product_outflows_created'
    )


    def __str__(self):
        return f"{self.product.item.name} to {self.customer_name} - {self.quantity} units"

    class Meta:
        ordering = ['-created_at']


class SerialNumber(models.Model):
    STATUS_CHOICES = [
        ('in_stock', 'In Stock'),
        ('shipped', 'Shipped'),
    ]
    
    product_inflow = models.ForeignKey(ProductInflow, on_delete=models.CASCADE, related_name='serial_numbers')
    product_outflow = models.ForeignKey(
        ProductOutflow, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True, 
        related_name='new_serial_numbers'
    )
    serial_number = models.CharField(max_length=100, unique=True, db_index=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='in_stock')
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True, db_index=True)

    def __str__(self):
        return self.serial_number

    class Meta:
        indexes = [
            models.Index(fields=['status']),
            models.Index(fields=['product_inflow', 'status']),
        ]