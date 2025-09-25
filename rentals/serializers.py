from rest_framework import serializers
from .models import Equipment, Rental, RentalPayment
from django.contrib.auth import get_user_model
import logging  # Add this import

logger = logging.getLogger(__name__)  # Define logger

User = get_user_model()

class EquipmentSerializer(serializers.ModelSerializer):
    created_by_name = serializers.CharField(source='created_by.full_name', read_only=True, default='N/A')

    class Meta:
        model = Equipment
        fields = ['id', 'name', 'category', 'condition', 'location', 'created_by', 'created_at', 'created_by_name']
        read_only_fields = ['created_by', 'created_at', 'created_by_name']

    def validate(self, data):
        if not data.get('name') or not data.get('category') or not data.get('condition') or not data.get('location'):
            raise serializers.ValidationError('All fields are required.')
        return data

class RentalSerializer(serializers.ModelSerializer):
    renter_name = serializers.CharField(source='renter.full_name', read_only=True, default='N/A')
    equipment_name = serializers.CharField(source='equipment.name', read_only=True)
    created_by_name = serializers.CharField(source='created_by.full_name', read_only=True, default='N/A')
    equipment = serializers.PrimaryKeyRelatedField(queryset=Equipment.objects.all())

    class Meta:
        model = Rental
        fields = ['id', 'code', 'renter', 'renter_name', 'equipment', 'equipment_name', 'start_date', 'due_date', 'status', 'created_by', 'created_at', 'created_by_name']
        read_only_fields = ['id', 'code', 'renter', 'created_by', 'created_at', 'created_by_name', 'renter_name', 'equipment_name']

    def validate(self, data):
        # Log incoming data for debugging
        logger.debug(f"Validating rental data: {data}")

        # Validate required fields
        required_fields = ['equipment', 'start_date', 'due_date', 'status']
        for field in required_fields:
            if not data.get(field):
                logger.error(f"Missing required field: {field}")
                raise serializers.ValidationError({field: f'{field.replace("_", " ").title()} is required.'})

        # Validate dates
        if data.get('start_date') > data.get('due_date'):
            logger.error(f"Invalid dates: start_date={data.get('start_date')} > due_date={data.get('due_date')}")
            raise serializers.ValidationError({'due_date': 'Due date must be after start date.'})

        # Validate equipment
        equipment = data.get('equipment')
        if not isinstance(equipment, Equipment):
            try:
                equipment = Equipment.objects.get(id=equipment)
            except Equipment.DoesNotExist:
                logger.error(f"Invalid equipment ID: {equipment}")
                raise serializers.ValidationError({'equipment': 'Equipment does not exist.'})
            except ValueError:
                logger.error(f"Invalid equipment value: {equipment}")
                raise serializers.ValidationError({'equipment': 'Equipment ID must be a number.'})

        # Ensure equipment is an instance for consistency
        data['equipment'] = equipment

        return data

    def create(self, validated_data):
        request = self.context.get('request')
        if not request or not hasattr(request, 'user') or not request.user.is_authenticated:
            logger.error("Unauthenticated user attempted to create rental")
            raise serializers.ValidationError({'renter': 'Authenticated user required.'})

        # Ensure user has full_name
        if not hasattr(request.user, 'full_name') or not request.user.full_name:
            logger.error(f"User {request.user.username} has no full_name")
            raise serializers.ValidationError({'renter': 'User must have a full name.'})

        validated_data['renter'] = request.user
        validated_data['created_by'] = request.user

        try:
            rental = Rental.objects.create(**validated_data)
            if not rental.code:
                rental.code = f"RENT-{rental.id:06d}"
                rental.save(update_fields=['code'])
            logger.debug(f"Created rental: {rental.code}")
            return rental
        except Exception as e:
            logger.error(f"Failed to create rental: {str(e)}")
            raise serializers.ValidationError(f"Failed to create rental: {str(e)}")

class RentalPaymentSerializer(serializers.ModelSerializer):
    renter_name = serializers.CharField(source='rental.renter.full_name', read_only=True, default='N/A')
    equipment_name = serializers.CharField(source='rental.equipment.name', read_only=True)
    created_by_name = serializers.CharField(source='created_by.full_name', read_only=True, default='N/A')

    class Meta:
        model = RentalPayment
        fields = ['id', 'rental', 'renter_name', 'equipment_name', 'amount_paid', 'payment_date', 'status', 'created_by', 'created_at', 'created_by_name']
        read_only_fields = ['payment_date', 'created_by', 'created_at', 'created_by_name']

    def validate(self, data):
        if data.get('amount_paid', 0) <= 0:
            raise serializers.ValidationError({'amount_paid': 'Amount paid must be positive.'})
        return data

    def create(self, validated_data):
        request = self.context.get('request')
        if request and hasattr(request, 'user'):
            validated_data['created_by'] = request.user
        return super().create(validated_data)