from rest_framework import serializers
from .models import Equipment, Rental, RentalPayment, Branch, Reservation, Notification
from django.contrib.auth import get_user_model
from decimal import Decimal
import logging
from django.db import models
from django.conf import settings

logger = logging.getLogger(__name__)
User = get_user_model()

class BranchSerializer(serializers.ModelSerializer):
    created_by_name = serializers.SerializerMethodField()

    class Meta:
        model = Branch
        fields = ['id', 'name', 'code', 'address', 'created_by', 'created_by_name', 'created_at']
        read_only_fields = ['created_by', 'created_by_name', 'created_at']

    def get_created_by_name(self, obj):
        user = getattr(obj, 'created_by', None)
        if user:
            return getattr(user, 'full_name', None) or (user.get_full_name() if hasattr(user, 'get_full_name') else None) or user.email
        return "N/A"

class EquipmentSerializer(serializers.ModelSerializer):
    created_by_name = serializers.SerializerMethodField()
    branch_name = serializers.CharField(source='branch.name', read_only=True)
    image = serializers.SerializerMethodField()

    class Meta:
        model = Equipment
        fields = [
            'id', 'name', 'description', 'image', 'manufacture_date', 'expiry_date',
            'category', 'condition', 'location', 'branch', 'branch_name',
            'created_by', 'created_by_name', 'created_at',
            'total_quantity', 'available_quantity'
        ]
        read_only_fields = ['created_by', 'created_by_name', 'created_at']

    def get_image(self, obj):
        if getattr(obj, 'image', None):
            request = self.context.get('request')
            if request:
                return request.build_absolute_uri(obj.image.url)
            site = getattr(settings, 'SITE_URL', '')
            return f"{site}{obj.image.url}"
        return None

    def get_created_by_name(self, obj):
        user = getattr(obj, "created_by", None)
        if user:
            return getattr(user, 'full_name', None) or (user.get_full_name() if hasattr(user, 'get_full_name') else None) or user.email
        return ""

    def validate(self, data):
        required = ['name', 'category', 'condition', 'location', 'branch']
        for field in required:
            if not data.get(field):
                raise serializers.ValidationError(f"{field.replace('_', ' ').title()} is required.")
        return data

    def create(self, validated_data):
        validated_data['created_by'] = self.context['request'].user
        return super().create(validated_data)

class ReservationSerializer(serializers.ModelSerializer):
    equipment_name = serializers.CharField(source='equipment.name', read_only=True)
    reserved_for_name = serializers.SerializerMethodField()
    created_by_name = serializers.SerializerMethodField()

    class Meta:
        model = Reservation
        fields = [
            'id', 'equipment', 'equipment_name', 'reserved_for', 'reserved_for_name',
            'start_date', 'end_date', 'quantity', 'is_active', 'created_by', 'created_by_name', 'created_at'
        ]
        read_only_fields = ['created_by', 'created_by_name', 'created_at', 'reserved_for_name', 'equipment_name']

    def get_reserved_for_name(self, obj):
        user = getattr(obj, 'reserved_for', None)
        if user:
            return getattr(user, 'full_name', None) or (user.get_full_name() if hasattr(user, 'get_full_name') else None) or user.email
        return "N/A"

    def get_created_by_name(self, obj):
        user = getattr(obj, 'created_by', None)
        if user:
            return getattr(user, 'full_name', None) or (user.get_full_name() if hasattr(user, 'get_full_name') else None) or user.email
        return "N/A"

    def validate(self, data):
        if data.get('end_date') and data['start_date'] > data['end_date']:
            raise serializers.ValidationError("End date must be after start date.")
        equipment = data.get('equipment', self.instance.equipment if self.instance else None)
        quantity = data.get('quantity', self.instance.quantity if self.instance else 1)
        reserved_sum = equipment.reservations.filter(is_active=True).aggregate(models.Sum('quantity'))['quantity__sum'] or 0 if equipment else 0
        rented_sum = equipment.rentals.filter(returned=False).aggregate(models.Sum('quantity'))['quantity__sum'] or 0 if equipment else 0
        available = (equipment.total_quantity if equipment else 0) - reserved_sum - rented_sum
        if quantity > available:
            raise serializers.ValidationError(f"Only {available} units available for reservation.")
        return data

    def create(self, validated_data):
        validated_data['created_by'] = self.context['request'].user
        return super().create(validated_data)

