import logging
from datetime import datetime
from decimal import Decimal
from io import BytesIO

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models  # ✅ ADDED
from django.db.models import Count, Sum, Q, Avg
from django.http import HttpResponse
from django.utils import timezone
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
)
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

# Models from other apps
from inventory.models import StockMovement, InventoryAlert, Item, StorageBin
from procurement.models import (
    PurchaseOrder, Requisition, Vendor, Receiving, POItem
)
from rentals.models import Rental, Equipment, RentalPayment

logger = logging.getLogger(__name__)


class BaseAnalyticsView(APIView):
    permission_classes = [IsAuthenticated]

    def parse_date_range(self, request):
        start_str = request.query_params.get('start_date')
        end_str = request.query_params.get('end_date')

        if not start_str or not end_str:
            raise ValidationError("Both 'start_date' and 'end_date' are required.")

        try:
            start = datetime.strptime(start_str, '%Y-%m-%d').date()
            end = datetime.strptime(end_str, '%Y-%m-%d').date()
        except ValueError:
            raise ValidationError("Invalid date format. Use YYYY-MM-DD.")

        if start > end:
            raise ValidationError("'start_date' must be <= 'end_date'.")

        start_dt = timezone.make_aware(
            timezone.datetime.combine(start, timezone.datetime.min.time())
        )
        end_dt = timezone.make_aware(
            timezone.datetime.combine(end, timezone.datetime.max.time())
        )
        return start, end, start_dt, end_dt


class InventoryAnalyticsView(BaseAnalyticsView):
    def get(self, request):
        try:
            start, end, start_dt, end_dt = self.parse_date_range(request)
        except ValidationError as e:
            return Response({'error': str(e)}, status=400)

        movements = StockMovement.objects.filter(
            timestamp__gte=start_dt,
            timestamp__lte=end_dt
        ).aggregate(
            total_in=Sum('quantity', filter=Q(movement_type='IN')),
            total_out=Sum('quantity', filter=Q(movement_type='OUT'))
        )

        alerts = InventoryAlert.objects.filter(
            created_at__gte=start_dt,
            created_at__lte=end_dt,
            is_resolved=False
        ).aggregate(
            warning_count=Count('id', filter=Q(alert_type='WARNING')),
            critical_count=Count('id', filter=Q(alert_type='CRITICAL'))
        )

        low_stock_items = Item.objects.filter(
            min_stock_level__gt=0
        ).annotate(
            total_qty=Sum('stock_records__quantity')
        ).filter(
            total_qty__lte=models.F('min_stock_level')
        ).count()

        expired_items = Item.objects.filter(
            expiry_date__lte=end,
            expiry_date__gte=start
        ).count()

        bin_usage = StorageBin.objects.filter(
            movements__timestamp__gte=start_dt,
            movements__timestamp__lte=end_dt
        ).annotate(
            movement_count=Count('movements')
        ).order_by('-movement_count')[:5].values('bin_id', 'movement_count')

        return Response({
            'date_range': {'start': start.isoformat(), 'end': end.isoformat()},
            'metrics': {
                'total_stock_in': movements['total_in'] or 0,
                'total_stock_out': movements['total_out'] or 0,
                'net_movement': (movements['total_in'] or 0) - (movements['total_out'] or 0),
                'active_warnings': alerts['warning_count'],
                'active_critical': alerts['critical_count'],
                'low_stock_items': low_stock_items,
                'expiring_items': expired_items,
            },
            'top_active_bins': list(bin_usage),
        })


