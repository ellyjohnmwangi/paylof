from decimal import Decimal
from calendar import monthrange
from datetime import timedelta

from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from django.db.models import Count, F, Sum
from django.db.models.functions import ExtractHour, TruncDate
from django.db import transaction
from django.utils import timezone
from django.utils.dateparse import parse_date
from payments.reporting import active_report_subscription, report_subscription_required_response
from payments.serializers import MpesaPaymentSerializer
from payments.services import MpesaConfigurationError, MpesaRequestError, start_stk_push_for_sale
from users.permissions import CanSell, CanViewReports, HasBusinessProfile
from .models import Sale, SaleItem
from .serializers import SaleSerializer, SaleCreateSerializer
from products.models import Expense, Product, StockMovement

class SaleViewSet(viewsets.ModelViewSet):
    http_method_names = ['get', 'post', 'head', 'options']
    serializer_class = SaleSerializer

    def get_queryset(self):
        business = self.request.user.profile.business
        return Sale.objects.select_related('user').prefetch_related('items__product').filter(
            business=business
        ).all()

    def get_permissions(self):
        if self.action in ['analytics', 'reports']:
            permission_classes = [IsAuthenticated, HasBusinessProfile, CanViewReports]
        elif self.action in ['create_sale', 'create']:
            permission_classes = [IsAuthenticated, HasBusinessProfile, CanSell]
        else:
            permission_classes = [IsAuthenticated, HasBusinessProfile]
        return [permission() for permission in permission_classes]

    def create(self, request, *args, **kwargs):
        return Response(
            {'detail': 'Use /api/sales/create_sale/ to process a sale.'},
            status=status.HTTP_405_METHOD_NOT_ALLOWED,
        )

    @action(detail=False, methods=['post'])
    def create_sale(self, request):
        input_serializer = SaleCreateSerializer(data=request.data)
        input_serializer.is_valid(raise_exception=True)
        data = input_serializer.validated_data

        existing_sale = self._get_existing_offline_sale(data.get('offline_reference'))
        if existing_sale:
            serializer = self.get_serializer(existing_sale)
            return Response(serializer.data, status=status.HTTP_200_OK)

        user = request.user

        sale, error_response = self._create_sale_record(user, data)
        if error_response:
            return error_response

        serializer = self.get_serializer(sale)
        response_data = dict(serializer.data)

        if sale.payment_method == 'mpesa':
            try:
                payment, mpesa_response = start_stk_push_for_sale(sale)
            except ValueError as exc:
                sale.refresh_from_db()
                response_data = dict(self.get_serializer(sale).data)
                return Response(
                    {'detail': str(exc), 'sale': response_data},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            except MpesaConfigurationError as exc:
                sale.refresh_from_db()
                response_data = dict(self.get_serializer(sale).data)
                return Response(
                    {'detail': str(exc), 'sale': response_data},
                    status=status.HTTP_503_SERVICE_UNAVAILABLE,
                )
            except MpesaRequestError as exc:
                sale.refresh_from_db()
                response_data = dict(self.get_serializer(sale).data)
                return Response(
                    {'detail': str(exc), 'sale': response_data},
                    status=status.HTTP_502_BAD_GATEWAY,
                )

            response_data['mpesa_payment'] = MpesaPaymentSerializer(payment).data
            response_data['payment_id'] = payment.id
            response_data['mpesa_response'] = mpesa_response

        return Response(response_data, status=status.HTTP_201_CREATED)

    @action(detail=False, methods=['get'])
    def analytics(self, request):
        if not active_report_subscription(request.user.profile.business):
            return report_subscription_required_response(request)

        today = timezone.localdate()
        paid_sales = self.get_queryset().filter(payment_status=Sale.PAYMENT_STATUS_PAID)
        today_sales = paid_sales.filter(created_at__date=today)

        totals = paid_sales.aggregate(
            subtotal=Sum('subtotal_amount'),
            transaction_fees=Sum('transaction_fee'),
            total_collected=Sum('total_amount'),
        )
        today_totals = today_sales.aggregate(
            subtotal=Sum('subtotal_amount'),
            transaction_fees=Sum('transaction_fee'),
            total_collected=Sum('total_amount'),
        )
        top_products = SaleItem.objects.filter(
            sale__business=request.user.profile.business,
            sale__payment_status=Sale.PAYMENT_STATUS_PAID,
        ).values('product__name').annotate(
            quantity_sold=Sum('quantity'),
            revenue=Sum('price'),
            gross_profit=Sum('gross_profit'),
        ).order_by('-quantity_sold')[:5]
        low_stock_count = Product.objects.filter(
            business=request.user.profile.business,
            stock__lte=F('low_stock_threshold'),
        ).count()

        return Response({
            'sales_count': paid_sales.count(),
            'subtotal': totals['subtotal'] or Decimal('0.00'),
            'transaction_fees': totals['transaction_fees'] or Decimal('0.00'),
            'total_collected': totals['total_collected'] or Decimal('0.00'),
            'gross_profit': SaleItem.objects.filter(sale__in=paid_sales).aggregate(
                total=Sum('gross_profit')
            )['total'] or Decimal('0.00'),
            'today': {
                'sales_count': today_sales.count(),
                'subtotal': today_totals['subtotal'] or Decimal('0.00'),
                'transaction_fees': today_totals['transaction_fees'] or Decimal('0.00'),
                'total_collected': today_totals['total_collected'] or Decimal('0.00'),
            },
            'low_stock_count': low_stock_count,
            'top_products': list(top_products),
        })

    @action(detail=False, methods=['get'])
    def reports(self, request):
        if not active_report_subscription(request.user.profile.business):
            return report_subscription_required_response(request)

        report_type = request.query_params.get('type', 'daily')
        start_date, end_date = self._report_date_range(request, report_type)
        sales = self.get_queryset().filter(
            payment_status=Sale.PAYMENT_STATUS_PAID,
            created_at__date__gte=start_date,
            created_at__date__lte=end_date,
        )
        if report_type in ['cash_payments', 'mpesa_payments']:
            payment_method = 'cash' if report_type == 'cash_payments' else 'mpesa'
            sales = sales.filter(payment_method=payment_method)

        total_sales_amount = sales.aggregate(total=Sum('total_amount'))['total'] or Decimal('0.00')
        number_of_transactions = sales.count()
        average_transaction_value = (
            total_sales_amount / number_of_transactions
            if number_of_transactions
            else Decimal('0.00')
        )
        sale_items = SaleItem.objects.filter(sale__in=sales)
        gross_profit = sale_items.aggregate(total=Sum('gross_profit'))['total'] or Decimal('0.00')
        total_expenses = Expense.objects.filter(
            business=request.user.profile.business,
            expense_date__gte=start_date,
            expense_date__lte=end_date,
        ).aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
        net_profit = gross_profit - total_expenses
        product_rows = sale_items.values('product__name').annotate(
            quantity_sold=Sum('quantity'),
            revenue=Sum('price'),
            gross_profit=Sum('gross_profit'),
        )
        payment_rows = sales.values('payment_method').annotate(
            total_sales_amount=Sum('total_amount'),
            number_of_transactions=Count('id'),
        ).order_by('payment_method')
        best_selling_hours = list(sales.annotate(hour=ExtractHour('created_at')).values('hour').annotate(
            total_sales_amount=Sum('total_amount'),
            number_of_transactions=Count('id'),
        ).order_by('-number_of_transactions', '-total_sales_amount')[:5])
        days_in_range = max((end_date - start_date).days + 1, 1)
        forecast_next_7_days = (total_sales_amount / days_in_range) * 7
        stock_value = sum(
            (product.stock_value for product in Product.objects.filter(business=request.user.profile.business)),
            start=Decimal('0.00'),
        )
        sold_product_ids = sale_items.values('product_id')
        dead_stock = Product.objects.filter(
            business=request.user.profile.business,
            stock__gt=0,
        ).exclude(id__in=sold_product_ids).order_by('name')[:5]

        return Response({
            'report_type': report_type,
            'start_date': start_date,
            'end_date': end_date,
            'total_sales_amount': total_sales_amount,
            'number_of_transactions': number_of_transactions,
            'average_transaction_value': average_transaction_value,
            'gross_profit': gross_profit,
            'total_expenses': total_expenses,
            'net_profit': net_profit,
            'stock_value': stock_value,
            'best_selling_hours': best_selling_hours,
            'sales_forecast_next_7_days': forecast_next_7_days,
            'dead_stock': [
                {
                    'product__name': product.name,
                    'quantity_available': product.stock,
                    'stock_value': product.stock_value,
                }
                for product in dead_stock
            ],
            'best_selling_products': list(product_rows.order_by('-quantity_sold', '-revenue')[:5]),
            'slow_selling_products': list(product_rows.order_by('quantity_sold', 'revenue')[:5]),
            'cash_vs_mpesa_sales': self._payment_breakdown(payment_rows),
            'breakdown': self._report_breakdown(report_type, sales, sale_items),
        })

    @action(detail=True, methods=['get'])
    def receipt(self, request, pk=None):
        sale = self.get_queryset().get(pk=pk)
        return Response({
            'business_name': sale.business.name if sale.business else '',
            'sale_id': sale.id,
            'cashier_name': sale.user.username,
            'payment_method': sale.get_payment_method_display(),
            'payment_status': sale.get_payment_status_display(),
            'transaction_fee': sale.transaction_fee,
            'subtotal_amount': sale.subtotal_amount,
            'total_amount': sale.total_amount,
            'customer_phone': sale.customer_phone,
            'mpesa_receipt_number': sale.mpesa_receipt_number,
            'created_at': sale.created_at,
            'items': [
                {
                    'product_name': item.product.name,
                    'quantity': item.quantity,
                    'line_total': item.price,
                }
                for item in sale.items.select_related('product')
            ],
        })

    def _get_existing_offline_sale(self, offline_reference):
        if not offline_reference:
            return None
        return self.get_queryset().filter(offline_reference=offline_reference).first()

    def _create_sale_record(self, user, data):
        items_data = data['items']
        payment_method = data['payment_method']
        offline_reference = data.get('offline_reference')
        customer_phone = data.get('customer_phone', '')
        business = user.profile.business

        product_ids = [item['product_id'] for item in items_data]

        with transaction.atomic():
            products = Product.objects.select_for_update().filter(
                business=business
            ).in_bulk(product_ids)
            missing_ids = sorted(set(product_ids) - set(products.keys()))
            if missing_ids:
                return None, Response(
                    {'detail': f"Product IDs not found: {', '.join(map(str, missing_ids))}"},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            subtotal_amount = Decimal('0.00')
            prepared_items = []
            stock_errors = []

            for item in items_data:
                product = products[item['product_id']]
                quantity = item['quantity']

                if product.stock < quantity:
                    stock_errors.append(
                        f"{product.name} has {product.stock} in stock; requested {quantity}."
                    )
                    continue

                line_total = product.price * quantity
                subtotal_amount += line_total
                unit_cost = product.cost_price
                gross_profit = line_total - (unit_cost * quantity)
                prepared_items.append((product, quantity, line_total, unit_cost, gross_profit))

            if stock_errors:
                return None, Response(
                    {'detail': stock_errors},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            transaction_fee = Sale.calculate_transaction_fee(subtotal_amount)
            total_amount = subtotal_amount + transaction_fee

            sale = Sale.objects.create(
                business=business,
                user=user,
                subtotal_amount=subtotal_amount,
                transaction_fee=transaction_fee,
                total_amount=total_amount,
                payment_method=payment_method,
                payment_status=(
                    Sale.PAYMENT_STATUS_PENDING
                    if payment_method == 'mpesa'
                    else Sale.PAYMENT_STATUS_PAID
                ),
                customer_phone=customer_phone,
                mpesa_receipt_number='',
                offline_reference=offline_reference,
            )

            for product, quantity, line_total, unit_cost, gross_profit in prepared_items:
                SaleItem.objects.create(
                    sale=sale,
                    product=product,
                    quantity=quantity,
                    price=line_total,
                    unit_cost=unit_cost,
                    gross_profit=gross_profit,
                )

                product.stock -= quantity
                product.save(update_fields=['stock', 'updated_at'])
                StockMovement.objects.create(
                    business=business,
                    product=product,
                    user=user,
                    movement_type=StockMovement.TYPE_SOLD,
                    quantity=quantity,
                    quantity_change=-quantity,
                    note=f'Sale #{sale.id}',
                )

        return sale, None

    def _report_date_range(self, request, report_type):
        today = timezone.localdate()
        start_date = parse_date(request.query_params.get('start_date') or '')
        end_date = parse_date(request.query_params.get('end_date') or '')

        if not start_date or not end_date:
            if report_type == 'weekly':
                start_date = today - timedelta(days=today.weekday())
                end_date = start_date + timedelta(days=6)
            elif report_type == 'monthly':
                start_date = today.replace(day=1)
                end_date = today.replace(day=monthrange(today.year, today.month)[1])
            elif report_type in ['date_range', 'payment_trends']:
                start_date = start_date or today.replace(day=1)
                end_date = end_date or today
            else:
                start_date = start_date or today
                end_date = end_date or today

        if end_date < start_date:
            start_date, end_date = end_date, start_date
        return start_date, end_date

    def _payment_breakdown(self, payment_rows):
        breakdown = {
            'cash': {'total_sales_amount': Decimal('0.00'), 'number_of_transactions': 0},
            'mpesa': {'total_sales_amount': Decimal('0.00'), 'number_of_transactions': 0},
        }
        for row in payment_rows:
            breakdown[row['payment_method']] = {
                'total_sales_amount': row['total_sales_amount'] or Decimal('0.00'),
                'number_of_transactions': row['number_of_transactions'],
            }
        return breakdown

    def _report_breakdown(self, report_type, sales, sale_items):
        if report_type == 'product':
            return list(sale_items.values('product__id', 'product__name').annotate(
                quantity_sold=Sum('quantity'),
                total_sales_amount=Sum('price'),
            ).order_by('-quantity_sold', 'product__name'))

        if report_type == 'payment_method':
            return list(sales.values('payment_method').annotate(
                total_sales_amount=Sum('total_amount'),
                number_of_transactions=Count('id'),
            ).order_by('payment_method'))

        if report_type in ['cash_payments', 'mpesa_payments']:
            return list(sales.annotate(period=TruncDate('created_at')).values(
                'period',
                'user__username',
                'payment_method',
            ).annotate(
                total_sales_amount=Sum('total_amount'),
                number_of_transactions=Count('id'),
            ).order_by('-period', 'user__username'))

        if report_type == 'payment_trends':
            return list(sales.annotate(period=TruncDate('created_at')).values(
                'period',
                'payment_method',
            ).annotate(
                total_sales_amount=Sum('total_amount'),
                number_of_transactions=Count('id'),
            ).order_by('period', 'payment_method'))

        if report_type == 'cashier':
            return list(sales.values('user__id', 'user__username').annotate(
                total_sales_amount=Sum('total_amount'),
                number_of_transactions=Count('id'),
            ).order_by('user__username'))

        return list(sales.annotate(period=TruncDate('created_at')).values('period').annotate(
            total_sales_amount=Sum('total_amount'),
            number_of_transactions=Count('id'),
        ).order_by('period'))
