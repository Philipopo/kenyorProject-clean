from rest_framework import serializers
from django.db import transaction
from .models import Warehouse, StorageBin, Item, StockRecord, StockMovement, InventoryAlert, ExpiryTrackedItem, InventoryActivityLog, WarehouseReceipt
import logging
from django.utils import timezone  # Add this import
import uuid

logger = logging.getLogger(__name__)

class WarehouseSerializer(serializers.ModelSerializer):
    total_bins = serializers.ReadOnlyField()
    used_capacity = serializers.ReadOnlyField()
    available_capacity = serializers.ReadOnlyField()
    usage_percentage = serializers.ReadOnlyField()
    created_by = serializers.SerializerMethodField()
    bin_locations = serializers.SerializerMethodField()
    state = serializers.CharField(max_length=100, required=False, allow_blank=True)
    country = serializers.CharField(max_length=100, required=False, allow_blank=True)

    class Meta:
        model = Warehouse
        fields = [
            'id', 'name', 'code', 'description', 'address', 'city', 'state', 'country',
            'capacity', 'is_active', 'total_bins', 'used_capacity', 'available_capacity',
            'usage_percentage', 'user', 'created_by', 'created_at', 'updated_at', 'bin_locations'
        ]
        read_only_fields = ['user', 'created_at', 'updated_at']

    def get_created_by(self, obj):
        if obj.user:
            return obj.user.name or obj.user.email
        return '—'

    def get_bin_locations(self, obj):
        bins = obj.bins.select_related('warehouse').all().order_by('row', 'rack', 'shelf')
        locations = {}
        for bin in bins:
            if bin.row not in locations:
                locations[bin.row] = {}
            if bin.rack not in locations[bin.row]:
                locations[bin.row][bin.rack] = []
            locations[bin.row][bin.rack].append({
                'id': bin.id,
                'shelf': bin.shelf,
                'bin_id': bin.bin_id,
                'type': bin.type,
                'capacity': bin.capacity,
                'current_load': bin.current_load,
                'usage_percentage': bin.usage_percentage,
                'description': bin.description
            })
        return locations

class ItemSerializer(serializers.ModelSerializer):
    material_id = serializers.CharField(read_only=True)
    total_quantity = serializers.SerializerMethodField()
    available_quantity = serializers.SerializerMethodField()
    created_by = serializers.SerializerMethodField()

    class Meta:
        model = Item
        fields = [
            'id', 'material_id', 'name', 'description', 'part_number', 'manufacturer', 'contact', 'batch', 'expiry_date',
            'min_stock_level', 'reserved_quantity', 'custom_fields', 'user', 'created_at',
            'total_quantity', 'available_quantity', 'created_by'
        ]
        read_only_fields = ['id', 'material_id', 'user', 'created_at', 'total_quantity', 'available_quantity', 'created_by']

    def get_total_quantity(self, obj):
        return obj.total_quantity()

    def get_available_quantity(self, obj):
        return obj.available_quantity()

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

    def validate_reserved_quantity(self, value):
        if value < 0:
            raise serializers.ValidationError("Reserved quantity cannot be negative.")
        
        instance = getattr(self, 'instance', None)
        
        if instance:
            total_qty = instance.total_quantity()
            if value > total_qty:
                raise serializers.ValidationError(
                    f"Reserved quantity ({value}) cannot exceed total stock ({total_qty}). "
                    f"Please add stock inflow first."
                )
        else:
            if value > 0:
                raise serializers.ValidationError(
                    "Reserved quantity must be 0 for new items. Please add stock inflow first."
                )
        
        return value

    def validate(self, data):
        reserved_qty = data.get('reserved_quantity', getattr(self.instance, 'reserved_quantity', 0))
        
        if self.instance:
            total_qty = self.instance.total_quantity()
            if reserved_qty > total_qty:
                raise serializers.ValidationError({
                    'reserved_quantity': f"Reserved quantity ({reserved_qty}) cannot exceed total stock ({total_qty}). Please add stock inflow first."
                })
        
        return data

class StockRecordSerializer(serializers.ModelSerializer):
    item_name = serializers.CharField(source='item.name', read_only=True)
    material_id = serializers.CharField(source='item.material_id', read_only=True)
    storage_bin_id = serializers.CharField(source='storage_bin.bin_id', read_only=True)
    item = ItemSerializer(read_only=True)

    class Meta:
        model = StockRecord
        fields = ['id', 'item', 'item_name', 'material_id', 'storage_bin', 'storage_bin_id', 'quantity', 'user', 'created_at']
        read_only_fields = ['user', 'item_name', 'material_id', 'storage_bin_id', 'created_at']

