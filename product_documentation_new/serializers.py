from rest_framework import serializers
from .models import ProductInflow, ProductOutflow, SerialNumber
from inventory.models import Item

class SerialNumberSerializer(serializers.ModelSerializer):
    class Meta:
        model = SerialNumber
        fields = ['id', 'serial_number', 'status']

class ProductInflowSerializer(serializers.ModelSerializer):
    item_name = serializers.CharField(source='item.name', read_only=True)
    item_batch = serializers.CharField(source='item.batch', read_only=True)
    serial_numbers = SerialNumberSerializer(source='new_serial_numbers', many=True, read_only=True)

    class Meta:
        model = ProductInflow
        fields = [
            'id', 'item', 'item_name', 'item_batch', 'batch', 'vendor',
            'date_of_delivery', 'quantity', 'cost', 'serial_numbers',
            'created_at', 'updated_at'
        ]
        
        read_only_fields = ['id', 'item_name', 'item_batch', 'serial_numbers', 'created_at', 'updated_at']

    def validate_input_serial_numbers(self, value):
        quantity = self.initial_data.get('quantity')
        if value and quantity:
            serials = [s.strip() for s in value.split(',') if s.strip()]
            if len(serials) != int(quantity):
                raise serializers.ValidationError(
                    "Number of serial numbers must match quantity."
                )
        return value

    def create(self, validated_data):
        serial_numbers = validated_data.pop('input_serial_numbers', '')
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
        instance = super().update(instance, validated_data)
        if serial_numbers is not None:
            # clear old serials
            instance.new_serial_numbers.all().delete()
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
    serial_numbers = SerialNumberSerializer(many=True, read_only=True)
    input_serial_numbers = serializers.CharField(write_only=True, required=False, allow_blank=True)

    class Meta:
        model = ProductOutflow
        fields = [
            'id', 'product', 'item_name', 'item_batch', 'customer_name', 'sales_order',
            'dispatch_date', 'quantity', 'serial_numbers', 'created_at', 'updated_at',
            'input_serial_numbers'
        ]
        read_only_fields = ['id', 'item_name', 'item_batch', 'serial_numbers', 'created_at', 'updated_at']

    def validate_input_serial_numbers(self, value):
        quantity = self.initial_data.get('quantity')
        if value and quantity:
            serials = [s.strip() for s in value.split(',') if s.strip()]
            if len(serials) != int(quantity):
                raise serializers.ValidationError(
                    "Number of serial numbers must match quantity."
                )
        return value

    def validate(self, data):
        product = data.get('product')
        quantity = data.get('quantity')
        serials = data.get('input_serial_numbers', '')
        serials = [s.strip() for s in serials.split(',') if s.strip()] if serials else []
        available_serials = product.new_serial_numbers.filter(status='in_stock').values_list('serial_number', flat=True)
        if serials and any(s not in available_serials for s in serials):
            raise serializers.ValidationError("Invalid or unavailable serial numbers selected.")
        return data

    def create(self, validated_data):
        serial_numbers = validated_data.pop('input_serial_numbers', '')
        outflow = ProductOutflow.objects.create(**validated_data)
        if serial_numbers:
            serials = [s.strip() for s in serial_numbers.split(',') if s.strip()]
            for serial in serials:
                serial_obj = SerialNumber.objects.get(
                    product_inflow=outflow.product,
                    serial_number=serial,
                    status='in_stock'
                )
                serial_obj.status = 'shipped'
                serial_obj.product_outflow = outflow
                serial_obj.save()
        return outflow

    def update(self, instance, validated_data):
        serial_numbers = validated_data.pop('input_serial_numbers', None)
        instance = super().update(instance, validated_data)
        if serial_numbers is not None:
            instance.new_serial_numbers.all().update(status='in_stock', product_outflow=None)
            serials = [s.strip() for s in serial_numbers.split(',') if s.strip()]
            for serial in serials:
                serial_obj = SerialNumber.objects.get(
                    product_inflow=instance.product,
                    serial_number=serial,
                    status='in_stock'
                )
                serial_obj.status = 'shipped'
                serial_obj.product_outflow = instance
                serial_obj.save()
        return instance

class ItemSerializer(serializers.ModelSerializer):
    class Meta:
        model = Item
        fields = ['id', 'name', 'batch']