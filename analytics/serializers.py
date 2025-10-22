from rest_framework import serializers
from .models import DwellTime, EOQReport, EOQReportV2, StockAnalytics, ReorderQueue, Supplier
from inventory.models import Item

class ItemSerializer(serializers.ModelSerializer):
    class Meta:
        model = Item
        fields = ['id', 'name', 'material_id', 'part_number', 'description']

class DwellTimeSerializer(serializers.ModelSerializer):
    class Meta:
        model = DwellTime
        fields = '__all__'
        read_only_fields = ['user', 'created_at']

    def create(self, validated_data):
        validated_data['user'] = self.context['request'].user
        return super().create(validated_data)

class EOQReportSerializer(serializers.ModelSerializer):
    class Meta:
        model = EOQReport
        fields = '__all__'
        read_only_fields = ['user', 'created_at']

    def create(self, validated_data):
        validated_data['user'] = self.context['request'].user
        return super().create(validated_data)

class EOQReportV2Serializer(serializers.ModelSerializer):
    item_name = serializers.CharField(source='item.name', read_only=True)
    part_number = serializers.CharField(source='item.part_number', read_only=True)
    user_email = serializers.EmailField(source='user.email', read_only=True)
    supplier_name = serializers.CharField(source='supplier.name', read_only=True, allow_null=True)

    class Meta:
        model = EOQReportV2
        fields = [
            'id', 'user', 'user_email', 'item', 'item_name', 'part_number',
            'demand_rate', 'ordering_cost', 'holding_cost', 'lead_time_days',  # Changed order_cost to ordering_cost
            'safety_stock', 'eoq', 'reorder_point', 'total_cost',
            'holding_cost_breakdown', 'ordering_cost_breakdown', 'inventory_turnover',
            'supplier', 'supplier_name', 'created_at', 'updated_at'
        ]
        read_only_fields = [
            'user', 'user_email', 'item_name', 'part_number', 'eoq', 'reorder_point',
            'total_cost', 'holding_cost_breakdown', 'ordering_cost_breakdown',
            'inventory_turnover', 'created_at', 'updated_at', 'supplier_name'
        ]

    def validate(self, data):
        if data.get('demand_rate', 0) <= 0:
            raise serializers.ValidationError("Demand rate must be positive.")
        if data.get('ordering_cost', 0) <= 0:  # Changed to ordering_cost
            raise serializers.ValidationError("Ordering cost must be positive.")
        if data.get('holding_cost', 0) <= 0:
            raise serializers.ValidationError("Holding cost must be positive.")
        if data.get('lead_time_days', 0) < 0:
            raise serializers.ValidationError("Lead time cannot be negative.")
        return data

    def create(self, validated_data):
        validated_data['user'] = self.context['request'].user
        return super().create(validated_data)

class StockAnalyticsSerializer(serializers.ModelSerializer):
    class Meta:
        model = StockAnalytics
        fields = ['id', 'item', 'category', 'turnover_rate', 'obsolescence_risk']
        read_only_fields = ['user', 'created_at']

    def create(self, validated_data):
        validated_data['user'] = self.context['request'].user
        return super().create(validated_data)

class ReorderQueueSerializer(serializers.ModelSerializer):
    item_name = serializers.CharField(source='item.name', read_only=True)
    user_email = serializers.EmailField(source='user.email', read_only=True)

    class Meta:
        model = ReorderQueue
        fields = ['id', 'user', 'user_email', 'item', 'item_name', 'recommended_quantity', 'status', 'created_at', 'updated_at']
        read_only_fields = ['user', 'user_email', 'item_name', 'created_at', 'updated_at']

    def create(self, validated_data):
        validated_data['user'] = self.context['request'].user
        return super().create(validated_data)

class SupplierSerializer(serializers.ModelSerializer):
    class Meta:
        model = Supplier
        fields = ['id', 'name', 'lead_time_days', 'min_order_quantity', 'discount_threshold', 'discount_percentage', 'created_at']
        read_only_fields = ['created_at']