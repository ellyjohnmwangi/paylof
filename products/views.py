from django.db import transaction
from django.db.models import Count, F, Q, Sum, Value
from django.db.models.functions import Coalesce
from django.utils import timezone
from django.utils.dateparse import parse_date
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from payments.reporting import active_report_subscription, report_subscription_required_response
from users.permissions import (
    CanManageDistributors,
    CanManageInventory,
    CanViewReports,
    HasBusinessProfile,
)
from .models import Distributor, Product, StockMovement
from .serializers import (
    DistributorSerializer,
    ProductSerializer,
    StockAdjustmentSerializer,
    StockMovementSerializer,
)

class ProductViewSet(viewsets.ModelViewSet):
    serializer_class = ProductSerializer

    def get_queryset(self):
        business = self.request.user.profile.business
        return Product.objects.select_related('distributor').filter(business=business).order_by('name')

    def get_permissions(self):
        if self.action == 'reports':
            permission_classes = [IsAuthenticated, HasBusinessProfile, CanViewReports]
        elif self.action in ['create', 'update', 'partial_update', 'destroy', 'adjust_stock']:
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


class DistributorViewSet(viewsets.ModelViewSet):
    serializer_class = DistributorSerializer
    permission_classes = [IsAuthenticated, HasBusinessProfile, CanManageDistributors]

    def get_queryset(self):
        business = self.request.user.profile.business
        return Distributor.objects.filter(business=business).annotate(
            product_count=Count('products')
        ).order_by('name')

    def perform_create(self, serializer):
        serializer.save(business=self.request.user.profile.business)