class StorageBinSerializer(serializers.ModelSerializer):
    warehouse_name = serializers.CharField(source='warehouse.name', read_only=True)
    warehouse_code = serializers.CharField(source='warehouse.code', read_only=True)
    usage_percentage = serializers.SerializerMethodField()
    created_by = serializers.SerializerMethodField()
    location_display = serializers.SerializerMethodField()
    stock_records = StockRecordSerializer(many=True, read_only=True)

    class Meta:
        model = StorageBin
        fields = [
            'id', 'warehouse', 'warehouse_name', 'warehouse_code', 'bin_id',
            'row', 'rack', 'shelf', 'type', 'capacity', 'current_load',
            'description', 'usage_percentage', 'created_by', 'location_display',
            'created_at', 'updated_at', 'stock_records'
        ]
        read_only_fields = ['user', 'current_load', 'created_at', 'updated_at']

    def get_usage_percentage(self, obj):
        if obj.capacity == 0:
            return 0
        return round((obj.current_load / obj.capacity) * 100, 2)

    def get_created_by(self, obj):
        if obj.user:
            return obj.user.name or obj.user.email
        return '—'

    def get_location_display(self, obj):
        location = f"Row {obj.row}, Rack {obj.rack}"
        if obj.shelf:
            location += f", Shelf {obj.shelf}"
        return location

    def validate(self, data):
        if 'bin_id' in data:
            queryset = StorageBin.objects.filter(bin_id=data['bin_id'])
            if self.instance:
                queryset = queryset.exclude(pk=self.instance.pk)
            if queryset.exists():
                raise serializers.ValidationError({"bin_id": "Bin ID must be unique."})
        
        if 'warehouse' in data and data['warehouse']:
            bin_id = data.get('bin_id')
            if bin_id:
                existing_bin = StorageBin.objects.filter(
                    bin_id=bin_id
                ).exclude(
                    pk=getattr(self.instance, 'pk', None)
                ).first()
                if existing_bin and existing_bin.warehouse and existing_bin.warehouse != data['warehouse']:
                    raise serializers.ValidationError({
                        "warehouse": f"Bin {bin_id} already belongs to warehouse '{existing_bin.warehouse.name}'. Remove it first."
                    })
        
        warehouse = data.get('warehouse', getattr(self.instance, 'warehouse', None))
        row = data.get('row', getattr(self.instance, 'row', None))
        rack = data.get('rack', getattr(self.instance, 'rack', None))
        shelf = data.get('shelf', getattr(self.instance, 'shelf', ''))
        
        if warehouse and row and rack:
            queryset = StorageBin.objects.filter(
                warehouse=warehouse, row=row, rack=rack, shelf=shelf
            )
            if self.instance:
                queryset = queryset.exclude(pk=self.instance.pk)
            if queryset.exists():
                raise serializers.ValidationError({
                    "location": "A bin already exists at this location in the warehouse."
                })
        
        return data



class StockMovementSerializer(serializers.ModelSerializer):
    item_name = serializers.CharField(source='item.name', read_only=True)
    material_id = serializers.CharField(source='item.material_id', read_only=True)
    storage_bin_id = serializers.CharField(source='storage_bin.bin_id', read_only=True)
    batch = serializers.CharField(source='item.batch', read_only=True)
    user_display = serializers.SerializerMethodField()
    warehouse_receipt = serializers.PrimaryKeyRelatedField(read_only=True)

    class Meta:
        model = StockMovement
        fields = [
            'id', 'item', 'item_name', 'material_id', 'storage_bin', 'storage_bin_id', 'movement_type',
            'quantity', 'user', 'user_display', 'timestamp', 'notes', 'batch', 'warehouse_receipt'
        ]
        read_only_fields = ['user', 'item_name', 'material_id', 'storage_bin_id', 'timestamp', 'batch', 'user_display', 'warehouse_receipt']

    def get_user_display(self, obj):
        if obj.user:
            if hasattr(obj.user, 'name') and obj.user.name:
                return obj.user.name
            return obj.user.email
        return '—'


class InventoryAlertSerializer(serializers.ModelSerializer):
    item_name = serializers.CharField(source='related_item.name', read_only=True, allow_null=True)
    material_id = serializers.CharField(source='related_item.material_id', read_only=True, allow_null=True)
    bin_id = serializers.CharField(source='related_bin.bin_id', read_only=True, allow_null=True)

    class Meta:
        model = InventoryAlert
        fields = ['id', 'alert_type', 'message', 'related_item', 'item_name', 'material_id', 'related_bin', 'bin_id', 'created_at', 'is_resolved']
        read_only_fields = ['created_at', 'item_name', 'material_id', 'bin_id']

