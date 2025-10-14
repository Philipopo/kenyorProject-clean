# rentals/models.py
from django.db import models
from django.conf import settings
from django.core.exceptions import ValidationError
from django.utils import timezone
from alerts.models import Alert
import logging

logger = logging.getLogger(__name__)

CURRENCY_CHOICES = [
    ('NGN', 'Nigerian Naira'),
    ('USD', 'US Dollar'),
]

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

    def delete(self, *args, **kwargs):
        if self.equipment.exists():
            raise ValidationError("Cannot delete branch with assigned equipment.")
        super().delete(*args, **kwargs)

    class Meta:
        ordering = ['name']

class Equipment(models.Model):
    name = models.CharField(max_length=100)
    category = models.CharField(max_length=100)
    condition = models.CharField(max_length=50)
    location = models.CharField(max_length=100)
    branch = models.ForeignKey(Branch, on_delete=models.PROTECT, related_name='equipment', null=True, blank=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name='equipment')
    created_at = models.DateTimeField(auto_now_add=True)
    total_quantity = models.PositiveIntegerField(default=1)
    available_quantity = models.PositiveIntegerField(default=1)

    def clean(self):
        # Validate quantities
        if self.available_quantity > self.total_quantity:
            raise ValidationError("Available quantity cannot exceed total quantity.")
        if self.available_quantity < 0:
            raise ValidationError("Available quantity cannot be negative.")
        # Skip branch validation if None, as it's allowed to be null
        if self.branch is None:
            return
        # Validate other required fields
        required_fields = ['name', 'category', 'condition', 'location']
        for field in required_fields:
            if not getattr(self, field):
                raise ValidationError({field: "This field cannot be blank."})

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)

    def __str__(self):
        return self.name

class Rental(models.Model):
    code = models.CharField(max_length=20, unique=True, editable=False)
    renter = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='rentals')
    equipment = models.ForeignKey(Equipment, on_delete=models.CASCADE, related_name='rentals')
    branch = models.ForeignKey(Branch, on_delete=models.PROTECT, related_name='rentals', null=True, blank=True)
    start_date = models.DateField(null=True, blank=True)
    due_date = models.DateField(null=True, blank=True)
    approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='approved_rentals'
    )
    returned = models.BooleanField(default=False)
    returned_at = models.DateTimeField(null=True, blank=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name='created_rentals')
    created_at = models.DateTimeField(auto_now_add=True)
    
    # New fields
    currency = models.CharField(max_length=3, choices=CURRENCY_CHOICES, default='NGN')
    rental_rate = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    notes = models.TextField(blank=True)

    @property
    def is_overdue(self):
        # Return False if due_date is None (open-ended rentals can't be overdue)
        if not self.due_date or self.returned:
            return False
        return self.due_date < timezone.now().date()

    @property
    def days_overdue(self):
        if self.is_overdue:
            return (timezone.now().date() - self.due_date).days
        return 0

    @property
    def duration_days(self):
        if not self.start_date:
            return 0
        if self.returned and self.returned_at:
            return (self.returned_at.date() - self.start_date).days
        if not self.due_date:
            return (timezone.now().date() - self.start_date).days
        return (self.due_date - self.start_date).days

    def save(self, *args, **kwargs):
        is_new = not self.pk
        is_return_update = False

        if not is_new:
            old = Rental.objects.get(pk=self.pk)
            is_return_update = (not old.returned) and self.returned

        if is_new:
            super().save(*args, **kwargs)
            self.code = f"RENT-{self.id:06d}"
            self.branch = self.equipment.branch
            super().save(update_fields=['code', 'branch'])

            equipment = self.equipment
            if equipment.available_quantity <= 0:
                raise ValidationError("Equipment is not available for rental.")
            equipment.available_quantity -= 1
            equipment.save(update_fields=['available_quantity'])

            self._check_overdue_alert()

        elif is_return_update:
            equipment = self.equipment
            equipment.available_quantity = min(
                equipment.available_quantity + 1,
                equipment.total_quantity
            )
            equipment.save(update_fields=['available_quantity'])
            if not self.returned_at:
                self.returned_at = timezone.now()
            super().save(*args, **kwargs)

        else:
            super().save(*args, **kwargs)
            self._check_overdue_alert()

    def _check_overdue_alert(self):
        if self.is_overdue and not self.returned:
            existing = Alert.objects.filter(
                user=self.renter,
                message__contains=self.code,
                type='Tracker Issue',
            ).exists()

            if not existing:
                try:
                    Alert.objects.create(
                        user=self.renter,
                        type='Tracker Issue',
                        message=f"Rental {self.code} for {self.equipment.name} is overdue by {self.days_overdue} days.",
                    )
                    logger.warning(f"Overdue rental alert created for {self.code}")
                except Exception as e:
                    logger.error(f"Failed to create overdue alert for rental {self.code}: {e}")

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
        return f"{self.rental.code} - {self.amount_paid} ({self.status})"