class ProcurementAnalyticsView(BaseAnalyticsView):
    def get(self, request):
        try:
            start, end, start_dt, end_dt = self.parse_date_range(request)
        except ValidationError as e:
            return Response({'error': str(e)}, status=400)

        requisitions = Requisition.objects.filter(
            created_at__gte=start_dt,
            created_at__lte=end_dt
        ).aggregate(
            total=Count('id'),
            approved=Count('id', filter=Q(status='approved')),
            rejected=Count('id', filter=Q(status='rejected'))
        )

        pos = PurchaseOrder.objects.filter(
            created_at__gte=start_dt,
            created_at__lte=end_dt
        ).aggregate(
            total=Count('id'),
            approved=Count('id', filter=Q(status='approved')),
            received=Count('id', filter=Q(status='received'))
        )

        total_spend = POItem.objects.filter(
            po__created_at__gte=start_dt,
            po__created_at__lte=end_dt,
            total_price__isnull=False
        ).aggregate(
            spend=Sum('total_price')
        )['spend'] or Decimal('0.00')

        vendor_performance = Vendor.objects.filter(
            purchase_orders__created_at__gte=start_dt,
            purchase_orders__created_at__lte=end_dt
        ).annotate(
            order_count=Count('purchase_orders'),
            avg_lead_time=Avg('lead_time')
        ).order_by('-order_count')[:5].values('name', 'order_count', 'avg_lead_time')

        return Response({
            'date_range': {'start': start.isoformat(), 'end': end.isoformat()},
            'metrics': {
                'requisitions_total': requisitions['total'],
                'requisitions_approved': requisitions['approved'],
                'requisitions_rejected': requisitions['rejected'],
                'pos_total': pos['total'],
                'pos_received': pos['received'],
                'total_spend': float(total_spend),
            },
            'top_vendors': list(vendor_performance),
        })


class RentalsAnalyticsView(BaseAnalyticsView):
    def get(self, request):
        try:
            start, end, start_dt, end_dt = self.parse_date_range(request)
        except ValidationError as e:
            return Response({'error': str(e)}, status=400)

        rentals = Rental.objects.filter(
            created_at__gte=start_dt,
            created_at__lte=end_dt
        )

        # ✅ FIX: total_rental_cost is @property → sum in Python
        revenue = sum(r.total_rental_cost for r in rentals)
        revenue = Decimal(str(revenue)).quantize(Decimal('0.01'))

        overdue_rentals = rentals.filter(is_overdue=True)
        overdue_count = overdue_rentals.count()
        overdue_value = sum(r.balance_due for r in overdue_rentals)
        overdue_value = Decimal(str(overdue_value)).quantize(Decimal('0.01'))

        equipment_util = Equipment.objects.annotate(
            rental_count=Count('rentals', filter=Q(rentals__created_at__gte=start_dt, rentals__created_at__lte=end_dt))
        ).filter(rental_count__gt=0).order_by('-rental_count')[:5].values('name', 'rental_count')

        payments = RentalPayment.objects.filter(
            payment_date__gte=start,
            payment_date__lte=end,
            status='Paid'
        ).aggregate(
            total_paid=Sum('amount_paid')
        )['total_paid'] or Decimal('0.00')

        return Response({
            'date_range': {'start': start.isoformat(), 'end': end.isoformat()},
            'metrics': {
                'total_rentals': rentals.count(),
                'total_revenue': float(revenue),
                'total_payments': float(payments),
                'overdue_count': overdue_count,
                'overdue_value': float(overdue_value),
            },
            'top_equipment': list(equipment_util),
        })


class UnifiedAnalyticsView(BaseAnalyticsView):
    def get(self, request):
        try:
            start, end, start_dt, end_dt = self.parse_date_range(request)
        except ValidationError as e:
            return Response({'error': str(e)}, status=400)

        # Stock inflow
        stock_in = StockMovement.objects.filter(
            timestamp__gte=start_dt, timestamp__lte=end_dt, movement_type='IN'
        ).aggregate(total=Sum('quantity'))['total'] or 0

        # Procurement spend
        spend_qs = POItem.objects.filter(
            po__created_at__gte=start_dt,
            po__created_at__lte=end_dt,
            total_price__isnull=False
        )
        spend = spend_qs.aggregate(total=Sum('total_price'))['total'] or Decimal('0.00')

        # Rental revenue → ✅ FIX: use Python sum
        rentals = Rental.objects.filter(created_at__gte=start_dt, created_at__lte=end_dt)
        revenue = sum(r.total_rental_cost for r in rentals)
        revenue = Decimal(str(revenue)).quantize(Decimal('0.01'))

        alerts = InventoryAlert.objects.filter(
            created_at__gte=start_dt, created_at__lte=end_dt, is_resolved=False
        ).count()

        return Response({
            'date_range': {'start': start.isoformat(), 'end': end.isoformat()},
            'metrics': {
                'stock_inflow': stock_in,
                'procurement_spend': float(spend),
                'rental_revenue': float(revenue),
                'active_alerts': alerts,
                'net_operational_flow': float(revenue - spend),
            }
        })


