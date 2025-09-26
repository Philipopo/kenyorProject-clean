# procurement/serializers.py
from rest_framework import serializers
from django.db import transaction
from django.contrib.auth import get_user_model
from .models import (
    Requisition, RequisitionItem, PurchaseOrder, POItem, 
    Receiving, ReceivingItem, Vendor, ProcurementAuditLog, ApprovalBoard
)
from inventory.serializers import ItemSerializer
User = get_user_model()

class ApprovalBoardSerializer(serializers.ModelSerializer):
    user_email = serializers.CharField(source='user.email', read_only=True)
    user_name = serializers.CharField(source='user.name', read_only=True)
    added_by_name = serializers.CharField(source='added_by.name', read_only=True)
    
    class Meta:
        model = ApprovalBoard
        fields = '__all__'
        read_only_fields = ['added_by', 'added_at']

class VendorSerializer(serializers.ModelSerializer):
    class Meta:
        model = Vendor
        fields = '__all__'
        read_only_fields = ['created_by', 'created_at', 'updated_at']

    def validate(self, data):
        if data.get('lead_time', 0) <= 0:
            raise serializers.ValidationError({'lead_time': 'Lead time must be positive.'})
        return data

class RequisitionItemSerializer(serializers.ModelSerializer):
    item_details = ItemSerializer(source='item', read_only=True)
    
    class Meta:
        model = RequisitionItem
        fields = ['id', 'item', 'item_details', 'quantity', 'unit_cost', 'total_cost', 'notes']
        read_only_fields = ['total_cost']

    def validate(self, data):
        if data.get('quantity', 0) <= 0:
            raise serializers.ValidationError({'quantity': 'Quantity must be positive.'})
        if data.get('unit_cost', 0) <= 0:
            raise serializers.ValidationError({'unit_cost': 'Unit cost must be positive.'})
        return data


class RequisitionSerializer(serializers.ModelSerializer):
    items = RequisitionItemSerializer(many=True, required=False)
    requested_by_name = serializers.CharField(source='requested_by.name', read_only=True)
    created_by_name = serializers.CharField(source='created_by.name', read_only=True)
    approved_by_name = serializers.CharField(source='approved_by.name', read_only=True)
    
    class Meta:
        model = Requisition
        fields = '__all__'
        read_only_fields = [
            'code', 'approved_by', 'created_at', 'updated_at', 'approved_at',
            'requested_by', 'created_by'
        ]


    def create(self, validated_data):
        # Automatically set requested_by and created_by from request user
        user = self.context['request'].user
        validated_data['requested_by'] = user
        validated_data['created_by'] = user
        items_data = validated_data.pop('items', [])
        requisition = Requisition.objects.create(**validated_data)
        
        for item_data in items_data:
            RequisitionItem.objects.create(requisition=requisition, **item_data)
        
        return requisition



class POItemSerializer(serializers.ModelSerializer):
    item_details = ItemSerializer(source='item', read_only=True)
    
    class Meta:
        model = POItem
        fields = ['id', 'item', 'item_details', 'quantity', 'received_quantity', 'unit_price', 'total_price', 'notes']
        read_only_fields = ['received_quantity', 'total_price']

    def validate(self, data):
        if data.get('quantity', 0) <= 0:
            raise serializers.ValidationError({'quantity': 'Quantity must be positive.'})
        if data.get('unit_price', 0) <= 0:
            raise serializers.ValidationError({'unit_price': 'Unit price must be positive.'})
        return data

