# rentals/models.py

from django.db import models
from django.conf import settings
from django.core.exceptions import ValidationError
from django.utils import timezone
import logging
from decimal import Decimal

logger = logging.getLogger(__name__)

CURRENCY_CHOICES = [
    ('NGN', 'Nigerian Naira'),
    ('USD', 'US Dollar'),
]

NOTIFICATION_TYPES = [
    ('OVERDUE', 'Overdue Rental'),
    ('ALMOST_OVERDUE', 'Almost Overdue Rental'),
]

SEVERITY_LEVELS = [
    ('INFO', 'Info'),
    ('WARNING', 'Warning'),
    ('CRITICAL', 'Critical'),
]

def rental_image_upload_path(instance, filename):
    return f'rentals/equipment_{instance.id}/{filename}'


class Notification(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='notifications')
    type = models.CharField(max_length=50, choices=NOTIFICATION_TYPES)
    severity = models.CharField(max_length=20, choices=SEVERITY_LEVELS, default='INFO')
    title = models.CharField(max_length=255)
    message = models.TextField()
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    related_rental = models.ForeignKey('Rental', on_delete=models.CASCADE, null=True, blank=True)
    related_equipment = models.ForeignKey('Equipment', on_delete=models.CASCADE, null=True, blank=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.user.email} - {self.title}"


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
    description = models.TextField(blank=True)
    image = models.ImageField(upload_to=rental_image_upload_path, blank=True, null=True)
    manufacture_date = models.DateField(null=True, blank=True)
    expiry_date = models.DateField(null=True, blank=True)
    category = models.CharField(max_length=100)
    condition = models.CharField(max_length=50)
    location = models.CharField(max_length=100)
    branch = models.ForeignKey(Branch, on_delete=models.PROTECT, related_name='equipment', null=True, blank=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name='equipment')
    created_at = models.DateTimeField(auto_now_add=True)
    total_quantity = models.PositiveIntegerField(default=1)
    available_quantity = models.PositiveIntegerField(default=1)

    def clean(self):
        if self.available_quantity > self.total_quantity:
            raise ValidationError("Available quantity cannot exceed total quantity.")
        if self.available_quantity < 0:
            raise ValidationError("Available quantity cannot be negative.")
        if self.branch is None:
            return
        required_fields = ['name', 'category', 'condition', 'location']
        for field in required_fields:
            if not getattr(self, field):
                raise ValidationError({field: "This field cannot be blank."})

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)

    def __str__(self):
        return self.name


class Reservation(models.Model):
    equipment = models.ForeignKey(Equipment, on_delete=models.CASCADE, related_name='reservations')
    reserved_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='reservations', null=True, blank=True)
    start_date = models.DateField()
    end_date = models.DateField(null=True, blank=True)  # null = open-ended
    quantity = models.PositiveIntegerField(default=1)
    created_at = models.DateTimeField(auto_now_add=True)
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return f"Reservation for {self.equipment.name} by {self.reserved_by.email}"

    def clean(self):
        if self.end_date and self.start_date > self.end_date:
            raise ValidationError("End date must be after start date.")
        if self.quantity <= 0:
            raise ValidationError("Reservation quantity must be positive.")
        if self.quantity > self.equipment.available_quantity:
            raise ValidationError(f"Only {self.equipment.available_quantity} units available for reservation.")

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)


