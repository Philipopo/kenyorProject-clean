# receipts/models.py
from django.db import models
from django.conf import settings

class Receipt(models.Model):
    reference = models.CharField(max_length=100, unique=True)
    issued_by = models.CharField(max_length=100)
    date = models.DateField()
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name='receipts')
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.reference

class StockReceipt(models.Model):
    item = models.CharField(max_length=255)
    quantity = models.PositiveIntegerField()
    location = models.CharField(max_length=100)
    date = models.DateField()
    notes = models.TextField(blank=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name='stock_receipts')
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.item

class SigningReceipt(models.Model):
    recipient = models.CharField(max_length=100)
    signed_by = models.CharField(max_length=100)
    date = models.DateField()
    status = models.CharField(max_length=50, choices=[('Signed', 'Signed'), ('Pending', 'Pending')])
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name='signing_receipts')
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f'{self.recipient} - {self.status}'