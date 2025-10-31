from rest_framework import serializers
from decimal import Decimal

class MetricSerializer(serializers.Serializer):
    """Generic serializer for key-value metric pairs."""
    name = serializers.CharField()
    value = serializers.FloatField()


class TopItemSerializer(serializers.Serializer):
    """Generic serializer for top-N ranked items (bins, vendors, equipment, etc.)."""
    name = serializers.CharField()
    value = serializers.IntegerField()


class InventoryAnalyticsSerializer(serializers.Serializer):
    date_range = serializers.DictField(child=serializers.CharField())
    metrics = serializers.DictField(child=serializers.FloatField())
    top_active_bins = serializers.ListField(
        child=serializers.DictField()
    )


class ProcurementAnalyticsSerializer(serializers.Serializer):
    date_range = serializers.DictField(child=serializers.CharField())
    metrics = serializers.DictField(child=serializers.FloatField())
    top_vendors = serializers.ListField(
        child=serializers.DictField()
    )


class RentalsAnalyticsSerializer(serializers.Serializer):
    date_range = serializers.DictField(child=serializers.CharField())
    metrics = serializers.DictField(child=serializers.FloatField())
    top_equipment = serializers.ListField(
        child=serializers.DictField()
    )


class UnifiedAnalyticsSerializer(serializers.Serializer):
    date_range = serializers.DictField(child=serializers.CharField())
    metrics = serializers.DictField(child=serializers.FloatField())