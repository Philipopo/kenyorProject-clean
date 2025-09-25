# procurement/models.py
from django.db import models
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from inventory.models import Item, StorageBin
import uuid

User = get_user_model()

class Vendor(models.Model):
    STAR_CHOICES = [(i, f"{i} Star{'s' if i > 1 else ''}") for i in range(1, 6)]
    STATUS_CHOICES = [
        ('active', 'Active'),
        ('inactive', 'Inactive'),
        ('suspended', 'Suspended'),
        ('blacklisted', 'Blacklisted'),
    ]
    
    name = models.CharField(max_length=255, unique=True)
    contact_person = models.CharField(max_length=255, blank=True)
    email = models.EmailField(blank=True)
    phone = models.CharField(max_length=20, blank=True)
    address = models.TextField(blank=True)
    tax_id = models.CharField(max_length=50, blank=True, help_text="Tax/VAT registration number")
    details = models.TextField(blank=True, null=True)
    lead_time = models.PositiveIntegerField(help_text="Average lead time in days")
    ratings = models.IntegerField(choices=STAR_CHOICES, default=3)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='active')
    document = models.FileField(upload_to='vendor_documents/', blank=True, null=True)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='vendors')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['name']

    def __str__(self):
        return self.name

    def clean(self):
        if self.lead_time <= 0:
            raise ValidationError("Lead time must be positive.")

class Requisition(models.Model):
    STATUS_CHOICES = [
        ('draft', 'Draft'),
        ('submitted', 'Submitted'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
        ('cancelled', 'Cancelled'),
        ('completed', 'Completed'),
    ]
    
    code = models.CharField(max_length=100, unique=True, blank=True)
    department = models.CharField(max_length=100)
    purpose = models.TextField()
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='draft')
    priority = models.CharField(max_length=20, choices=[
        ('low', 'Low'),
        ('medium', 'Medium'),
        ('high', 'High'),
        ('urgent', 'Urgent'),
    ], default='medium')
    requested_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name='requisitions')
    approved_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='approved_requisitions')
    created_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name='created_requisitions')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    approved_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-created_at']

    def save(self, *args, **kwargs):
        if not self.code:
            self.code = f"REQ-{uuid.uuid4().hex[:8].upper()}"
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.code}: {self.department} ({self.status})"

    def can_approve(self, user):
        """Check if user can approve this requisition"""
        return user.role in ['finance_manager', 'operations_manager', 'md', 'admin']

class RequisitionItem(models.Model):
    requisition = models.ForeignKey(Requisition, on_delete=models.CASCADE, related_name='items')
    item = models.ForeignKey(Item, on_delete=models.CASCADE, related_name='requisition_items')
    quantity = models.PositiveIntegerField()
    unit_cost = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    total_cost = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['id']

    def __str__(self):
        return f"{self.item.name} x {self.quantity}"

    def save(self, *args, **kwargs):
        if self.unit_cost and self.quantity:
            self.total_cost = self.unit_cost * self.quantity
        super().save(*args, **kwargs)

class PurchaseOrder(models.Model):
    STATUS_CHOICES = [
        ('draft', 'Draft'),
        ('submitted', 'Submitted'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
        ('partially_received', 'Partially Received'),
        ('received', 'Received'),
        ('cancelled', 'Cancelled'),
    ]
    
    code = models.CharField(max_length=100, unique=True, blank=True)
    requisition = models.ForeignKey(Requisition, on_delete=models.SET_NULL, null=True, blank=True, related_name='purchase_orders')
    vendor = models.ForeignKey(Vendor, on_delete=models.CASCADE, related_name='purchase_orders')
    department = models.CharField(max_length=100)
    delivery_address = models.TextField()
    expected_delivery_date = models.DateField()
    payment_terms = models.TextField(blank=True)
    notes = models.TextField(blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='draft')
    total_amount = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    tax_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    discount_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    created_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name='purchase_orders')
    approved_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='approved_pos')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    approved_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-created_at']

    def save(self, *args, **kwargs):
        if not self.code:
            self.code = f"PO-{uuid.uuid4().hex[:8].upper()}"
        # Calculate total amount from PO items
        if self.pk:
            self.total_amount = self.items.aggregate(
                total=models.Sum(models.F('unit_price') * models.F('quantity'))
            )['total'] or 0
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.code} - {self.vendor.name} ({self.status})"

    def can_approve(self, user):
        return user.role in ['finance_manager', 'operations_manager', 'md', 'admin']

    def is_fully_received(self):
        """Check if all PO items have been received"""
        if not self.items.exists():
            return False
        return all(item.received_quantity >= item.quantity for item in self.items.all())

