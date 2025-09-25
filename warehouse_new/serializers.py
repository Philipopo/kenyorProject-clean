from rest_framework import serializers
from .models import WarehouseItem
from inventory.models import Item, StorageBin

class WarehouseItemSerializer(serializers.ModelSerializer):
    item_name = serializers.CharField(source='item.name', read_only=True)
    storage_bin_id = serializers.CharField(source='storage_bin.bin_id', read_only=True, allow_null=True)
    part_number = serializers.CharField(source='item.part_number', read_only=True, allow_null=True)
    manufacturer = serializers.CharField(source='item.manufacturer', read_only=True, allow_null=True)
    batch = serializers.CharField(source='item.batch', read_only=True, allow_null=True)
    expiry_date = serializers.DateField(source='item.expiry_date', read_only=True, allow_null=True)

    class Meta:
        model = WarehouseItem
        fields = ['id', 'item', 'item_name', 'storage_bin', 'storage_bin_id', 'quantity', 'status', 'last_updated',
                  'part_number', 'manufacturer', 'batch', 'expiry_date']
        read_only_fields = ['id', 'item_name', 'storage_bin_id', 'part_number', 'manufacturer', 'batch', 'expiry_date', 'last_updated']

    def validate(self, data):
        item = data.get('item')  # This is already an Item instance, not an ID
        quantity = data.get('quantity')
        storage_bin = data.get('storage_bin')

        # Validate item quantity
        if item:
            if quantity > item.quantity:
                raise serializers.ValidationError({
                    'quantity': f'Quantity ({quantity}) exceeds available item quantity ({item.quantity}).'
                })
        else:
            raise serializers.ValidationError({'item': 'Item is required.'})

        # Validate storage bin capacity
        if storage_bin:
            # Calculate available capacity
            available_capacity = storage_bin.capacity - storage_bin.used
            
            # If updating an existing item, subtract its current quantity from used capacity
            if self.instance and self.instance.storage_bin == storage_bin:
                available_capacity += self.instance.quantity
                
            if quantity > available_capacity:
                raise serializers.ValidationError({
                    'quantity': f'Quantity ({quantity}) exceeds storage bin available capacity ({available_capacity}).'
                })

        return data

class ItemSerializer(serializers.ModelSerializer):
    class Meta:
        model = Item
        fields = ['id', 'name', 'part_number', 'manufacturer', 'batch', 'quantity', 'expiry_date']