# receipts/serializers.py
from rest_framework import serializers
from .models import Receipt, StockReceipt, SigningReceipt

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
    created_by_name = serializers.CharField(source='created_by.username', read_only=True, default='N/A')

    class Meta:
        model = SigningReceipt
        fields = ['id', 'recipient', 'signed_by', 'date', 'status', 'created_by', 'created_at', 'created_by_name']
        read_only_fields = ['created_by', 'created_at', 'created_by_name']