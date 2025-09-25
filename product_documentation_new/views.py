from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.response import Response
from .models import ProductInflow, ProductOutflow
from .serializers import ProductInflowSerializer, ProductOutflowSerializer, ItemSerializer
from inventory.models import Item

class ProductInflowViewSet(viewsets.ModelViewSet):
    queryset = ProductInflow.objects.all()
    serializer_class = ProductInflowSerializer

    @action(detail=False, methods=['get'])
    def items(self, request):
        items = Item.objects.order_by('-created_at')[:10]
        serializer = ItemSerializer(items, many=True)
        return Response(serializer.data)

class ProductOutflowViewSet(viewsets.ModelViewSet):
    queryset = ProductOutflow.objects.all()
    serializer_class = ProductOutflowSerializer