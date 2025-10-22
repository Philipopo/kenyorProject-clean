# rentals/views.py
import logging
from io import BytesIO
from datetime import datetime
from django.http import HttpResponse
from django.utils import timezone
from django.db.models import Q
from django.conf import settings
from rest_framework.viewsets import ModelViewSet
from rest_framework.permissions import IsAuthenticated
from rest_framework.pagination import PageNumberPagination
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.views import APIView
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from decimal import Decimal
from .models import Equipment, Rental, RentalPayment, Branch, Reservation, Notification
from .serializers import (
    EquipmentSerializer, RentalSerializer, RentalPaymentSerializer,
    BranchSerializer, ReservationSerializer, NotificationSerializer
)

logger = logging.getLogger(__name__)

class StandardResultsSetPagination(PageNumberPagination):
    page_size = 10
    page_size_query_param = 'page_size'
    max_page_size = 100

class BranchViewSet(ModelViewSet):
    queryset = Branch.objects.all().order_by('name')
    serializer_class = BranchSerializer
    permission_classes = [IsAuthenticated]
    pagination_class = StandardResultsSetPagination

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)

class EquipmentViewSet(ModelViewSet):
    queryset = Equipment.objects.select_related('branch', 'created_by').all().order_by('-created_at')
    serializer_class = EquipmentSerializer
    permission_classes = [IsAuthenticated]
    pagination_class = StandardResultsSetPagination

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)

