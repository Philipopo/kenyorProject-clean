from rest_framework import generics, permissions
from .models import Alert
from .serializers import AlertSerializer
from rest_framework import generics


class AlertListCreateView(generics.ListCreateAPIView):
    serializer_class = AlertSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return Alert.objects.filter(user=self.request.user).order_by('-time')

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)
