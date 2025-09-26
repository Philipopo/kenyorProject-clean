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
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "EOQ Report V2"
        verbose_name_plural = "EOQ Reports V2"

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

    def save(self, *args, **kwargs):
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
