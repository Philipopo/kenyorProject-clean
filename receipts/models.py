# receipts/models.py
from django.db import models
from django.conf import settings
from inventory.models import Item, StorageBin
from procurement.models import PurchaseOrder

User = settings.AUTH_USER_MODEL

# === Keep your existing models, but enhance them ===

class Receipt(models.Model):
    reference = models.CharField(max_length=100, unique=True)
    issued_by = models.CharField(max_length=100)
    date = models.DateField()
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        related_name='created_receipts'  # Better naming
    )
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.reference


class StockReceipt(models.Model):
    # 🔗 Link to real inventory & procurement
    item = models.ForeignKey(
        Item,
        on_delete=models.PROTECT,
        null=True,  # Allow null temporarily if migrating
        blank=True,
        related_name='stock_receipts'
    )
    item_name_legacy = models.CharField(max_length=255, blank=True)  # Preserve old data

    storage_bin = models.ForeignKey(
        StorageBin,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name='stock_receipts'
    )
    location_legacy = models.CharField(max_length=100, blank=True)  # Preserve old

    purchase_order = models.ForeignKey(
        PurchaseOrder,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='stock_receipts'
    )

    quantity = models.PositiveIntegerField()
    notes = models.TextField(blank=True)
    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        related_name='created_stock_receipts'
    )
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        item_name = self.item.name if self.item else self.item_name_legacy
        return item_name or "Unnamed Item"


class SigningReceipt(models.Model):
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('signed', 'Signed'),
        ('rejected', 'Rejected'),
    ]

    recipient = models.CharField(max_length=100)
    signed_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='signed_signing_receipts'
    )
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    notes = models.TextField(blank=True)

    # 🔗 Optional: link to procurement
    purchase_order = models.ForeignKey(
        PurchaseOrder,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='signing_receipts'
    )

    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        related_name='created_signing_receipts'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    signed_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f'{self.recipient} - {self.get_status_display()}'

    def can_sign(self, user):
        """Check if user is authorized to sign receipts"""
        from .models import ReceiptApprovalBoard  # Avoid circular import
        try:
            permission = ReceiptApprovalBoard.objects.get(user=user, is_active=True)
            return permission.can_sign_receipts
        except ReceiptApprovalBoard.DoesNotExist:
            return False


# === NEW: Permission Table ===
class ReceiptApprovalBoard(models.Model):
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='receipt_signing_permissions'
    )
    can_sign_receipts = models.BooleanField(default=False)
    added_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        related_name='added_receipt_approvers'
    )
    added_at = models.DateTimeField(auto_now_add=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        unique_together = ['user']
        verbose_name = "Receipt Signer"
        verbose_name_plural = "Receipt Signers"

    def __str__(self):
        return f"{self.user.email} - Can Sign: {self.can_sign_receipts}"