class RentalPaymentSerializer(serializers.ModelSerializer):
    renter_name = serializers.SerializerMethodField()
    equipment_name = serializers.CharField(source='rental.equipment.name', read_only=True)
    currency = serializers.CharField(source='rental.currency', read_only=True)
    total_rental_cost = serializers.DecimalField(source='rental.total_rental_cost', max_digits=12, decimal_places=2, read_only=True)
    balance_due = serializers.DecimalField(source='rental.balance_due', max_digits=12, decimal_places=2, read_only=True)
    created_by_name = serializers.SerializerMethodField()

    class Meta:
        model = RentalPayment
        fields = [
            'id', 'rental', 'renter_name', 'equipment_name', 'amount_paid', 'amount_in_words',
            'payment_date', 'status', 'created_by', 'created_by_name', 'currency',
            'total_rental_cost', 'balance_due'
        ]
        read_only_fields = ['payment_date', 'created_by', 'created_at', 'created_by_name', 'currency', 'total_rental_cost', 'balance_due']

    def get_renter_name(self, obj):
        rental = getattr(obj, 'rental', None)
        renter = getattr(rental, 'renter', None) if rental else None
        if renter:
            return getattr(renter, 'full_name', None) or (renter.get_full_name() if hasattr(renter, 'get_full_name') else None) or renter.email
        logger.warning(f"Invalid renter for rental payment {obj.id}: {rental.renter if rental else None} (type: {type(rental.renter) if rental else None})")
        return ""

    def get_created_by_name(self, obj):
        user = getattr(obj, 'created_by', None)
        if user:
            return getattr(user, 'full_name', None) or (user.get_full_name() if hasattr(user, 'get_full_name') else None) or user.email
        return ""

    def validate(self, data):
        if data.get('amount_paid', 0) <= 0:
            raise serializers.ValidationError({'amount_paid': 'Amount paid must be positive.'})
        rental = data.get('rental', self.instance.rental if self.instance else None)
        if rental and data.get('amount_paid') > getattr(rental, 'balance_due', 0):
            raise serializers.ValidationError({
                'amount_paid': f"Amount paid ({data['amount_paid']}) exceeds balance due ({rental.balance_due})."
            })
        if not data.get('amount_in_words'):
            raise serializers.ValidationError({'amount_in_words': 'Amount in words is required.'})
        return data

    def create(self, validated_data):
        validated_data['created_by'] = self.context['request'].user
        return super().create(validated_data)

class RentalSerializer(serializers.ModelSerializer):
    renter_name = serializers.SerializerMethodField()
    equipment_name = serializers.CharField(source='equipment.name', read_only=True)
    branch_name = serializers.CharField(source='branch.name', read_only=True)
    created_by_name = serializers.SerializerMethodField()
    total_rental_cost = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True)
    total_paid = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True)
    balance_due = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True)
    is_overdue = serializers.BooleanField(read_only=True)
    days_overdue = serializers.IntegerField(read_only=True)
    duration_days = serializers.IntegerField(read_only=True)
    is_open_ended = serializers.BooleanField(read_only=True)
    payments = RentalPaymentSerializer(many=True, read_only=True)

    class Meta:
        model = Rental
        fields = [
            'id', 'code', 'renter', 'renter_name', 'equipment', 'equipment_name',
            'branch', 'branch_name', 'start_date', 'due_date', 'extended_to',
            'rental_rate', 'currency', 'quantity',
            'returned', 'returned_at', 'notes', 'created_by', 'created_by_name', 'created_at',
            'total_rental_cost', 'total_paid', 'balance_due',
            'is_overdue', 'days_overdue', 'duration_days', 'is_open_ended', 'payments'
        ]
        read_only_fields = [
            'id', 'code', 'branch', 'created_by', 'created_by_name',
            'renter_name', 'equipment_name', 'branch_name',
            'total_rental_cost', 'total_paid', 'balance_due',
            'is_overdue', 'days_overdue', 'duration_days', 'is_open_ended'
        ]

    def get_renter_name(self, obj):
        renter = getattr(obj, "renter", None)
        if renter:
            return getattr(renter, 'full_name', None) or (renter.get_full_name() if hasattr(renter, 'get_full_name') else None) or renter.email
        return ""

    def get_created_by_name(self, obj):
        user = getattr(obj, 'created_by', None)
        if user:
            return getattr(user, 'full_name', None) or (user.get_full_name() if hasattr(user, 'get_full_name') else None) or user.email
        return "N/A"

    def validate(self, data):
        method = self.context['request'].method
        if method == 'POST':
            required = ['equipment', 'renter', 'start_date', 'quantity']
            for field in required:
                if not data.get(field):
                    raise serializers.ValidationError(f"{field.replace('_', ' ').title()} is required.")
            if data['quantity'] <= 0:
                raise serializers.ValidationError("Quantity must be at least 1.")
            if data.get('due_date') and data.get('start_date') and data['start_date'] > data['due_date']:
                raise serializers.ValidationError("Due date must be after start date.")
            
            # Validate equipment availability
            equipment = data['equipment']
            reserved_quantity = equipment.reservations.filter(
                is_active=True,
                start_date__lte=data['start_date'],
                end_date__gte=data['start_date']
            ).aggregate(models.Sum('quantity'))['quantity__sum'] or 0
            rented_quantity = equipment.rentals.filter(returned=False).aggregate(
                models.Sum('quantity'))['quantity__sum'] or 0
            available = equipment.total_quantity - reserved_quantity - rented_quantity
            if data['quantity'] > available:
                raise serializers.ValidationError(f"Only {available} units available for rental.")
        
        elif method == 'PATCH' and 'returned' in data and data['returned']:
            if self.instance and self.instance.returned:
                raise serializers.ValidationError("Rental is already returned.")
        
        return data

    def create(self, validated_data):
        validated_data['created_by'] = self.context['request'].user
        return super().create(validated_data)



        

class NotificationSerializer(serializers.ModelSerializer):
    rental_code = serializers.CharField(source='related_rental.code', read_only=True)
    equipment_name = serializers.CharField(source='related_equipment.name', read_only=True)

    class Meta:
        model = Notification
        fields = ['id', 'type', 'severity', 'title', 'message', 'is_read', 'created_at', 'rental_code', 'equipment_name']