from django.contrib import admin


from .models import FinanceCategory, FinanceTransaction

@admin.register(FinanceCategory)
class FinanceCategoryAdmin(admin.ModelAdmin):
    list_display = ('name', 'description', 'created_at')
    search_fields = ('name', 'description')

@admin.register(FinanceTransaction)
class FinanceTransactionAdmin(admin.ModelAdmin):
    list_display = ('ref', 'type', 'amount', 'date')
    search_fields = ('ref',)
    list_filter = ('type', 'date')
