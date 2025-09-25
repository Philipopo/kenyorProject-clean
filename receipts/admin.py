from django.contrib import admin
from .models import Receipt, StockReceipt, SigningReceipt

admin.site.register(Receipt)
admin.site.register(StockReceipt)
admin.site.register(SigningReceipt)