class Rental(models.Model):
    code = models.CharField(max_length=20, unique=True, editable=False)
    renter = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='rentals')
    equipment = models.ForeignKey(Equipment, on_delete=models.CASCADE, related_name='rentals')
    branch = models.ForeignKey(Branch, on_delete=models.PROTECT, related_name='rentals', null=True, blank=True)
    start_date = models.DateField()
    due_date = models.DateField(null=True, blank=True)  # null = open-ended
    extended_to = models.DateField(null=True, blank=True)  # for extension
    rental_rate = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    currency = models.CharField(max_length=3, choices=CURRENCY_CHOICES, default='NGN')
    quantity = models.PositiveIntegerField(default=1)
    approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='approved_rentals'
    )
    returned = models.BooleanField(default=False)
    returned_at = models.DateTimeField(null=True, blank=True)
    notes = models.TextField(blank=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name='created_rentals')
    created_at = models.DateTimeField(auto_now_add=True)

    @property
    def effective_due_date(self):
        return self.extended_to or self.due_date

    @property
    def is_open_ended(self):
        return self.due_date is None and self.extended_to is None

    @property
    def is_overdue(self):
        if self.returned or self.is_open_ended:
            return False
        due = self.effective_due_date
        return due and due < timezone.now().date()

    @property
    def days_overdue(self):
        if self.is_overdue:
            return (timezone.now().date() - self.effective_due_date).days
        return 0

    @property
    def duration_days(self):
        if not self.start_date:
            return 0
        if self.returned and self.returned_at:
            end = self.returned_at.date()
        elif self.is_open_ended:
            end = timezone.now().date()
        else:
            end = self.effective_due_date or self.start_date
        return max(0, (end - self.start_date).days)

    @property
    def total_rental_cost(self):
        if not self.rental_rate or self.rental_rate <= 0:
            return Decimal('0.00')
        if self.is_open_ended:
            days = self.duration_days
        else:
            if self.effective_due_date:
                days = (self.effective_due_date - self.start_date).days
            else:
                days = 0
        return Decimal(str(self.rental_rate * days * self.quantity)).quantize(Decimal('0.01'))

    @property
    def total_paid(self):
        return self.payments.filter(status='Paid').aggregate(
            total=models.Sum('amount_paid')
        )['total'] or Decimal('0.00')

    @property
    def balance_due(self):
        return max(self.total_rental_cost - self.total_paid, Decimal('0.00'))

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

            # Reservation conflict check
            active_res = Reservation.objects.filter(
                equipment=self.equipment,
                is_active=True,
                start_date__lte=self.start_date,
            ).filter(
                models.Q(end_date__isnull=True) | models.Q(end_date__gte=self.start_date)
            ).exists()
            if active_res:
                raise ValidationError("This equipment is currently reserved and cannot be rented.")

            if self.quantity > self.equipment.available_quantity:
                raise ValidationError(f"Only {self.equipment.available_quantity} units available.")

            self.equipment.available_quantity -= self.quantity
            self.equipment.save(update_fields=['available_quantity'])
            self.check_notifications()  # ✅ Generate Notification (NO Alert)

        elif is_return_update:
            self.equipment.available_quantity = min(
                self.equipment.available_quantity + self.quantity,
                self.equipment.total_quantity
            )
            self.equipment.save(update_fields=['available_quantity'])
            if not self.returned_at:
                self.returned_at = timezone.now()
            super().save(*args, **kwargs)

        else:
            super().save(*args, **kwargs)
            self.check_notifications()  # ✅ Also on update (NO Alert)

    def check_notifications(self):
        """Generate Notification records for overdue or almost overdue rentals."""
        if self.returned:
            return

        today = timezone.now().date()
        due = self.effective_due_date

        if not due:
            return  # Open-ended rentals don’t trigger notifications

        days_until_due = (due - today).days

        # Overdue → CRITICAL
        if days_until_due < 0:
            Notification.objects.get_or_create(
                user=self.renter,
                type='OVERDUE',
                defaults={
                    'severity': 'CRITICAL',
                    'title': 'Rental Overdue',
                    'message': f"Rental {self.code} for {self.equipment.name} is overdue by {abs(days_until_due)} days.",
                    'related_rental': self
                }
            )

        # Due in 1–3 days → WARNING
        elif 0 <= days_until_due <= 3:
            Notification.objects.get_or_create(
                user=self.renter,
                type='ALMOST_OVERDUE',
                defaults={
                    'severity': 'WARNING',
                    'title': 'Rental Due Soon',
                    'message': f"Rental {self.code} for {self.equipment.name} is due in {days_until_due} days.",
                    'related_rental': self
                }
            )

    def __str__(self):
        return f"{self.code} - {self.renter.email} - {self.equipment.name} x{self.quantity}"


class RentalPayment(models.Model):
    rental = models.ForeignKey(Rental, on_delete=models.CASCADE, related_name='payments')
    amount_paid = models.DecimalField(max_digits=10, decimal_places=2)
    amount_in_words = models.CharField(max_length=255, blank=True)  # Manual input
    payment_date = models.DateField(auto_now_add=True)
    status = models.CharField(max_length=20, choices=[('Paid', 'Paid'), ('Pending', 'Pending')])
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name='rental_payments')
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.rental.code} - {self.amount_paid} ({self.status})"


class RentalReceipt(models.Model):
    rental = models.OneToOneField(Rental, on_delete=models.CASCADE, related_name='receipt')
    generated_at = models.DateTimeField(auto_now_add=True)
    generated_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True)

    def __str__(self):
        return f"Receipt for {self.rental.code}"