class RentalViewSet(ModelViewSet):
    queryset = Rental.objects.select_related(
        'renter', 'equipment', 'branch', 'created_by'
    ).prefetch_related('payments').all().order_by('-created_at')
    serializer_class = RentalSerializer
    permission_classes = [IsAuthenticated]
    pagination_class = StandardResultsSetPagination

    def get_queryset(self):
        user = self.request.user
        return self.queryset.filter(
            Q(renter=user) | Q(created_by=user)
        )

    @action(detail=True, methods=['post'])
    def extend_rental(self, request, pk=None):
        rental = self.get_object()
        if rental.is_open_ended:
            return Response({'error': 'Cannot extend open-ended rental.'}, status=400)
        if rental.returned:
            return Response({'error': 'Cannot extend a returned rental.'}, status=400)
        new_due_date_str = request.data.get('new_due_date')
        if not new_due_date_str:
            return Response({'error': 'New due date is required.'}, status=400)
        try:
            new_due_date = datetime.strptime(new_due_date_str, '%Y-%m-%d').date()
        except ValueError:
            return Response({'error': 'Invalid date format. Use YYYY-MM-DD.'}, status=400)
        if new_due_date <= rental.start_date:
            return Response({'error': 'New due date must be after start date.'}, status=400)
        if rental.effective_due_date and new_due_date <= rental.effective_due_date:
            return Response({'error': 'New due date must be after current due date.'}, status=400)
        rental.extended_to = new_due_date
        rental.save(update_fields=['extended_to'])
        return Response({
            'message': 'Rental extended successfully.',
            'extended_to': new_due_date.isoformat()
        })

    @action(detail=True, methods=['post'])
    def mark_returned(self, request, pk=None):
        rental = self.get_object()
        if rental.returned:
            return Response({'error': 'Rental is already returned.'}, status=400)
        rental.returned = True
        rental.returned_at = timezone.now()
        rental.save()
        return Response({'message': 'Rental marked as returned.'})

    @action(detail=False, methods=['post'])
    def bulk_return(self, request):
        rental_ids = request.data.get('ids', [])
        if not isinstance(rental_ids, list):
            return Response({'error': 'Invalid ids payload. Must be a list of ids.'}, status=400)
        updated = 0
        for rental_id in rental_ids:
            try:
                rental = Rental.objects.get(id=rental_id, returned=False)
                rental.returned = True
                rental.returned_at = timezone.now()
                rental.save()
                updated += 1
            except Rental.DoesNotExist:
                continue
        return Response({'message': f'{updated} rentals marked as returned.'})

    @action(detail=False, methods=['post'])
    def bulk_delete(self, request):
        rental_ids = request.data.get('ids', [])
        if not isinstance(rental_ids, list):
            return Response({'error': 'Invalid ids payload. Must be a list of ids.'}, status=400)
        deleted = 0
        for rental_id in rental_ids:
            try:
                rental = Rental.objects.get(id=rental_id)
                if not rental.returned:
                    continue
                rental.delete()
                deleted += 1
            except Rental.DoesNotExist:
                continue
        return Response({'message': f'{deleted} rentals deleted.'})

    @action(detail=True, methods=['get'])
    def receipt_pdf(self, request, pk=None):
        rental = self.get_object()
        buffer = BytesIO()
        doc = SimpleDocTemplate(
            buffer,
            pagesize=letter,
            topMargin=0.75 * inch,
            bottomMargin=0.75 * inch,
            leftMargin=0.75 * inch,
            rightMargin=0.75 * inch
        )
        elements = []
        styles = getSampleStyleSheet()
        title_style = ParagraphStyle(
            'ReceiptTitle', parent=styles['Heading1'],
            fontSize=16, alignment=1, spaceAfter=8, leading=20,
            textColor=colors.HexColor("#333333")
        )
        section_heading = ParagraphStyle(
            'SectionHeading', parent=styles['Heading3'],
            fontSize=10.5, spaceBefore=6, spaceAfter=6,
            textColor=colors.HexColor("#2b2b2b"), leading=13
        )
        small_info = ParagraphStyle(
            'SmallInfo', parent=styles['Normal'],
            fontSize=9, leading=12, textColor=colors.black
        )

        # Header
        try:
            if getattr(settings, 'COMPANY_LOGO_PATH', None):
                logo_img = Image(settings.COMPANY_LOGO_PATH, width=1.0 * inch, height=0.6 * inch)
                header_table = Table([[  
                    logo_img,
                    Paragraph(f"<b>{getattr(settings, 'COMPANY_NAME', '')}</b><br/><span>{getattr(settings, 'COMPANY_TAGLINE', '')}</span>", styles['Title']),
                    Paragraph(
                        f"<b>Receipt No.</b><br/>{rental.code}<br/><br/>"
                        f"<b>Date</b><br/>{rental.created_at.strftime('%d/%m/%Y %H:%M')}",
                        small_info
                    )
                ]], colWidths=[1.0 * inch, 4.3 * inch, 2.2 * inch])
                header_table.setStyle(TableStyle([
                    ('BACKGROUND', (0, 0), (0, 0), colors.HexColor("#B2B2B2")),
                    ('BACKGROUND', (1, 0), (1, 0), colors.white),
                    ('BACKGROUND', (2, 0), (2, 0), colors.HexColor("#F6F6F6")),
                    ('TEXTCOLOR', (0, 0), (-1, -1), colors.black),
                    ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                    ('ALIGN', (2, 0), (2, 0), 'RIGHT'),
                    ('LEFTPADDING', (0, 0), (-1, -1), 8),
                    ('RIGHTPADDING', (0, 0), (-1, -1), 8),
                    ('TOPPADDING', (0, 0), (-1, -1), 10),
                    ('BOTTOMPADDING', (0, 0), (-1, -1), 10),
                    ('BOX', (0, 0), (-1, -1), 0.5, colors.HexColor("#D0D0D0")),
                ]))
                elements.append(header_table)
                elements.append(Spacer(1, 12))
            else:
                raise Exception("No company logo configured")
        except Exception as e:
            logger.warning(f"Logo load failed or no logo configured: {e}")
            header_table = Table([[  
                Paragraph(f"<b>{getattr(settings, 'COMPANY_NAME', '')}</b>", styles['Title']),
                Paragraph(
                    f"<b>Receipt No.</b><br/>{rental.code}<br/><br/>"
                    f"<b>Date</b><br/>{rental.created_at.strftime('%d/%m/%Y %H:%M')}",
                    small_info
                )
            ]], colWidths=[5.3 * inch, 2.2 * inch])
            header_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (0, 0), colors.HexColor("#B2B2B2")),
                ('BACKGROUND', (1, 0), (1, 0), colors.HexColor("#F6F6F6")),
                ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                ('ALIGN', (1, 0), (1, 0), 'RIGHT'),
                ('BOX', (0, 0), (-1, -1), 0.5, colors.HexColor("#D0D0D0")),
            ]))
            elements.append(header_table)
            elements.append(Spacer(1, 12))

        # Title
        elements.append(Paragraph("EQUIPMENT RENTAL RECEIPT", title_style))
        elements.append(Spacer(1, 8))

        # Rental Info
        elements.append(Paragraph("<b>RENTAL DETAILS</b>", section_heading))
        rental_data = [
            ["Rental Code", rental.code],
            ["Renter", rental.renter.email],
            ["Equipment", rental.equipment.name if rental.equipment else "—"],
            ["Quantity", str(rental.quantity)],
            ["Start Date", rental.start_date.strftime('%d/%m/%Y') if rental.start_date else "—"],
            ["Due Date", rental.effective_due_date.strftime('%d/%m/%Y') if rental.effective_due_date else "Open-ended"],
            ["Status", "Returned" if rental.returned else "Active"],
        ]
        rental_table = Table(rental_data, colWidths=[2.0 * inch, 4.1 * inch])
        rental_table.setStyle(TableStyle([
            ('GRID', (0, 0), (-1, -1), 0.35, colors.HexColor("#E0E0E0")),
            ('BACKGROUND', (0, 0), (0, -1), colors.HexColor("#FAFAFA")),
            ('LEFTPADDING', (0, 0), (-1, -1), 8),
            ('TOPPADDING', (0, 0), (-1, -1), 6),
        ]))
        elements.append(rental_table)
        elements.append(Spacer(1, 12))

        # Financial Summary
        elements.append(Paragraph("<b>FINANCIAL SUMMARY</b>", section_heading))
        fin_data = [
            ["Rental Rate", f"{rental.rental_rate or 0} {rental.currency}/day"],
            ["Duration (days)", str(rental.duration_days)],
            ["Total Incurred", f"{rental.total_rental_cost} {rental.currency}"],
            ["Total Paid", f"{rental.total_paid} {rental.currency}"],
            ["Balance Due", f"{rental.balance_due} {rental.currency}"],
        ]
        fin_table = Table(fin_data, colWidths=[2.0 * inch, 4.1 * inch])
        fin_table.setStyle(TableStyle([
            ('GRID', (0, 0), (-1, -1), 0.35, colors.HexColor("#E0E0E0")),
            ('BACKGROUND', (0, 0), (0, -1), colors.HexColor("#FAFAFA")),
            ('LEFTPADDING', (0, 0), (-1, -1), 8),
            ('TOPPADDING', (0, 0), (-1, -1), 6),
        ]))
        elements.append(fin_table)
        elements.append(Spacer(1, 12))

        # Payments
        elements.append(Paragraph("<b>PAYMENTS</b>", section_heading))
        payment_rows = [["Date", "Amount", "In Words", "Status"]]
        for p in rental.payments.all():
            payment_rows.append([
                p.payment_date.strftime('%d/%m/%Y'),
                f"{p.amount_paid} {rental.currency}",
                p.amount_in_words or "—",
                p.status
            ])
        if len(payment_rows) == 1:
            payment_rows.append(["—", "—", "—", "No payments"])
        pay_table = Table(payment_rows, colWidths=[1.2 * inch, 1.5 * inch, 2.4 * inch, 1.0 * inch])
        pay_table.setStyle(TableStyle([
            ('GRID', (0, 0), (-1, -1), 0.35, colors.HexColor("#E0E0E0")),
            ('BACKGROUND', (0, 0), (0, 0), colors.HexColor("#E0E0E0")),
            ('LEFTPADDING', (0, 0), (-1, -1), 6),
            ('TOPPADDING', (0, 0), (-1, -1), 6),
        ]))
        elements.append(pay_table)
        elements.append(Spacer(1, 18))

        # Footer
        footer_table = Table([[  
            Paragraph("<i>This rental receipt is auto-generated.</i>", styles['Italic']),
            Paragraph(f"{getattr(settings, 'COMPANY_NAME', '')}", small_info)
        ]], colWidths=[4.6 * inch, 2.0 * inch])
        footer_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor("#333333")),
            ('TEXTCOLOR', (0, 0), (-1, -1), colors.whitesmoke),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('ALIGN', (1, 0), (1, 0), 'RIGHT'),
        ]))
        elements.append(footer_table)

        doc.build(elements)
        buffer.seek(0)
        filename = f"Rental_{rental.code}_receipt.pdf"
        response = HttpResponse(buffer.getvalue(), content_type='application/pdf')
        response['Content-Disposition'] = f'attachment; filename="{filename}"'
        return response

