# finance/serializers.py
from rest_framework import serializers
from .models import FinanceCategory, FinanceTransaction

class FinanceCategorySerializer(serializers.ModelSerializer):
    created_by_name = serializers.CharField(source='created_by.name', read_only=True)

    class Meta:
        model = FinanceCategory
        fields = ['id', 'name', 'description', 'created_by_name', 'created_at']

class FinanceTransactionSerializer(serializers.ModelSerializer):
    created_by_name = serializers.CharField(source='created_by.name', read_only=True)

    class Meta:
        model = FinanceTransaction
        fields = ['id', 'ref', 'type', 'amount', 'date', 'created_by_name']