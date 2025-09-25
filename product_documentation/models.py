# product_documentation/models.py
from django.db import models
from django.conf import settings
from inventory.models import Item  # Import Item from inventory app

class ProductInflow(models.Model):
    item = models.ForeignKey(Item, on_delete=models.CASCADE, related_name='inflows')  # Link to Item
    batch = models.CharField(max_length=255)  # Batch number
    vendor = models.CharField(max_length=255)  # Vendor name
    date_of_delivery = models.DateField()  # Date of delivery
    quantity = models.PositiveIntegerField()
    cost = models.DecimalField(max_digits=10, decimal_places=2)
    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name='inflows')

    class Meta:
        ordering = ['-date_of_delivery']
        indexes = [
            models.Index(fields=['batch']),
        ]

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
    responsible_staff = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name='outflows')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-dispatch_date']

    def __str__(self):
        return f"{self.product.item.name} to {self.customer_name}"