class PurchaseOrderSerializer(serializers.ModelSerializer):
    items = POItemSerializer(many=True, required=False)
    vendor_details = VendorSerializer(source='vendor', read_only=True)
    requisition_code = serializers.CharField(source='requisition.code', read_only=True)
    created_by_name = serializers.CharField(source='created_by.name', read_only=True)
    
    class Meta:
        model = PurchaseOrder
        fields = '__all__'
        read_only_fields = [
            'code', 'total_amount', 'approved_by', 'created_at', 
            'updated_at', 'approved_at'
        ]

    def validate(self, data):
        # Ensure vendor is selected
        if not data.get('vendor'):
            raise serializers.ValidationError({'vendor': 'Vendor is required.'})
        
        # Ensure items are provided for submission
        if self.context['request'].method == 'POST' and data.get('status') != 'draft':
            if not self.initial_data.get('items') or len(self.initial_data.get('items', [])) == 0:
                raise serializers.ValidationError({'items': 'At least one item is required.'})
        
        return data

    @transaction.atomic
    def create(self, validated_data):
        items_data = validated_data.pop('items', [])
        po = PurchaseOrder.objects.create(**validated_data)
        
        total_amount = 0
        for item_data in items_data:
            po_item = POItem.objects.create(po=po, **item_data)
            total_amount += po_item.total_price
        
        po.total_amount = total_amount
        po.save()
        return po

    @transaction.atomic
    def update(self, instance, validated_data):
        items_data = validated_data.pop('items', None)
        instance = super().update(instance, validated_data)
        
        if items_data is not None:
            # Update total amount
            total_amount = 0
            for item_data in items_data:
                po_item = POItem.objects.create(po=instance, **item_data)
                total_amount += po_item.total_price
            instance.total_amount = total_amount
            instance.save()
        
        return instance

class ReceivingItemSerializer(serializers.ModelSerializer):
    item_name = serializers.CharField(source='po_item.item.name', read_only=True)
    po_item_details = POItemSerializer(source='po_item', read_only=True)
    
    class Meta:
        model = ReceivingItem
        fields = '__all__'
        read_only_fields = ['rejected_quantity']

    def validate(self, data):
        po_item = data.get('po_item')
        received_quantity = data.get('received_quantity', 0)
        accepted_quantity = data.get('accepted_quantity', 0)
        
        if received_quantity <= 0:
            raise serializers.ValidationError({'received_quantity': 'Received quantity must be positive.'})
        
        if accepted_quantity < 0:
            raise serializers.ValidationError({'accepted_quantity': 'Accepted quantity cannot be negative.'})
        
        if accepted_quantity > received_quantity:
            raise serializers.ValidationError({'accepted_quantity': 'Accepted quantity cannot exceed received quantity.'})
        
        if accepted_quantity > 0 and not data.get('storage_bin'):
            raise serializers.ValidationError({'storage_bin': 'Storage bin is required for accepted items.'})
        
        if received_quantity > (po_item.quantity - po_item.received_quantity):
            raise serializers.ValidationError({
                'received_quantity': f'Cannot receive more than remaining quantity. Remaining: {po_item.quantity - po_item.received_quantity}'
            })
        
        return data

class ReceivingSerializer(serializers.ModelSerializer):
    items = ReceivingItemSerializer(many=True, required=False)
    po_code = serializers.CharField(source='po.code', read_only=True)
    vendor_name = serializers.CharField(source='po.vendor.name', read_only=True)
    created_by_name = serializers.CharField(source='created_by.name', read_only=True)
    
    class Meta:
        model = Receiving
        fields = '__all__'
        read_only_fields = ['grn', 'created_at', 'updated_at']

    def validate(self, data):
        if not data.get('po'):
            raise serializers.ValidationError({'po': 'Purchase Order is required.'})
        
        if self.context['request'].method == 'POST':
            if not self.initial_data.get('items') or len(self.initial_data.get('items', [])) == 0:
                raise serializers.ValidationError({'items': 'At least one receiving item is required.'})
        
        return data

    @transaction.atomic
    def create(self, validated_data):
        items_data = validated_data.pop('items', [])
        receiving = Receiving.objects.create(**validated_data)
        
        for item_data in items_data:
            ReceivingItem.objects.create(receiving=receiving, **item_data)
        
        # Update PO status
        receiving.update_po_status()
        return receiving

    @transaction.atomic
    def update(self, instance, validated_data):
        items_data = validated_data.pop('items', None)
        instance = super().update(instance, validated_data)
        
        if items_data is not None:
            # Clear existing items and add new ones
            instance.items.all().delete()
            for item_data in items_data:
                ReceivingItem.objects.create(receiving=instance, **item_data)
            
            # Update PO status
            instance.update_po_status()
        
        return instance

class ProcurementAuditLogSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProcurementAuditLog
        fields = '__all__'