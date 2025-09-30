# receipts/views.py
from rest_framework.viewsets import ModelViewSet
from rest_framework.permissions import IsAuthenticated
from rest_framework.pagination import PageNumberPagination
from django.db.models import Q
from .models import Receipt, StockReceipt, SigningReceipt
from .serializers import ReceiptSerializer, StockReceiptSerializer, SigningReceiptSerializer
from accounts.permissions import DynamicPermission
from rest_framework.decorators import action




class StandardResultsSetPagination(PageNumberPagination):
    page_size = 10
    page_size_query_param = 'page_size'
    max_page_size = 100

class ReceiptViewSet(ModelViewSet):
    queryset = Receipt.objects.all()
    serializer_class = ReceiptSerializer
    permission_classes = [IsAuthenticated, DynamicPermission]
    page_permission_name = 'receipt_archive'
    required_permissions = {
        'create': 'create_receipt',
        'update': 'update_receipt',
        'partial_update': 'update_receipt',
        'destroy': 'delete_receipt',
    }
    pagination_class = StandardResultsSetPagination

    def get_queryset(self):
        queryset = Receipt.objects.filter(created_by=self.request.user)
        search = self.request.query_params.get('search', None)
        if search:
            queryset = queryset.filter(Q(reference__icontains=search) | Q(issued_by__icontains=search))
        return queryset.order_by('-created_at')

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)

    def perform_update(self, serializer):
        serializer.save(created_by=self.request.user)

class StockReceiptViewSet(ModelViewSet):
    queryset = StockReceipt.objects.all()
    serializer_class = StockReceiptSerializer
    permission_classes = [IsAuthenticated, DynamicPermission]
    page_permission_name = 'stock_receipts'
    required_permissions = {
        'create': 'create_stock_receipt',
        'update': 'update_stock_receipt',
        'partial_update': 'update_stock_receipt',
        'destroy': 'delete_stock_receipt',
    }
    pagination_class = StandardResultsSetPagination

    def get_queryset(self):
        queryset = StockReceipt.objects.filter(created_by=self.request.user)
        search = self.request.query_params.get('search', None)
        if search:
            queryset = queryset.filter(Q(item__icontains=search) | Q(location__icontains=search))
        return queryset.order_by('-created_at')

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)

    def perform_update(self, serializer):
        serializer.save(created_by=self.request.user)

class SigningReceiptViewSet(ModelViewSet):
    queryset = SigningReceipt.objects.all()
    serializer_class = SigningReceiptSerializer
    permission_classes = [IsAuthenticated, DynamicPermission]
    page_permission_name = 'signing_receipts'
    required_permissions = {
        'create': 'create_signing_receipt',
        'update': 'update_signing_receipt',
        'partial_update': 'update_signing_receipt',
        'destroy': 'delete_signing_receipt',
    }
    pagination_class = StandardResultsSetPagination

    def get_queryset(self):
        queryset = SigningReceipt.objects.filter(created_by=self.request.user)
        search = self.request.query_params.get('search', None)
        if search:
            queryset = queryset.filter(Q(recipient__icontains=search) | Q(signed_by__icontains=search))
        return queryset.order_by('-created_at')

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)

    def perform_update(self, serializer):
        serializer.save(created_by=self.request.user)

    @action(detail=True, methods=['post'])
    def sign(self, request, pk=None):
        receipt = self.get_object()
        if receipt.status != 'pending':
            return Response({'error': 'Receipt is not pending.'}, status=status.HTTP_400_BAD_REQUEST)

        if not receipt.can_sign(request.user):
            return Response({'error': 'You are not authorized to sign receipts.'}, status=status.HTTP_403_FORBIDDEN)

        receipt.status = 'signed'
        receipt.signed_by = request.user
        receipt.signed_at = timezone.now()
        receipt.save()

        return Response({
            'status': 'signed',
            'signed_by': request.user.email,
            'signed_at': receipt.signed_at
        })

    @action(detail=True, methods=['get'])
    def download_pdf(self, request, pk=None):
        receipt = self.get_object()
        buffer = BytesIO()
        p = canvas.Canvas(buffer, pagesize=letter)
        width, height = letter

        # Title
        p.setFont("Helvetica-Bold", 16)
        p.drawString(1 * inch, height - 1 * inch, "Receipt Signing Confirmation")

        # Metadata
        y = height - 1.4 * inch
        p.setFont("Helvetica", 12)
        fields = [
            ("Receipt ID", str(receipt.id)),
            ("Recipient", receipt.recipient),
            ("Status", receipt.get_status_display()),
            ("Created By", receipt.created_by.email if receipt.created_by else "—"),
            ("Created At", receipt.created_at.strftime('%Y-%m-%d %H:%M')),
        ]
        if receipt.status == 'signed':
            fields += [
                ("Signed By", receipt.signed_by.email if receipt.signed_by else "—"),
                ("Signed At", receipt.signed_at.strftime('%Y-%m-%d %H:%M') if receipt.signed_at else "—"),
            ]
        if receipt.notes:
            fields.append(("Notes", receipt.notes))

        for label, value in fields:
            p.drawString(1 * inch, y, f"{label}:")
            p.drawString(2.5 * inch, y, str(value)[:80])  # Truncate long text
            y -= 0.25 * inch

        p.showPage()
        p.save()
        buffer.seek(0)

        response = HttpResponse(buffer.getvalue(), content_type='application/pdf')
        response['Content-Disposition'] = f'attachment; filename="SigningReceipt_{receipt.id}.pdf"'
        return response