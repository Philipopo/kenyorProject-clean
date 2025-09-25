from rest_framework import serializers
from .models import DwellTime, EOQReport, EOQReportV2, StockAnalytics
from inventory.models import Item

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

    class Meta:
        model = EOQReportV2
        fields = [
            'id', 'user', 'user_email', 'item', 'item_name', 'part_number',
            'demand_rate', 'order_cost', 'holding_cost', 'lead_time_days',
            'safety_stock', 'eoq', 'reorder_point', 'total_cost',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['user', 'user_email', 'item_name', 'part_number', 'eoq', 'reorder_point', 'total_cost', 'created_at', 'updated_at']

    def validate(self, data):
        if data.get('demand_rate', 0) <= 0:
            raise serializers.ValidationError("Demand rate must be positive.")
        if data.get('order_cost', 0) <= 0:
            raise serializers.ValidationError("Order cost must be positive.")
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