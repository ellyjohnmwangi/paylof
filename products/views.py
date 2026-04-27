import csv
from decimal import Decimal, InvalidOperation
from io import StringIO

from django.db import transaction
from django.db.models import Count, F, Q, Sum, Value
from django.db.models.functions import Coalesce
from django.utils import timezone
from django.utils.dateparse import parse_date
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from payments.reporting import active_report_subscription, report_subscription_required_response
from users.permissions import (
    CanManageDistributors,
    CanManageInventory,
    CanViewReports,
    HasBusinessProfile,
)
from .models import Distributor, Expense, ExpenseCategory, Product, PurchaseOrder, StockMovement
from .serializers import (
    DistributorSerializer,
    ExpenseCategorySerializer,
    ExpenseSerializer,
    ProductSerializer,
    PurchaseOrderSerializer,
    StockAdjustmentSerializer,
    StockMovementSerializer,
)

class ProductViewSet(viewsets.ModelViewSet):
    serializer_class = ProductSerializer
    parser_classes = [JSONParser, MultiPartParser, FormParser]

    def get_queryset(self):
        business = self.request.user.profile.business
        return Product.objects.select_related('distributor').filter(business=business).order_by('name')

    def get_permissions(self):
        if self.action == 'reports':
            permission_classes = [IsAuthenticated, HasBusinessProfile, CanViewReports]
        elif self.action in ['create', 'update', 'partial_update', 'destroy', 'adjust_stock', 'import_csv']:
            permission_classes = [IsAuthenticated, HasBusinessProfile, CanManageInventory]
        else:
            permission_classes = [IsAuthenticated, HasBusinessProfile]
        return [permission() for permission in permission_classes]

    def perform_create(self, serializer):
        product = serializer.save(business=self.request.user.profile.business)
        if product.stock > 0:
            StockMovement.objects.create(
                business=product.business,
                product=product,
                user=self.request.user,
                movement_type=StockMovement.TYPE_ADDED,
                quantity=product.stock,
                quantity_change=product.stock,
                note='Opening stock',
            )

    def perform_update(self, serializer):
        previous_stock = serializer.instance.stock
        product = serializer.save()
        stock_delta = product.stock - previous_stock
        if stock_delta:
            StockMovement.objects.create(
                business=product.business,
                product=product,
                user=self.request.user,
                movement_type=(
                    StockMovement.TYPE_ADDED
                    if stock_delta > 0
                    else StockMovement.TYPE_ADJUSTED
                ),
                quantity=abs(stock_delta),
                quantity_change=stock_delta,
                note='Stock edited from inventory',
            )

    @action(detail=False, methods=['get'])
    def low_stock(self, request):
        products = self.get_queryset().filter(stock__lte=F('low_stock_threshold'))
        serializer = self.get_serializer(products, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=['post'], url_path='import-csv')
    def import_csv(self, request):
        upload = request.FILES.get('file')
        if not upload:
            return Response({'file': 'Choose a CSV file to upload.'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            text = upload.read().decode('utf-8-sig')
        except UnicodeDecodeError:
            return Response({'file': 'CSV must be UTF-8 encoded.'}, status=status.HTTP_400_BAD_REQUEST)

        reader = csv.DictReader(StringIO(text))
        headers = {header.strip().lower() for header in (reader.fieldnames or []) if header}
        required_headers = {'name', 'price'}
        if not required_headers.issubset(headers):
            return Response(
                {'file': 'CSV must include at least name and price columns.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        business = request.user.profile.business
        created = 0
        updated = 0
        errors = []
        imported_products = []

        with transaction.atomic():
            for row_number, raw_row in enumerate(reader, start=2):
                row = {
                    (key or '').strip().lower(): (value or '').strip()
                    for key, value in raw_row.items()
                }
                if not any(row.values()):
                    continue

                try:
                    product, was_created = self._product_from_csv_row(business, request.user, row)
                except ValueError as exc:
                    errors.append({'row': row_number, 'detail': str(exc)})
                    continue

                imported_products.append(product)
                if was_created:
                    created += 1
                else:
                    updated += 1

            if errors:
                transaction.set_rollback(True)
                return Response(
                    {
                        'detail': 'CSV import failed. Fix the listed rows and upload again.',
                        'errors': errors,
                    },
                    status=status.HTTP_400_BAD_REQUEST,
                )

        return Response({
            'created': created,
            'updated': updated,
            'products': ProductSerializer(imported_products, many=True, context={'request': request}).data,
        }, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=['post'])
    def adjust_stock(self, request, pk=None):
        input_serializer = StockAdjustmentSerializer(data=request.data)
        input_serializer.is_valid(raise_exception=True)
        data = input_serializer.validated_data

        with transaction.atomic():
            product = self.get_queryset().select_for_update().get(pk=pk)
            movement_type = data['movement_type']
            quantity = data['quantity']

            if movement_type == StockMovement.TYPE_ADDED:
                quantity_change = quantity
            else:
                quantity_change = -quantity

            next_stock = product.stock + quantity_change
            if next_stock < 0:
                return Response(
                    {'detail': f'{product.name} only has {product.stock} available.'},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            product.stock = next_stock
            product.save(update_fields=['stock', 'updated_at'])
            movement = StockMovement.objects.create(
                business=product.business,
                product=product,
                user=request.user,
                movement_type=movement_type,
                quantity=quantity,
                quantity_change=quantity_change,
                note=data.get('note', ''),
            )

        return Response(StockMovementSerializer(movement).data, status=status.HTTP_201_CREATED)

    @action(detail=False, methods=['get'])
    def reports(self, request):
        if not active_report_subscription(request.user.profile.business):
            return report_subscription_required_response(request)

        report_type = request.query_params.get('type', 'current_stock')
        start_date, end_date = self._date_range(request)
        products = self.get_queryset()
        movements = StockMovement.objects.filter(
            business=request.user.profile.business,
            created_at__date__gte=start_date,
            created_at__date__lte=end_date,
        )

        if report_type == 'low_stock':
            products = products.filter(stock__lte=F('low_stock_threshold'), stock__gt=0)
        elif report_type == 'out_of_stock':
            products = products.filter(stock=0)
        elif report_type == 'stock_movement':
            product_ids = movements.values('product_id')
            products = products.filter(id__in=product_ids)
        elif report_type == 'stock_adjustment':
            product_ids = movements.filter(movement_type=StockMovement.TYPE_ADJUSTED).values('product_id')
            products = products.filter(id__in=product_ids)
        elif report_type == 'damaged_lost_stock':
            product_ids = movements.filter(
                movement_type__in=[StockMovement.TYPE_DAMAGED, StockMovement.TYPE_LOST]
            ).values('product_id')
            products = products.filter(id__in=product_ids)

        products = products.annotate(
            stock_added=Coalesce(
                Sum(
                    'stock_movements__quantity',
                    filter=Q(
                        stock_movements__movement_type=StockMovement.TYPE_ADDED,
                        stock_movements__created_at__date__gte=start_date,
                        stock_movements__created_at__date__lte=end_date,
                    ),
                ),
                Value(0),
            ),
            stock_sold=Coalesce(
                Sum(
                    'stock_movements__quantity',
                    filter=Q(
                        stock_movements__movement_type=StockMovement.TYPE_SOLD,
                        stock_movements__created_at__date__gte=start_date,
                        stock_movements__created_at__date__lte=end_date,
                    ),
                ),
                Value(0),
            ),
            stock_adjusted_manually=Coalesce(
                Sum(
                    'stock_movements__quantity',
                    filter=Q(
                        stock_movements__movement_type=StockMovement.TYPE_ADJUSTED,
                        stock_movements__created_at__date__gte=start_date,
                        stock_movements__created_at__date__lte=end_date,
                    ),
                ),
                Value(0),
            ),
            damaged_or_lost_stock=Coalesce(
                Sum(
                    'stock_movements__quantity',
                    filter=Q(
                        stock_movements__movement_type__in=[
                            StockMovement.TYPE_DAMAGED,
                            StockMovement.TYPE_LOST,
                        ],
                        stock_movements__created_at__date__gte=start_date,
                        stock_movements__created_at__date__lte=end_date,
                    ),
                ),
                Value(0),
            ),
        )

        rows = [
            {
                'product_name': product.name,
                'quantity_available': product.stock,
                'reorder_level': product.low_stock_threshold,
                'items_below_reorder_level': product.stock <= product.low_stock_threshold,
                'cost_price': product.cost_price,
                'selling_price': product.price,
                'stock_value': product.stock_value,
                'estimated_margin': product.estimated_margin,
                'stock_added': product.stock_added,
                'stock_sold': product.stock_sold,
                'stock_adjusted_manually': product.stock_adjusted_manually,
                'damaged_or_lost_stock': product.damaged_or_lost_stock,
            }
            for product in products
        ]

        return Response({
            'report_type': report_type,
            'start_date': start_date,
            'end_date': end_date,
            'summary': {
                'product_count': len(rows),
                'low_stock_count': self.get_queryset().filter(stock__lte=F('low_stock_threshold'), stock__gt=0).count(),
                'out_of_stock_count': self.get_queryset().filter(stock=0).count(),
                'items_below_reorder_level': sum(1 for row in rows if row['items_below_reorder_level']),
                'stock_added': sum(row['stock_added'] for row in rows),
                'stock_sold': sum(row['stock_sold'] for row in rows),
                'stock_adjusted_manually': sum(row['stock_adjusted_manually'] for row in rows),
                'damaged_or_lost_stock': sum(row['damaged_or_lost_stock'] for row in rows),
                'stock_value': sum((row['stock_value'] for row in rows), start=Decimal('0.00')),
            },
            'products': rows,
        })

    def _date_range(self, request):
        today = timezone.localdate()
        start_date = parse_date(request.query_params.get('start_date') or '') or today.replace(day=1)
        end_date = parse_date(request.query_params.get('end_date') or '') or today
        if end_date < start_date:
            start_date, end_date = end_date, start_date
        return start_date, end_date

    def _product_from_csv_row(self, business, user, row):
        name = row.get('name', '')
        if not name:
            raise ValueError('Product name is required.')

        price = self._csv_decimal(row.get('price'), 'price')
        cost_price = self._csv_decimal(row.get('cost_price') or row.get('buying_price') or '0', 'cost_price')
        stock = self._csv_int(row.get('stock') or row.get('quantity') or '0', 'stock')
        low_stock_threshold = self._csv_int(
            row.get('low_stock_threshold') or row.get('reorder_level') or '5',
            'low_stock_threshold',
        )
        distributor = self._csv_distributor(business, row.get('distributor') or row.get('supplier') or '')

        existing = Product.objects.filter(business=business, name__iexact=name).first()
        previous_stock = existing.stock if existing else 0

        if existing:
            product = existing
            product.name = name
            product.price = price
            product.cost_price = cost_price
            product.stock = stock
            product.low_stock_threshold = low_stock_threshold
            product.distributor = distributor
            product.save(update_fields=[
                'name',
                'price',
                'cost_price',
                'stock',
                'low_stock_threshold',
                'distributor',
                'updated_at',
            ])
            created = False
        else:
            product = Product.objects.create(
                business=business,
                name=name,
                price=price,
                cost_price=cost_price,
                stock=stock,
                low_stock_threshold=low_stock_threshold,
                distributor=distributor,
            )
            created = True

        stock_delta = stock - previous_stock
        if stock_delta:
            StockMovement.objects.create(
                business=business,
                product=product,
                user=user,
                movement_type=StockMovement.TYPE_ADDED if stock_delta > 0 else StockMovement.TYPE_ADJUSTED,
                quantity=abs(stock_delta),
                quantity_change=stock_delta,
                note='CSV product import' if created else 'CSV product update',
            )

        return product, created

    def _csv_decimal(self, value, field_name):
        try:
            amount = Decimal(str(value or '0'))
        except (InvalidOperation, TypeError, ValueError):
            raise ValueError(f'{field_name} must be a valid amount.')
        if amount < 0:
            raise ValueError(f'{field_name} cannot be negative.')
        return amount

    def _csv_int(self, value, field_name):
        try:
            number = int(value or 0)
        except (TypeError, ValueError):
            raise ValueError(f'{field_name} must be a whole number.')
        if number < 0:
            raise ValueError(f'{field_name} cannot be negative.')
        return number

    def _csv_distributor(self, business, name):
        if not name:
            return None
        distributor, _ = Distributor.objects.get_or_create(
            business=business,
            name=name,
            defaults={'notes': 'Created during CSV product import'},
        )
        return distributor


class DistributorViewSet(viewsets.ModelViewSet):
    serializer_class = DistributorSerializer
    parser_classes = [JSONParser, MultiPartParser, FormParser]
    permission_classes = [IsAuthenticated, HasBusinessProfile, CanManageDistributors]

    def get_queryset(self):
        business = self.request.user.profile.business
        return Distributor.objects.filter(business=business).annotate(
            product_count=Count('products')
        ).order_by('name')

    def perform_create(self, serializer):
        serializer.save(business=self.request.user.profile.business)

    @action(detail=False, methods=['post'], url_path='import-csv')
    def import_csv(self, request):
        upload = request.FILES.get('file')
        if not upload:
            return Response({'file': 'Choose a CSV file to upload.'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            text = upload.read().decode('utf-8-sig')
        except UnicodeDecodeError:
            return Response({'file': 'CSV must be UTF-8 encoded.'}, status=status.HTTP_400_BAD_REQUEST)

        reader = csv.DictReader(StringIO(text))
        headers = {header.strip().lower() for header in (reader.fieldnames or []) if header}
        if 'name' not in headers:
            return Response(
                {'file': 'CSV must include a name column.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        business = request.user.profile.business
        created = 0
        updated = 0
        errors = []
        imported_distributors = []

        with transaction.atomic():
            for row_number, raw_row in enumerate(reader, start=2):
                row = {
                    (key or '').strip().lower(): (value or '').strip()
                    for key, value in raw_row.items()
                }
                if not any(row.values()):
                    continue

                name = row.get('name', '')
                if not name:
                    errors.append({'row': row_number, 'detail': 'Distributor name is required.'})
                    continue

                distributor, was_created = Distributor.objects.update_or_create(
                    business=business,
                    name=name,
                    defaults={
                        'contact_person': row.get('contact_person') or row.get('contact') or '',
                        'phone': row.get('phone') or '',
                        'email': row.get('email') or '',
                        'location': row.get('location') or '',
                        'notes': row.get('notes') or row.get('supplies') or '',
                    },
                )
                imported_distributors.append(distributor)
                if was_created:
                    created += 1
                else:
                    updated += 1

            if errors:
                transaction.set_rollback(True)
                return Response(
                    {
                        'detail': 'CSV import failed. Fix the listed rows and upload again.',
                        'errors': errors,
                    },
                    status=status.HTTP_400_BAD_REQUEST,
                )

        return Response({
            'created': created,
            'updated': updated,
            'distributors': DistributorSerializer(imported_distributors, many=True).data,
        }, status=status.HTTP_201_CREATED)


class PurchaseOrderViewSet(viewsets.ModelViewSet):
    serializer_class = PurchaseOrderSerializer
    permission_classes = [IsAuthenticated, HasBusinessProfile, CanManageInventory]

    def get_queryset(self):
        business = self.request.user.profile.business
        return PurchaseOrder.objects.select_related('distributor', 'created_by').prefetch_related(
            'items__product'
        ).filter(business=business)

    def perform_create(self, serializer):
        serializer.save(
            business=self.request.user.profile.business,
            created_by=self.request.user,
        )

    @action(detail=True, methods=['post'])
    def receive(self, request, pk=None):
        with transaction.atomic():
            order = self.get_queryset().select_for_update().get(pk=pk)
            if order.status == PurchaseOrder.STATUS_RECEIVED:
                return Response({'detail': 'This purchase order has already been received.'}, status=status.HTTP_400_BAD_REQUEST)

            for item in order.items.select_related('product').select_for_update():
                product = item.product
                product.stock += item.quantity
                product.cost_price = item.unit_cost
                product.save(update_fields=['stock', 'cost_price', 'updated_at'])
                StockMovement.objects.create(
                    business=order.business,
                    product=product,
                    user=request.user,
                    movement_type=StockMovement.TYPE_ADDED,
                    quantity=item.quantity,
                    quantity_change=item.quantity,
                    note=f'Purchase received: {order.reference or order.id}',
                )

            order.status = PurchaseOrder.STATUS_RECEIVED
            order.received_at = timezone.now()
            order.save(update_fields=['status', 'received_at', 'updated_at'])

        return Response(self.get_serializer(order).data)


class ExpenseCategoryViewSet(viewsets.ModelViewSet):
    serializer_class = ExpenseCategorySerializer
    permission_classes = [IsAuthenticated, HasBusinessProfile, CanManageInventory]

    def get_queryset(self):
        return ExpenseCategory.objects.filter(business=self.request.user.profile.business)

    def perform_create(self, serializer):
        serializer.save(business=self.request.user.profile.business)


class ExpenseViewSet(viewsets.ModelViewSet):
    serializer_class = ExpenseSerializer

    def get_queryset(self):
        business = self.request.user.profile.business
        return Expense.objects.select_related('category', 'recorded_by').filter(business=business)

    def get_permissions(self):
        if self.action == 'reports':
            permission_classes = [IsAuthenticated, HasBusinessProfile, CanViewReports]
        else:
            permission_classes = [IsAuthenticated, HasBusinessProfile, CanManageInventory]
        return [permission() for permission in permission_classes]

    def perform_create(self, serializer):
        serializer.save(
            business=self.request.user.profile.business,
            recorded_by=self.request.user,
        )

    @action(detail=False, methods=['get'])
    def reports(self, request):
        if not active_report_subscription(request.user.profile.business):
            return report_subscription_required_response(request)

        start_date, end_date = self._date_range(request)
        expenses = self.get_queryset().filter(
            expense_date__gte=start_date,
            expense_date__lte=end_date,
        )
        total_expenses = expenses.aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
        categories = expenses.values('category__name').annotate(
            total_amount=Sum('amount'),
            number_of_expenses=Count('id'),
        ).order_by('-total_amount', 'category__name')

        return Response({
            'start_date': start_date,
            'end_date': end_date,
            'total_expenses': total_expenses,
            'number_of_expenses': expenses.count(),
            'by_category': list(categories),
            'expenses': ExpenseSerializer(expenses[:25], many=True).data,
        })

    def _date_range(self, request):
        today = timezone.localdate()
        start_date = parse_date(request.query_params.get('start_date') or '') or today.replace(day=1)
        end_date = parse_date(request.query_params.get('end_date') or '') or today
        if end_date < start_date:
            start_date, end_date = end_date, start_date
        return start_date, end_date