class ExpiryTrackedItemSerializer(serializers.ModelSerializer):
    item_name = serializers.CharField(source='item.name', read_only=True)
    material_id = serializers.CharField(source='item.material_id', read_only=True)

    class Meta:
        model = ExpiryTrackedItem
        fields = ['id', 'item', 'item_name', 'material_id', 'batch', 'quantity', 'expiry_date', 'user', 'created_at']
        read_only_fields = ['user', 'created_at', 'item_name', 'material_id']

class StockInSerializer(serializers.Serializer):
    item_id = serializers.IntegerField()
    storage_bin_id = serializers.IntegerField()
    quantity = serializers.IntegerField(min_value=1)
    notes = serializers.CharField(max_length=255, required=False, allow_blank=True)

    def validate(self, data):
        try:
            item = Item.objects.get(id=data['item_id'])
            storage_bin = StorageBin.objects.get(id=data['storage_bin_id'])
        except Item.DoesNotExist:
            raise serializers.ValidationError("Invalid item_id.")
        except StorageBin.DoesNotExist:
            raise serializers.ValidationError("Invalid storage_bin_id.")

        free_space = storage_bin.capacity - storage_bin.current_load
        if data['quantity'] > free_space:
            InventoryAlert.objects.create(
                user=self.context['request'].user,
                alert_type='CRITICAL',
                message=f"Cannot add {data['quantity']} to bin {storage_bin.bin_id}: insufficient space (available: {free_space}).",
                related_bin=storage_bin,
                related_item=item
            )
            raise serializers.ValidationError(
                f"Insufficient space in bin {storage_bin.bin_id}. Available: {free_space}, requested: {data['quantity']}."
            )

        data['item'] = item
        data['storage_bin'] = storage_bin
        return data

    def save(self):
        with transaction.atomic():
            item = self.validated_data['item']
            storage_bin = self.validated_data['storage_bin']
            quantity = self.validated_data['quantity']
            notes = self.validated_data.get('notes', '')

            stock_record, created = StockRecord.objects.get_or_create(
                item=item,
                storage_bin=storage_bin,
                defaults={'quantity': 0, 'user': self.context['request'].user}
            )
            stock_record.quantity += quantity
            stock_record.save()

            storage_bin.current_load += quantity
            storage_bin.save()

            StockMovement.objects.create(
                user=self.context['request'].user,
                item=item,
                storage_bin=storage_bin,
                movement_type='IN',
                quantity=quantity,
                notes=notes
            )

            logger.info(f"Stock In: {quantity} of {item.name} ({item.material_id}) to {storage_bin.bin_id} by {self.context['request'].user.email}")




