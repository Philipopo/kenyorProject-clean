# receipts/serializers.py
from rest_framework import serializers
from .models import Receipt, StockReceipt, SigningReceipt
from django.contrib.auth import get_user_model

User = get_user_model()



class ReceiptSerializer(serializers.ModelSerializer):
    created_by_name = serializers.CharField(source='created_by.username', read_only=True, default='N/A')

    class Meta:
        model = Receipt
        fields = ['id', 'reference', 'issued_by', 'date', 'amount', 'created_by', 'created_at', 'created_by_name']
        read_only_fields = ['created_by', 'created_at', 'created_by_name']

class StockReceiptSerializer(serializers.ModelSerializer):
    created_by_name = serializers.CharField(source='created_by.username', read_only=True, default='N/A')

    class Meta:
        model = StockReceipt
        fields = ['nceid', 'item', 'quantity', 'location', 'date', 'notes', 'created_by', 'created_at', 'created_by_name']
        read_only_fields = ['created_by', 'created_at', 'created_by_name']

class SigningReceiptSerializer(serializers.ModelSerializer):
    created_by_email = serializers.CharField(source='created_by.email', read_only=True)
    signed_by_email = serializers.CharField(source='signed_by.email', read_only=True, allow_null=True)
    purchase_order_code = serializers.CharField(source='purchase_order.code', read_only=True, allow_null=True)

    class Meta:
        model = SigningReceipt
        fields = [
            'id', 'recipient', 'status', 'notes',
            'purchase_order', 'purchase_order_code',
            'created_by', 'created_by_email',
            'signed_by', 'signed_by_email',
            'created_at', 'signed_at'
        ]
        read_only_fields = [
            'created_by', 'signed_by', 'signed_at',
            'created_by_email', 'signed_by_email', 'purchase_order_code'
        ]