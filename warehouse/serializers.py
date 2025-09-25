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
        item_id = data.get('item')  # Get item ID (e.g., 1)
        quantity = data.get('quantity')
        storage_bin = data.get('storage_bin')

        # Fetch Item instance
        if item_id:
            try:
                item = Item.objects.get(id=item_id)
            except Item.DoesNotExist:
                raise serializers.ValidationError({'item': 'Item does not exist.'})
            if quantity > item.quantity:
                raise serializers.ValidationError({'quantity': f'Quantity ({quantity}) exceeds available item quantity ({item.quantity}).'})
        else:
            raise serializers.ValidationError({'item': 'Item is required.'})

        # Validate storage bin capacity
        if storage_bin and quantity > (storage_bin.capacity - storage_bin.used):
            raise serializers.ValidationError({'quantity': f'Quantity ({quantity}) exceeds storage bin capacity ({storage_bin.capacity - storage_bin.used}).'})

        return data

        

class ItemSerializer(serializers.ModelSerializer):
    class Meta:
        model = Item
        fields = ['id', 'name', 'part_number', 'manufacturer', 'batch', 'quantity', 'expiry_date']