class StockOutSerializer(serializers.Serializer):
    item_id = serializers.IntegerField()
    storage_bin_id = serializers.IntegerField()
    quantity = serializers.IntegerField(min_value=1)
    notes = serializers.CharField(max_length=255, required=False, allow_blank=True)
    recipient = serializers.CharField(max_length=255, required=False, allow_blank=True)

    def validate(self, data):
        try:
            item = Item.objects.select_related('user').get(id=data['item_id'])
            storage_bin = StorageBin.objects.select_related('warehouse').get(id=data['storage_bin_id'])
        except Item.DoesNotExist:
            raise serializers.ValidationError("Invalid item_id.")
        except StorageBin.DoesNotExist:
            raise serializers.ValidationError("Invalid storage_bin_id.")

        stock_record = StockRecord.objects.filter(item=item, storage_bin=storage_bin).first()
        if not stock_record or stock_record.quantity < data['quantity']:
            available = stock_record.quantity if stock_record else 0
            InventoryAlert.objects.create(
                user=self.context['request'].user,
                alert_type='CRITICAL',
                message=f"Cannot remove {data['quantity']} of {item.name} ({item.material_id}) from bin {storage_bin.bin_id}: insufficient stock (available: {available}).",
                related_bin=storage_bin,
                related_item=item
            )
            raise serializers.ValidationError(
                f"Insufficient stock in bin {storage_bin.bin_id}. Available: {available}, requested: {data['quantity']}."
            )

        available = item.available_quantity()
        if data['quantity'] > available:
            InventoryAlert.objects.create(
                user=self.context['request'].user,
                alert_type='WARNING',
                message=f"Requested quantity {data['quantity']} exceeds available stock ({available}) for {item.name} ({item.material_id}) due to reservations.",
                related_item=item
            )
            raise serializers.ValidationError(
                f"Requested quantity exceeds available stock ({available}) due to reservations."
            )

        data['item'] = item
        data['storage_bin'] = storage_bin
        data['stock_record'] = stock_record
        return data

    def save(self):
        with transaction.atomic():
            item = self.validated_data['item']
            storage_bin = self.validated_data['storage_bin']
            quantity = self.validated_data['quantity']
            stock_record = self.validated_data['stock_record']
            notes = self.validated_data.get('notes', '')
            recipient = self.validated_data.get('recipient', '')

            # Update stock record
            stock_record.quantity -= quantity
            if stock_record.quantity == 0:
                stock_record.delete()
            else:
                stock_record.save()

            # Update bin's current load
            storage_bin.current_load = max(0, storage_bin.current_load - quantity)

            # Ensure storage_bin has a warehouse
            if not storage_bin.warehouse:
                warehouse, created = Warehouse.objects.get_or_create(
                    user=self.context['request'].user,
                    name="Default Warehouse",
                    code="WH-DEFAULT",
                    defaults={'capacity': 1000}
                )
                storage_bin.warehouse = warehouse
                storage_bin.save()
                logger.info(f"Assigned default warehouse to bin {storage_bin.bin_id}")

            storage_bin.save()

            # Create warehouse receipt first
            if not recipient:
                recipient = notes if notes else (
                    self.context['request'].user.name or
                    self.context['request'].user.email or
                    'Unknown Recipient'
                )
            receipt = WarehouseReceipt.objects.create(
                receipt_number=generate_receipt_number(),
                issued_from_warehouse=storage_bin.warehouse,
                issued_from_bin=storage_bin,
                item=item,
                quantity=quantity,
                recipient=recipient,
                purpose=notes or f"Stock out for {item.name}",
                created_by=self.context['request'].user,
                delivery_to=recipient,
                transfer_order_no=f"TO-{item.id}-{timezone.now().strftime('%Y%m%d%H%M%S')}",  # Temporary unique ID
                plant_site=storage_bin.warehouse.code,
                bin_location=storage_bin.bin_id,
                qty_picked=quantity,
                qty_remaining=item.available_quantity(),
                unloading_point='Default Unloading Point',
                picker=self.context['request'].user.name or self.context['request'].user.email,
                controller='N/A'
            )
            logger.info(
                f"Warehouse Receipt {receipt.receipt_number} created for stock out: "
                f"{quantity} of {item.name} ({item.material_id}) from {storage_bin.bin_id} "
                f"by {self.context['request'].user.email}"
            )

            # Create stock movement with linked receipt
            stock_movement = StockMovement.objects.create(
                user=self.context['request'].user,
                item=item,
                storage_bin=storage_bin,
                movement_type='OUT',
                quantity=quantity,
                notes=notes,
                warehouse_receipt=receipt
            )

            # Update receipt with stock movement
            receipt.stock_movement = stock_movement
            receipt.transfer_order_no = f"TO-{stock_movement.id}"  # Update with final stock movement ID
            receipt.save()

            logger.info(
                f"Stock Out: {quantity} of {item.name} ({item.material_id}) from "
                f"{storage_bin.bin_id} by {self.context['request'].user.email}"
            )
            return stock_movement


