from django.db import models
from django.conf import settings
import uuid

class Branch(models.Model):
    name = models.CharField(max_length=100, unique=True)
    code = models.CharField(max_length=20, unique=True)
    address = models.TextField()
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='created_branches'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.name} ({self.code})"

    class Meta:
        ordering = ['name']



class Equipment(models.Model):
    name = models.CharField(max_length=100)
    category = models.CharField(max_length=100)
    condition = models.CharField(max_length=50)
    location = models.CharField(max_length=100)
    branch = models.ForeignKey(Branch, on_delete=models.PROTECT, related_name='equipment', null=True)  # ✅ NEW
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name='equipment')
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name

class Rental(models.Model):
    code = models.CharField(max_length=20, unique=True, editable=False)
    renter = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='rentals')
    equipment = models.ForeignKey(Equipment, on_delete=models.CASCADE, related_name='rentals')
    branch = models.ForeignKey(Branch, on_delete=models.PROTECT, related_name='rentals')  # ✅ From equipment
    start_date = models.DateField()
    due_date = models.DateField()
    approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='approved_rentals'
    )
    returned = models.BooleanField(default=False)
    returned_at = models.DateTimeField(null=True, blank=True)
    status = models.CharField(max_length=20, choices=[('Active', 'Active'), ('Overdue', 'Overdue')])
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name='created_rentals')
    created_at = models.DateTimeField(auto_now_add=True)

    def save(self, *args, **kwargs):
        if not self.pk:
            super().save(*args, **kwargs)
            self.code = f"RENT-{self.id:06d}"
            self.branch = self.equipment.branch  # ✅ Auto-set from equipment
            super().save(update_fields=['code', 'branch'])
        else:
            super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.code} - {self.renter.email} - {self.equipment.name}"



class RentalPayment(models.Model):
    rental = models.ForeignKey(Rental, on_delete=models.CASCADE, related_name='payments')
    amount_paid = models.DecimalField(max_digits=10, decimal_places=2)
    payment_date = models.DateField(auto_now_add=True)
    status = models.CharField(max_length=20, choices=[('Paid', 'Paid'), ('Pending', 'Pending')])
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name='rental_payments')
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.rental.code} - ₦{self.amount_paid} ({self.status})"



