from django.db import models
from inventory.models import Item

class ProductInflow(models.Model):
    item = models.ForeignKey(Item, on_delete=models.CASCADE, related_name='new_inflows')
    batch = models.CharField(max_length=100)
    vendor = models.CharField(max_length=255)
    date_of_delivery = models.DateField()
    quantity = models.PositiveIntegerField()
    cost = models.DecimalField(max_digits=10, decimal_places=2)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.item.name} (Batch: {self.batch}) - {self.quantity} units"

class ProductOutflow(models.Model):
    product = models.ForeignKey(ProductInflow, on_delete=models.CASCADE, related_name='new_outflows')
    customer_name = models.CharField(max_length=255)
    sales_order = models.CharField(max_length=100, blank=True, null=True)
    dispatch_date = models.DateField()
    quantity = models.PositiveIntegerField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.product.item.name} to {self.customer_name} - {self.quantity} units"

class SerialNumber(models.Model):
    product_inflow = models.ForeignKey(ProductInflow, on_delete=models.CASCADE, related_name='new_serial_numbers')
    product_outflow = models.ForeignKey(ProductOutflow, on_delete=models.SET_NULL, null=True, blank=True, related_name='new_serial_numbers')
    serial_number = models.CharField(max_length=100, unique=True)
    status = models.CharField(max_length=20, choices=[('in_stock', 'In Stock'), ('shipped', 'Shipped')])
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.serial_number