class StockOutSerializer(serializers.Serializer):
    item_id = serializers.IntegerField()
    storage_bin_id = serializers.IntegerField()
    quantity = serializers.IntegerField(min_value=1)
    notes = serializers.CharField(max_length=255, required=False, allow_blank=True)
    recipient = serializers.CharField(max_length=255, required=False, allow_blank=True)

    def validate(self, data):
        try:
            item = Item.objects.select_related('user').get(id=data['item_id'])
            storage_bin = StorageBin.objects.select_related('warehouse').get(id=data['storage_bin_id'])
        except Item.DoesNotExist:
            raise serializers.ValidationError("Invalid item_id.")
        except StorageBin.DoesNotExist:
            raise serializers.ValidationError("Invalid storage_bin_id.")

        stock_record = StockRecord.objects.filter(item=item, storage_bin=storage_bin).first()
        if not stock_record or stock_record.quantity < data['quantity']:
            available = stock_record.quantity if stock_record else 0
            InventoryAlert.objects.create(
                user=self.context['request'].user,
                alert_type='CRITICAL',
                message=f"Cannot remove {data['quantity']} of {item.name} ({item.material_id}) from bin {storage_bin.bin_id}: insufficient stock (available: {available}).",
                related_bin=storage_bin,
                related_item=item
            )
            raise serializers.ValidationError(
                f"Insufficient stock in bin {storage_bin.bin_id}. Available: {available}, requested: {data['quantity']}."
            )

        available = item.available_quantity()
        if data['quantity'] > available:
            InventoryAlert.objects.create(
                user=self.context['request'].user,
                alert_type='WARNING',
                message=f"Requested quantity {data['quantity']} exceeds available stock ({available}) for {item.name} ({item.material_id}) due to reservations.",
                related_item=item
            )
            raise serializers.ValidationError(
                f"Requested quantity exceeds available stock ({available}) due to reservations."
            )

        data['item'] = item
        data['storage_bin'] = storage_bin
        data['stock_record'] = stock_record
        return data

    def save(self):
        with transaction.atomic():
            item = self.validated_data['item']
            storage_bin = self.validated_data['storage_bin']
            quantity = self.validated_data['quantity']
            stock_record = self.validated_data['stock_record']
            notes = self.validated_data.get('notes', '')
            recipient = self.validated_data.get('recipient', '')

            # Update stock record
            stock_record.quantity -= quantity
            if stock_record.quantity == 0:
                stock_record.delete()
            else:
                stock_record.save()

            # Update bin's current load
            storage_bin.current_load = max(0, storage_bin.current_load - quantity)

            # Ensure storage_bin has a warehouse
            if not storage_bin.warehouse:
                warehouse, created = Warehouse.objects.get_or_create(
                    user=self.context['request'].user,
                    name="Default Warehouse",
                    code="WH-DEFAULT",
                    defaults={'capacity': 1000}
                )
                storage_bin.warehouse = warehouse
                storage_bin.save()
                logger.info(f"Assigned default warehouse to bin {storage_bin.bin_id}")

            storage_bin.save()

            # Create warehouse receipt first (omit receipt_number, let model generate it)
            if not recipient:
                recipient = notes if notes else (
                    self.context['request'].user.name or
                    self.context['request'].user.email or
                    'Unknown Recipient'
                )
            receipt = WarehouseReceipt.objects.create(
                issued_from_warehouse=storage_bin.warehouse,
                issued_from_bin=storage_bin,
                item=item,
                quantity=quantity,
                recipient=recipient,
                purpose=notes or f"Stock out for {item.name}",
                created_by=self.context['request'].user,
                delivery_to=recipient,
                transfer_order_no=f"TO-{item.id}-{timezone.now().strftime('%Y%m%d%H%M%S')}",  # Temporary unique ID
                plant_site=storage_bin.warehouse.code,
                bin_location=storage_bin.bin_id,
                qty_picked=quantity,
                qty_remaining=item.available_quantity(),
                unloading_point='Default Unloading Point',
                picker=self.context['request'].user.name or self.context['request'].user.email,
                controller='N/A'
            )
            logger.info(
                f"Warehouse Receipt {receipt.receipt_number} created for stock out: "
                f"{quantity} of {item.name} ({item.material_id}) from {storage_bin.bin_id} "
                f"by {self.context['request'].user.email}"
            )

            # Create stock movement with linked receipt
            stock_movement = StockMovement.objects.create(
                user=self.context['request'].user,
                item=item,
                storage_bin=storage_bin,
                movement_type='OUT',
                quantity=quantity,
                notes=notes,
                warehouse_receipt=receipt
            )

            # Update receipt with stock movement
            receipt.stock_movement = stock_movement
            receipt.transfer_order_no = f"TO-{stock_movement.id}"  # Update with final stock movement ID
            receipt.save()

            logger.info(
                f"Stock Out: {quantity} of {item.name} ({item.material_id}) from "
                f"{storage_bin.bin_id} by {self.context['request'].user.email}"
            )
            return stock_movement



class InventoryActivityLogSerializer(serializers.ModelSerializer):
    user_name = serializers.CharField(source='user.name', read_only=True)
    user_email = serializers.CharField(source='user.email', read_only=True)
    
    class Meta:
        model = InventoryActivityLog
        fields = '__all__'
        read_only_fields = ['user', 'timestamp']


class WarehouseReceiptSerializer(serializers.ModelSerializer):
    class Meta:
        model = WarehouseReceipt
        fields = '__all__'
        read_only_fields = ['receipt_number', 'created_at', 'created_by', 'stock_movement']