class POItem(models.Model):
    po = models.ForeignKey(PurchaseOrder, on_delete=models.CASCADE, related_name='items')
    item = models.ForeignKey(Item, on_delete=models.CASCADE, related_name='po_items')
    quantity = models.PositiveIntegerField()
    received_quantity = models.PositiveIntegerField(default=0)
    unit_price = models.DecimalField(max_digits=12, decimal_places=2)
    total_price = models.DecimalField(max_digits=15, decimal_places=2, null=True, blank=True)
    notes = models.TextField(blank=True)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='po_items')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['id']

    def __str__(self):
        return f"{self.item.name} x {self.quantity} @ {self.unit_price}"

    def save(self, *args, **kwargs):
        self.total_price = self.unit_price * self.quantity
        super().save(*args, **kwargs)

    def clean(self):
        if self.quantity <= 0:
            raise ValidationError("Quantity must be positive.")
        if self.unit_price <= 0:
            raise ValidationError("Unit price must be positive.")
        if self.received_quantity > self.quantity:
            raise ValidationError("Received quantity cannot exceed ordered quantity.")

class Receiving(models.Model):
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('partial', 'Partial'),
        ('complete', 'Complete'),
        ('rejected', 'Rejected'),
    ]
    
    po = models.ForeignKey(PurchaseOrder, on_delete=models.CASCADE, related_name='receivings')
    grn = models.CharField(max_length=100, unique=True, blank=True)
    invoice_number = models.CharField(max_length=100)
    invoice_date = models.DateField()
    received_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name='receivings')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    notes = models.TextField(blank=True)
    document = models.FileField(upload_to='receipts/', blank=True, null=True)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='created_receivings')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def save(self, *args, **kwargs):
        if not self.grn:
            self.grn = f"GRN-{uuid.uuid4().hex[:8].upper()}"
        super().save(*args, **kwargs)

    def __str__(self):
        return f"Receiving {self.grn} for {self.po.code}"

    def update_po_status(self):
        """Update PO status based on receiving status"""
        po = self.po
        if po.is_fully_received():
            po.status = 'received'
        elif any(r.status == 'complete' for r in po.receivings.all()):
            po.status = 'partially_received'
        po.save()

class ReceivingItem(models.Model):
    receiving = models.ForeignKey(Receiving, on_delete=models.CASCADE, related_name='items')
    po_item = models.ForeignKey(POItem, on_delete=models.CASCADE, related_name='receiving_items')
    received_quantity = models.PositiveIntegerField()
    accepted_quantity = models.PositiveIntegerField()
    rejected_quantity = models.PositiveIntegerField(default=0)
    rejection_reason = models.TextField(blank=True)
    storage_bin = models.ForeignKey(StorageBin, on_delete=models.SET_NULL, null=True, blank=True, related_name='received_items')
    batch_number = models.CharField(max_length=100, blank=True)
    expiry_date = models.DateField(null=True, blank=True)
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['id']

    def __str__(self):
        return f"{self.po_item.item.name} x {self.received_quantity}"

    def clean(self):
        if self.received_quantity <= 0:
            raise ValidationError("Received quantity must be positive.")
        if self.accepted_quantity + self.rejected_quantity != self.received_quantity:
            raise ValidationError("Accepted + Rejected must equal Received quantity.")
        if self.rejected_quantity > 0 and not self.rejection_reason:
            raise ValidationError("Rejection reason is required when rejecting items.")

    def save(self, *args, **kwargs):
        self.rejected_quantity = self.received_quantity - self.accepted_quantity
        super().save(*args, **kwargs)
        
        # Update PO item received quantity
        self.po_item.received_quantity += self.accepted_quantity
        self.po_item.save()
        
        # Update inventory stock if accepted
        if self.accepted_quantity > 0 and self.storage_bin:
            from inventory.models import StockRecord
            stock_record, created = StockRecord.objects.get_or_create(
                item=self.po_item.item,
                storage_bin=self.storage_bin,
                defaults={'quantity': 0, 'user': self.created_by or self.receiving.created_by}
            )
            stock_record.quantity += self.accepted_quantity
            stock_record.save()

class GoodsReceipt(models.Model):
    """Legacy model - consider deprecating in favor of Receiving model"""
    po_code = models.CharField(max_length=100)
    grn_code = models.CharField(max_length=100)
    invoice_code = models.CharField(max_length=100)
    match_success = models.BooleanField(default=False)
    attachment = models.FileField(upload_to='grn_docs/', blank=True, null=True)
    timestamp = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='goods_receipts')

    def __str__(self):
        return f"GRN {self.grn_code} for PO {self.po_code}"

# Audit trail for procurement activities
class ProcurementAuditLog(models.Model):
    ACTION_CHOICES = [
        ('create', 'Create'),
        ('update', 'Update'),
        ('delete', 'Delete'),
        ('approve', 'Approve'),
        ('reject', 'Reject'),
        ('receive', 'Receive'),
    ]
    
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    action = models.CharField(max_length=20, choices=ACTION_CHOICES)
    model_name = models.CharField(max_length=50)
    object_id = models.PositiveIntegerField()
    details = models.JSONField(default=dict)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.user.email} {self.action} {self.model_name} {self.object_id}"