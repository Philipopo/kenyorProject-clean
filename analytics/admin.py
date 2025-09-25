# analytics/admin.py

from django.contrib import admin
from .models import DwellTime, EOQReport, StockAnalytics

@admin.register(DwellTime)
class DwellTimeAdmin(admin.ModelAdmin):
    list_display = ('item', 'duration_days', 'is_aging', 'storage_cost', 'user', 'created_at')
    list_filter = ('is_aging', 'created_at')
    search_fields = ('item', 'user__email')

@admin.register(EOQReport)
class EOQReportAdmin(admin.ModelAdmin):
    list_display = ('item', 'part_number', 'demand_rate', 'order_cost', 'holding_cost', 'eoq', 'user', 'created_at')
    list_filter = ('created_at',)
    search_fields = ('item', 'part_number', 'user__email')

@admin.register(StockAnalytics)
class StockAnalyticsAdmin(admin.ModelAdmin):
    list_display = ('item', 'category', 'turnover_rate', 'obsolescence_risk', 'user', 'created_at')
    list_filter = ('category', 'created_at')
    search_fields = ('item', 'user__email')
