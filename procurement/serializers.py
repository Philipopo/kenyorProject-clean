# procurement/serializers.py
from rest_framework import serializers
from .models import Requisition, PurchaseOrder, POItem, Receiving, GoodsReceipt, Vendor

class RequisitionSerializer(serializers.ModelSerializer):
    class Meta:
        model = Requisition
        fields = '__all__'
        read_only_fields = ['created_by', 'created_at', 'code']

    def validate(self, data):
        if data.get('quantity', 0) <= 0:
            raise serializers.ValidationError({'quantity': 'Quantity must be positive.'})
        if data.get('cost', 0) <= 0:
            raise serializers.ValidationError({'cost': 'Cost must be positive.'})
        return data


class VendorSerializer(serializers.ModelSerializer):
    class Meta:
        model = Vendor
        fields = ['id', 'name', 'details', 'lead_time', 'ratings', 'document', 'created_by']
        read_only_fields = ['created_by']

    def validate(self, data):
        if data.get('lead_time', 0) <= 0:
            raise serializers.ValidationError({'lead_time': 'Lead time must be positive.'})
        return data


class PurchaseOrderSerializer(serializers.ModelSerializer):
    vendor = VendorSerializer(read_only=True)
    vendor_id = serializers.PrimaryKeyRelatedField(
        queryset=Vendor.objects.all(),
        source='vendor',
        write_only=True,
        required=False
    )
    requisition_id = serializers.PrimaryKeyRelatedField(
        queryset=Requisition.objects.all(),
        source='requisition',
        write_only=True,
        required=False
    )

    class Meta:
        model = PurchaseOrder
        fields = [
            'id', 'code', 'requisition', 'requisition_id', 'vendor', 'vendor_id',
            'item_name', 'eoq', 'amount', 'date', 'status', 'notes', 'created_by'
        ]
        read_only_fields = ['created_by', 'date', 'code']

    def validate(self, data):
        if data.get('eoq', 0) < 0:
            raise serializers.ValidationError({'eoq': 'EOQ must be non-negative.'})
        if data.get('amount', 0) <= 0:
            raise serializers.ValidationError({'amount': 'Amount must be positive.'})
        return data


class POItemSerializer(serializers.ModelSerializer):
    po_code = serializers.CharField(write_only=True, required=True)

    class Meta:
        model = POItem
        fields = ['id', 'po', 'po_code', 'name', 'quantity', 'unit', 'created_by']
        read_only_fields = ['po', 'created_by']

    def validate(self, data):
        po_code = data.get('po_code')
        if po_code:
            try:
                data['po'] = PurchaseOrder.objects.get(code=po_code)
            except PurchaseOrder.DoesNotExist:
                raise serializers.ValidationError({'po_code': 'Purchase Order with this code not found.'})
        if data.get('quantity', 0) <= 0:
            raise serializers.ValidationError({'quantity': 'Quantity must be positive.'})
        return data

    def create(self, validated_data):
        validated_data.pop('po_code')
        return super().create(validated_data)

    def update(self, validated_data):
        validated_data.pop('po_code', None)
        return super().update(validated_data)


class ReceivingSerializer(serializers.ModelSerializer):
    po_code = serializers.CharField(write_only=True, required=True)
    grn_code = serializers.CharField(write_only=True)
    invoice_code = serializers.CharField(write_only=True)
    attachment = serializers.FileField(write_only=True, required=False)

    class Meta:
        model = Receiving
        fields = ['id', 'po', 'po_code', 'grn', 'grn_code', 'invoice', 'invoice_code', 'attachment', 'document', 'matched', 'received_at', 'created_by']
        read_only_fields = ['po', 'matched', 'received_at', 'created_by']

    def validate(self, data):
        po_code = data.get('po_code')
        if po_code:
            try:
                data['po'] = PurchaseOrder.objects.get(code=po_code)
            except PurchaseOrder.DoesNotExist:
                raise serializers.ValidationError({'po_code': 'Purchase Order with this code not found.'})
        if not data.get('grn_code'):
            raise serializers.ValidationError({'grn_code': 'GRN code is required.'})
        if not data.get('invoice_code'):
            raise serializers.ValidationError({'invoice_code': 'Invoice code is required.'})
        return data

    def create(self, validated_data):
        po_code = validated_data.pop('po_code')
        grn_code = validated_data.pop('grn_code')
        invoice_code = validated_data.pop('invoice_code')
        attachment = validated_data.pop('attachment', None)
        po = PurchaseOrder.objects.get(code=po_code)
        receiving = Receiving.objects.create(
            po=po,
            grn=grn_code,
            invoice=invoice_code,
            matched=True,
            document=attachment
        )
        return receiving

    def update(self, instance, validated_data):
        po_code = validated_data.pop('po_code', None)
        if po_code:
            try:
                validated_data['po'] = PurchaseOrder.objects.get(code=po_code)
            except PurchaseOrder.DoesNotExist:
                raise serializers.ValidationError({'po_code': 'Purchase Order with this code not found.'})
        validated_data.pop('grn_code', None)
        validated_data.pop('invoice_code', None)
        validated_data.pop('attachment', None)
        return super().update(instance, validated_data)


class GoodsReceiptSerializer(serializers.ModelSerializer):
    class Meta:
        model = GoodsReceipt
        fields = ['id', 'po_code', 'grn_code', 'invoice_code', 'match_success', 'attachment', 'timestamp', 'created_by']
        read_only_fields = ['timestamp', 'created_by']

    def validate(self, data):
        if not data.get('po_code'):
            raise serializers.ValidationError({'po_code': 'PO code is required.'})
        if not data.get('grn_code'):
            raise serializers.ValidationError({'grn_code': 'GRN code is required.'})
        if not data.get('invoice_code'):
            raise serializers.ValidationError({'invoice_code': 'Invoice code is required.'})
        return data