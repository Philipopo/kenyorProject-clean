from rest_framework import serializers
from .models import Equipment, Rental, RentalPayment, Branch
from django.contrib.auth import get_user_model
import logging

logger = logging.getLogger(__name__)

User = get_user_model()

class BranchSerializer(serializers.ModelSerializer):
    created_by_name = serializers.SerializerMethodField()

    class Meta:
        model = Branch
        fields = ['id', 'name', 'code', 'address', 'created_by', 'created_by_name', 'created_at']
        read_only_fields = ['created_by', 'created_by_name', 'created_at']

    def get_created_by_name(self, obj):
        if obj.created_by:
            return obj.created_by.full_name or obj.created_by.name or obj.created_by.email
        return "N/A"

class EquipmentSerializer(serializers.ModelSerializer):
    created_by_name = serializers.SerializerMethodField()
    branch_name = serializers.CharField(source='branch.name', read_only=True)

    class Meta:
        model = Equipment
        fields = [
            'id', 'name', 'category', 'condition', 'location', 'branch', 'branch_name',
            'created_by', 'created_by_name', 'created_at',
            'total_quantity', 'available_quantity'
        ]
        read_only_fields = ['created_by', 'created_by_name', 'created_at']

    def get_created_by_name(self, obj):
        if obj.created_by:
            return obj.created_by.full_name or obj.created_by.name or obj.created_by.email
        return "N/A"

    def validate(self, data):
        required = ['name', 'category', 'condition', 'location', 'branch']
        for field in required:
            if not data.get(field):
                raise serializers.ValidationError(f"{field.replace('_', ' ').title()} is required.")
        return data

    def create(self, validated_data):
        validated_data['created_by'] = self.context['request'].user
        return super().create(validated_data)

class RentalSerializer(serializers.ModelSerializer):
    renter_name = serializers.SerializerMethodField()
    equipment_name = serializers.CharField(source='equipment.name', read_only=True)
    branch_name = serializers.CharField(source='branch.name', read_only=True)
    approved_by_name = serializers.SerializerMethodField()
    created_by_name = serializers.SerializerMethodField()
    computed_status = serializers.CharField(read_only=True)
    duration_days = serializers.IntegerField(read_only=True)
    days_overdue = serializers.IntegerField(read_only=True)
    is_overdue = serializers.BooleanField(read_only=True)

    class Meta:
        model = Rental
        fields = [
            'id', 'code', 'renter', 'renter_name', 'equipment', 'equipment_name',
            'branch', 'branch_name', 'start_date', 'due_date',
            'approved_by', 'approved_by_name', 'returned', 'returned_at',
            'created_by', 'created_by_name', 'created_at',
            'computed_status', 'duration_days', 'days_overdue', 'is_overdue',
            'currency', 'rental_rate', 'notes'
        ]
        read_only_fields = [
            'id', 'code', 'branch', 'created_by', 'created_by_name',
            'renter_name', 'equipment_name', 'branch_name', 'approved_by_name',
            'computed_status', 'duration_days', 'days_overdue', 'is_overdue'
        ]

    def get_renter_name(self, obj):
        if obj.renter:
            return obj.renter.full_name or obj.renter.name or obj.renter.email
        return "N/A"

    def get_approved_by_name(self, obj):
        if obj.approved_by:
            return obj.approved_by.full_name or obj.approved_by.name or obj.approved_by.email
        return "N/A"

    def get_created_by_name(self, obj):
        if obj.created_by:
            return obj.created_by.full_name or obj.created_by.name or obj.created_by.email
        return "N/A"

    def validate(self, data):
        logger.debug(f"Validating rental data for {self.context['request'].method}: {data}")
        # Only require equipment, renter, and start_date for POST (creation)
        if self.context['request'].method == 'POST':
            required = ['equipment', 'renter', 'start_date']
            for field in required:
                if not data.get(field):
                    raise serializers.ValidationError(f"{field.replace('_', ' ').title()} is required.")
        # Validate due_date only if provided
        if data.get('due_date') and data.get('start_date') and data['start_date'] > data['due_date']:
            raise serializers.ValidationError("Due date must be after start date.")
        # For PATCH, check if rental is already returned
        if self.context['request'].method == 'PATCH' and 'returned' in data and data['returned']:
            if self.instance and self.instance.returned:
                raise serializers.ValidationError("Rental is already returned.")
        return data

    def create(self, validated_data):
        request = self.context['request']
        validated_data['created_by'] = request.user
        return super().create(validated_data)

class RentalPaymentSerializer(serializers.ModelSerializer):
    renter_name = serializers.SerializerMethodField()
    equipment_name = serializers.CharField(source='rental.equipment.name', read_only=True)
    created_by_name = serializers.SerializerMethodField()
    currency = serializers.CharField(source='rental.currency', read_only=True)

    class Meta:
        model = RentalPayment
        fields = ['id', 'rental', 'renter_name', 'equipment_name', 'amount_paid', 'payment_date', 'status', 'created_by', 'created_at', 'created_by_name', 'currency']
        read_only_fields = ['payment_date', 'created_by', 'created_at', 'created_by_name', 'currency']

    def get_renter_name(self, obj):
        if obj.rental and obj.rental.renter:
            return obj.rental.renter.full_name or obj.rental.renter.name or obj.rental.renter.email
        return "N/A"

    def get_created_by_name(self, obj):
        if obj.created_by:
            return obj.created_by.full_name or obj.created_by.name or obj.created_by.email
        return "N/A"

    def validate(self, data):
        if data.get('amount_paid', 0) <= 0:
            raise serializers.ValidationError({'amount_paid': 'Amount paid must be positive.'})
        return data

    def create(self, validated_data):
        request = self.context.get('request')
        if request and hasattr(request, 'user'):
            validated_data['created_by'] = request.user
        return super().create(validated_data)