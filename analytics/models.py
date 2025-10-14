from django.db import models
from django.conf import settings
from django.core.exceptions import ValidationError
import math

class DwellTime(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    item = models.CharField(max_length=100)
    duration_days = models.PositiveIntegerField()
    is_aging = models.BooleanField(default=False)
    storage_cost = models.DecimalField(max_digits=10, decimal_places=2)
    created_at = models.DateTimeField(auto_now_add=True)

class EOQReport(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    item = models.CharField(max_length=100)
    part_number = models.CharField(max_length=50)
    demand_rate = models.PositiveIntegerField(help_text="Units/year")
    order_cost = models.DecimalField(max_digits=10, decimal_places=2)
    holding_cost = models.DecimalField(max_digits=10, decimal_places=2)
    eoq = models.PositiveIntegerField()
    created_at = models.DateTimeField(auto_now_add=True)

class EOQReportV2(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='eoq_reports_v2')
    item = models.ForeignKey('inventory.Item', on_delete=models.CASCADE, related_name='eoq_reports_v2', help_text="Inventory item")
    demand_rate = models.PositiveIntegerField(help_text="Annual demand in units")
    order_cost = models.DecimalField(max_digits=10, decimal_places=2, help_text="Cost per order")
    holding_cost = models.DecimalField(max_digits=10, decimal_places=2, help_text="Holding cost per unit per year")
    lead_time_days = models.PositiveIntegerField(help_text="Lead time in days")
    safety_stock = models.PositiveIntegerField(default=0, help_text="Safety stock in units")
    eoq = models.PositiveIntegerField(blank=True, help_text="Calculated Economic Order Quantity")
    reorder_point = models.PositiveIntegerField(blank=True, help_text="Inventory level to trigger reorder")
    total_cost = models.DecimalField(max_digits=12, decimal_places=2, blank=True, help_text="Total inventory cost at EOQ")
    holding_cost_breakdown = models.DecimalField(max_digits=12, decimal_places=2, blank=True, null=True, help_text="Holding cost component")
    ordering_cost_breakdown = models.DecimalField(max_digits=12, decimal_places=2, blank=True, null=True, help_text="Ordering cost component")
    inventory_turnover = models.DecimalField(max_digits=10, decimal_places=2, blank=True, null=True, help_text="Inventory turnover ratio")
    supplier = models.ForeignKey('Supplier', on_delete=models.SET_NULL, null=True, blank=True, help_text="Supplier for this item")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "EOQ Report V2"
        verbose_name_plural = "EOQ Reports V2"

    def calculate_safety_stock(self):
        from inventory.models import StockMovement
        try:
            # Get last 6 months of stock movements for the item
            movements = StockMovement.objects.filter(
                item=self.item,
                timestamp__gte=self.created_at - timezone.timedelta(days=180)
            ).values('quantity')
            quantities = [m['quantity'] for m in movements]
            if not quantities:
                return 0
            max_daily_demand = max(quantities) / 30  # Assume monthly avg
            avg_daily_demand = sum(quantities) / len(quantities) / 30
            max_lead_time = self.lead_time_days * 1.2  # 20% buffer
            return round((max_daily_demand * max_lead_time) - (avg_daily_demand * self.lead_time_days))
        except:
            return 0

    def clean(self):
        if self.demand_rate <= 0:
            raise ValidationError("Demand rate must be positive.")
        if self.order_cost <= 0:
            raise ValidationError("Order cost must be positive.")
        if self.holding_cost <= 0:
            raise ValidationError("Holding cost must be positive.")
        if self.lead_time_days < 0:
            raise ValidationError("Lead time cannot be negative.")

        # Calculate EOQ: sqrt(2 * D * S / H)
        try:
            eoq = math.sqrt((2 * self.demand_rate * float(self.order_cost)) / float(self.holding_cost))
            self.eoq = round(eoq)
        except (ValueError, ZeroDivisionError):
            raise ValidationError("Invalid values for EOQ calculation.")

        # Calculate Reorder Point: (Demand Rate per day * Lead Time) + Safety Stock
        demand_per_day = self.demand_rate / 365
        self.reorder_point = round(demand_per_day * self.lead_time_days) + self.safety_stock

        # Calculate Total Cost: sqrt(2 * D * S * H)
        self.total_cost = round(math.sqrt(2 * self.demand_rate * float(self.order_cost) * float(self.holding_cost)), 2)

        # Calculate Cost Breakdowns
        orders_per_year = self.demand_rate / self.eoq if self.eoq else 0
        self.holding_cost_breakdown = round((self.eoq / 2) * float(self.holding_cost), 2)
        self.ordering_cost_breakdown = round(orders_per_year * float(self.order_cost), 2)

        # Calculate Inventory Turnover
        self.inventory_turnover = round(self.demand_rate / (self.eoq / 2), 2) if self.eoq else 0

    def save(self, *args, **kwargs):
        self.safety_stock = self.calculate_safety_stock()
        self.clean()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"EOQ Report for {self.item.name} ({self.created_at})"

class StockAnalytics(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='stock_analytics')
    item = models.CharField(max_length=255)
    category = models.CharField(max_length=20, choices=[('A', 'A'), ('B', 'B'), ('C', 'C')])
    turnover_rate = models.DecimalField(max_digits=10, decimal_places=2)
    obsolescence_risk = models.CharField(max_length=20)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.item} - {self.category}"

class ReorderQueue(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='reorder_queues')
    item = models.ForeignKey('inventory.Item', on_delete=models.CASCADE, related_name='reorder_queues')
    recommended_quantity = models.PositiveIntegerField(help_text="Quantity to reorder based on EOQ")
    status = models.CharField(max_length=20, choices=[
        ('Pending', 'Pending'),
        ('Ordered', 'Ordered'),
        ('Completed', 'Completed')
    ], default='Pending')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Reorder Queue"
        verbose_name_plural = "Reorder Queues"

    def __str__(self):
        return f"Reorder {self.recommended_quantity} of {self.item.name}"

class Supplier(models.Model):
    name = models.CharField(max_length=100, unique=True)
    lead_time_days = models.PositiveIntegerField(default=7, help_text="Default lead time in days")
    min_order_quantity = models.PositiveIntegerField(blank=True, null=True, help_text="Minimum order quantity")
    discount_threshold = models.PositiveIntegerField(blank=True, null=True, help_text="Quantity for discount")
    discount_percentage = models.DecimalField(max_digits=5, decimal_places=2, blank=True, null=True, help_text="Discount percentage")
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name
