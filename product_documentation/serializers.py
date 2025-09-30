# product_documentation/serializers.py

from rest_framework import serializers
from .models import ProductInflow, ProductOutflow, ProductSerialNumber  # ✅ Fixed name
from inventory.models import Item
from accounts.models import User



class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['id', 'name', 'email']

class ProductSerialNumberSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProductSerialNumber
        fields = ['id', 'serial_number', 'status']

class ProductInflowSerializer(serializers.ModelSerializer):
    item_name = serializers.CharField(source='item.name', read_only=True)
    created_by_name = serializers.CharField(source='created_by.name', read_only=True)
    serial_numbers = ProductSerialNumberSerializer(many=True, read_only=True)
    input_serial_numbers = serializers.CharField(write_only=True, required=False, allow_blank=True)

    class Meta:
        model = ProductInflow
        fields = [
            'id', 'item', 'item_name', 'batch', 'vendor',
            'date_of_delivery', 'quantity', 'cost',
             'created_by', 'serial_numbers',
            'created_at', 'input_serial_numbers'
        ]
        read_only_fields = ['id', 'item_name', 'created_by', 'serial_numbers', 'created_at']

    def get_created_by(self, obj):
        user = obj.user
        if user:
            try:
                profile = user.profile
                if profile and profile.full_name:
                    return profile.full_name
            except:
                pass
            return user.name or user.email
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
                ProductSerialNumber.objects.create(
                    inflow=inflow,
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
                ProductSerialNumber.objects.create(
                    inflow=instance,
                    serial_number=serial,
                    status='in_stock'
                )
        return instance

class ProductOutflowSerializer(serializers.ModelSerializer):
    item_name = serializers.CharField(source='product.item.name', read_only=True)
    responsible_staff_name = serializers.CharField(source='responsible_staff.name', read_only=True)
    serial_numbers = ProductSerialNumberSerializer(many=True, read_only=True)
    input_serial_numbers = serializers.CharField(write_only=True, required=False, allow_blank=True)

    class Meta:
        model = ProductOutflow
        fields = [
            'id', 'product', 'item_name', 'customer_name', 'sales_order',
            'dispatch_date', 'quantity', 'responsible_staff', 'responsible_staff_name',
            'serial_numbers', 'created_at', 'input_serial_numbers'
        ]
        read_only_fields = ['id', 'item_name', 'responsible_staff_name', 'serial_numbers', 'created_at']

    def validate_input_serial_numbers(self, value):
        quantity = self.initial_data.get('quantity')
        if value and quantity:
            serials = [s.strip() for s in value.split(',') if s.strip()]
            if len(serials) != int(quantity):
                raise serializers.ValidationError("Number of serial numbers must match quantity.")
        return value

    def validate(self, data):
        product = data.get('product')
        serials_input = data.get('input_serial_numbers', '')
        serials = [s.strip() for s in serials_input.split(',') if s.strip()] if serials_input else []
        available_serials = product.serial_numbers.filter(status='in_stock').values_list('serial_number', flat=True)
        if serials and any(s not in available_serials for s in serials):
            raise serializers.ValidationError("Invalid or unavailable serial numbers selected.")
        return data

    def create(self, validated_data):
        serial_numbers = validated_data.pop('input_serial_numbers', '')
        validated_data['responsible_staff'] = self.context['request'].user
        outflow = ProductOutflow.objects.create(**validated_data)
        if serial_numbers:
            serials = [s.strip() for s in serial_numbers.split(',') if s.strip()]
            for serial in serials:
                serial_obj = ProductSerialNumber.objects.get(
                    inflow=outflow.product,
                    serial_number=serial,
                    status='in_stock'
                )
                serial_obj.status = 'dispatched'
                serial_obj.save()
                outflow.serial_numbers.add(serial_obj)
        return outflow

    def update(self, instance, validated_data):
        serial_numbers = validated_data.pop('input_serial_numbers', None)
        validated_data['responsible_staff'] = self.context['request'].user
        instance = super().update(instance, validated_data)
        if serial_numbers is not None:
            instance.serial_numbers.clear()
            serials = [s.strip() for s in serial_numbers.split(',') if s.strip()]
            for serial in serials:
                serial_obj = ProductSerialNumber.objects.get(
                    inflow=instance.product,
                    serial_number=serial,
                    status='in_stock'
                )
                serial_obj.status = 'dispatched'
                serial_obj.save()
                instance.serial_numbers.add(serial_obj)
        return instance