class ReservationViewSet(ModelViewSet):
    queryset = Reservation.objects.select_related('equipment', 'reserved_by').all().order_by('-created_at')
    serializer_class = ReservationSerializer
    permission_classes = [IsAuthenticated]
    pagination_class = StandardResultsSetPagination

    def get_queryset(self):
        user = self.request.user
        return self.queryset.filter(reserved_by=user)

    def perform_create(self, serializer):
        serializer.save(reserved_by=self.request.user)

class RentalPaymentViewSet(ModelViewSet):
    queryset = RentalPayment.objects.select_related('rental__renter', 'rental__equipment').all().order_by('-created_at')
    serializer_class = RentalPaymentSerializer
    permission_classes = [IsAuthenticated]
    pagination_class = StandardResultsSetPagination

    def get_queryset(self):
        user = self.request.user
        return self.queryset.filter(
            Q(rental__renter=user) | Q(rental__created_by=user) | Q(created_by=user)
        )

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)

class EquipmentReportPDFView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        equipment_list = Equipment.objects.select_related('branch').all().order_by('name')
        buffer = BytesIO()
        doc = SimpleDocTemplate(
            buffer,
            pagesize=letter,
            topMargin=0.75 * inch,
            bottomMargin=0.75 * inch,
            leftMargin=0.75 * inch,
            rightMargin=0.75 * inch
        )
        elements = []
        styles = getSampleStyleSheet()
        title_style = ParagraphStyle(
            'ReportTitle', parent=styles['Heading1'],
            fontSize=16, alignment=1, spaceAfter=12, leading=20,
            textColor=colors.HexColor("#333333")
        )
        section_heading = ParagraphStyle(
            'SectionHeading', parent=styles['Heading3'],
            fontSize=11, spaceBefore=8, spaceAfter=6,
            textColor=colors.HexColor("#2b2b2b")
        )
        normal = styles['Normal']
        elements.append(Paragraph("EQUIPMENT INVENTORY REPORT", title_style))
        elements.append(Paragraph(f"Generated on: {timezone.now().strftime('%d/%m/%Y %H:%M')}", normal))
        elements.append(Spacer(1, 12))
        table_data = [
            ["#", "Name", "Category", "Branch", "Total Qty", "Available Qty", "Status", "Expiry"]
        ]
        for idx, eq in enumerate(equipment_list, 1):
            status = "Available" if eq.available_quantity == eq.total_quantity else "Partially Available" if eq.available_quantity > 0 else "Unavailable"
            expiry = eq.expiry_date.strftime('%d/%m/%Y') if eq.expiry_date else "—"
            if eq.expiry_date and eq.expiry_date < timezone.now().date():
                expiry = f"EXPIRED ({expiry})"
            table_data.append([
                str(idx),
                eq.name,
                eq.category,
                eq.branch.name if eq.branch else "—",
                str(eq.total_quantity),
                str(eq.available_quantity),
                status,
                expiry
            ])
        col_widths = [0.4 * inch, 1.5 * inch, 1.0 * inch, 1.2 * inch, 0.8 * inch, 0.9 * inch, 1.0 * inch, 1.2 * inch]
        table = Table(table_data, colWidths=col_widths)
        table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor("#4CAF50")),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 9),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor("#CCCCCC")),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ]))
        elements.append(table)
        doc.build(elements)
        buffer.seek(0)
        response = HttpResponse(buffer.getvalue(), content_type='application/pdf')
        response['Content-Disposition'] = 'attachment; filename="equipment_inventory_report.pdf"'
        return response

class NotificationViewSet(ModelViewSet):
    serializer_class = NotificationSerializer
    permission_classes = [IsAuthenticated]
    pagination_class = StandardResultsSetPagination
    queryset = Notification.objects.all()

    def get_queryset(self):
        return self.queryset.filter(user=self.request.user)

    @action(detail=False, methods=['post'])
    def mark_all_as_read(self, request):
        self.get_queryset().update(is_read=True)
        return Response({'status': 'success'})

    @action(detail=True, methods=['post'])
    def mark_as_read(self, request, pk=None):
        notification = self.get_object()
        notification.is_read = True
        notification.save()
        return Response({'status': 'success'})
