from rest_framework import serializers
from .models import ProductInflow, ProductOutflow, SerialNumber
from inventory.models import Item
from accounts.models import UserProfile

class SerialNumberSerializer(serializers.ModelSerializer):
    class Meta:
        model = SerialNumber
        fields = ['id', 'serial_number', 'status']

class ProductInflowSerializer(serializers.ModelSerializer):
    item_name = serializers.CharField(source='item.name', read_only=True)
    created_by_name = serializers.SerializerMethodField()
    serial_numbers = SerialNumberSerializer(many=True, read_only=True)
    input_serial_numbers = serializers.CharField(write_only=True, required=False, allow_blank=True)

    class Meta:
        model = ProductInflow
        fields = [
            'id', 'item', 'item_name', 'batch', 'vendor',
            'date_of_delivery', 'quantity', 'cost',
            'created_by', 'created_by_name', 'serial_numbers',
            'created_at', 'updated_at', 'input_serial_numbers'
        ]
        read_only_fields = ['id', 'item_name', 'created_by_name', 'serial_numbers', 'created_at', 'updated_at']

    def get_created_by_name(self, obj):
        if obj.created_by:
            try:
                profile = obj.created_by.profile
                if profile.full_name:
                    return profile.full_name
            except UserProfile.DoesNotExist:
                pass
            return obj.created_by.name or obj.created_by.email
        return '—'

    def validate_input_serial_numbers(self, value):
        quantity = self.initial_data.get('quantity')
        if value and quantity:
            serials = [s.strip() for s in value.split(',') if s.strip()]
            if len(serials) != int(quantity):
                raise serializers.ValidationError("Number of serial numbers must match quantity.")
        return value

    def create(self, validated_data):
        serial_numbers = validated_data.pop('input_serial_numbers', '')
        validated_data['created_by'] = self.context['request'].user
        inflow = ProductInflow.objects.create(**validated_data)
        if serial_numbers:
            serials = [s.strip() for s in serial_numbers.split(',') if s.strip()]
            for serial in serials:
                SerialNumber.objects.create(
                    product_inflow=inflow,
                    serial_number=serial,
                    status='in_stock'
                )
        return inflow

    def update(self, instance, validated_data):
        serial_numbers = validated_data.pop('input_serial_numbers', None)
        validated_data['created_by'] = self.context['request'].user
        instance = super().update(instance, validated_data)
        if serial_numbers is not None:
            instance.serial_numbers.all().delete()
            serials = [s.strip() for s in serial_numbers.split(',') if s.strip()]
            for serial in serials:
                SerialNumber.objects.create(
                    product_inflow=instance,
                    serial_number=serial,
                    status='in_stock'
                )
        return instance

class ProductOutflowSerializer(serializers.ModelSerializer):
    item_name = serializers.CharField(source='product.item.name', read_only=True)
    item_batch = serializers.CharField(source='product.item.batch', read_only=True)
    created_by_name = serializers.SerializerMethodField()

    class Meta:
        model = ProductOutflow
        fields = [
            'id', 'product', 'item_name', 'item_batch', 'customer_name', 'sales_order',
            'dispatch_date', 'quantity', 'created_by_name',
            'created_at', 'updated_at'
            # ❌ REMOVED: serial_numbers, input_serial_numbers
        ]
        read_only_fields = ['id', 'item_name', 'item_batch', 'created_by_name', 'created_at', 'updated_at']

    def get_created_by_name(self, obj):
        if obj.responsible_staff:
            try:
                profile = obj.responsible_staff.profile
                if profile.full_name:
                    return profile.full_name
            except UserProfile.DoesNotExist:
                pass
            return obj.responsible_staff.name or obj.responsible_staff.email
        return '—'

    # ✅ SIMPLE create/update (no serial numbers)
    def create(self, validated_data):
        validated_data['responsible_staff'] = self.context['request'].user
        return super().create(validated_data)

    def update(self, instance, validated_data):
        validated_data['responsible_staff'] = self.context['request'].user
        return super().update(instance, validated_data)