class ExportAnalyticsPDFView(BaseAnalyticsView):
    def get(self, request):
        tab = request.query_params.get('tab', 'unified')
        try:
            start, end, start_dt, end_dt = self.parse_date_range(request)
        except ValidationError as e:
            return Response({'error': str(e)}, status=400)

        # Fetch data
        if tab == 'inventory':
            data = self.get_inventory_data(start, end, start_dt, end_dt)
            title = "Inventory Analytics Report"
        elif tab == 'procurement':
            data = self.get_procurement_data(start, end, start_dt, end_dt)
            title = "Procurement Analytics Report"
        elif tab == 'rentals':
            data = self.get_rentals_data(start, end, start_dt, end_dt)
            title = "Rentals Analytics Report"
        else:
            data = self.get_unified_data(start, end, start_dt, end_dt)
            title = "Unified Operations Analytics"

        # Generate PDF
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
            'CustomTitle',
            parent=styles['Heading1'],
            fontSize=16,
            alignment=1,
            spaceAfter=12,
            textColor=colors.HexColor("#333333")
        )

        elements.append(Paragraph(title, title_style))
        elements.append(Paragraph(f"Period: {start} to {end}", styles['Normal']))
        elements.append(Spacer(1, 12))

        # Metrics Table
        metrics = data.get('metrics', {})
        if metrics:
            elements.append(Paragraph("<b>Key Metrics</b>", styles['Heading2']))
            metric_rows = [["Metric", "Value"]]
            for key, value in metrics.items():
                label = key.replace('_', ' ').title()
                metric_rows.append([label, str(value)])
            metric_table = Table(metric_rows, colWidths=[3 * inch, 2 * inch])
            metric_table.setStyle(TableStyle([
                ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
                ('BACKGROUND', (0, 0), (0, -1), colors.HexColor("#f0f0f0")),
                ('ALIGN', (1, 1), (-1, -1), 'RIGHT'),
            ]))
            elements.append(metric_table)
            elements.append(Spacer(1, 12))

        # Top Items Table (if exists)
        top_key = None
        if tab == 'inventory':
            top_key = 'top_active_bins'
            top_title = "Top 5 Most Active Bins"
            col1, col2 = "Bin ID", "Movements"
        elif tab == 'procurement':
            top_key = 'top_vendors'
            top_title = "Top 5 Vendors by Order Volume"
            col1, col2 = "Vendor", "Orders"
        elif tab == 'rentals':
            top_key = 'top_equipment'
            top_title = "Top 5 Rented Equipment"
            col1, col2 = "Equipment", "Rentals"

        if top_key and data.get(top_key):
            elements.append(Paragraph(f"<b>{top_title}</b>", styles['Heading2']))
            top_rows = [[col1, col2]]
            for item in data[top_key]:
                if tab == 'inventory':
                    top_rows.append([item['bin_id'], str(item['movement_count'])])
                elif tab == 'procurement':
                    top_rows.append([item['name'], str(item['order_count'])])
                elif tab == 'rentals':
                    top_rows.append([item['name'], str(item['rental_count'])])
            top_table = Table(top_rows, colWidths=[3 * inch, 2 * inch])
            top_table.setStyle(TableStyle([
                ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
                ('BACKGROUND', (0, 0), (0, -1), colors.HexColor("#f9f9f9")),
            ]))
            elements.append(top_table)

        doc.build(elements)
        buffer.seek(0)

        filename = f"Analytics_{tab}_{start}_to_{end}.pdf"
        response = HttpResponse(buffer.getvalue(), content_type='application/pdf')
        response['Content-Disposition'] = f'attachment; filename="{filename}"'
        return response

    def get_inventory_data(self, start, end, start_dt, end_dt):
        view = InventoryAnalyticsView()
        request = type('Request', (), {'query_params': {'start_date': str(start), 'end_date': str(end)}})()
        response = view.get(request)
        return response.data

    def get_procurement_data(self, start, end, start_dt, end_dt):
        view = ProcurementAnalyticsView()
        request = type('Request', (), {'query_params': {'start_date': str(start), 'end_date': str(end)}})()
        response = view.get(request)
        return response.data

    def get_rentals_data(self, start, end, start_dt, end_dt):
        view = RentalsAnalyticsView()
        request = type('Request', (), {'query_params': {'start_date': str(start), 'end_date': str(end)}})()
        response = view.get(request)
        return response.data

    def get_unified_data(self, start, end, start_dt, end_dt):
        view = UnifiedAnalyticsView()
        request = type('Request', (), {'query_params': {'start_date': str(start), 'end_date': str(end)}})()
        response = view.get(request)
        return response.data