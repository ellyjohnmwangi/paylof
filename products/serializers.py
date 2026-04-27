from rest_framework import serializers
from .models import (
    Distributor,
    Expense,
    ExpenseCategory,
    Product,
    PurchaseOrder,
    PurchaseOrderItem,
    StockMovement,
)


class DistributorSerializer(serializers.ModelSerializer):
    product_count = serializers.IntegerField(read_only=True)

    class Meta:
        model = Distributor
        fields = [
            'id',
            'name',
            'contact_person',
            'phone',
            'email',
            'location',
            'notes',
            'product_count',
            'created_at',
            'updated_at',
        ]

class ProductSerializer(serializers.ModelSerializer):
    is_low_stock = serializers.BooleanField(read_only=True)
    distributor_name = serializers.CharField(source='distributor.name', read_only=True)
    stock_value = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True)
    estimated_margin = serializers.DecimalField(max_digits=10, decimal_places=2, read_only=True)

    class Meta:
        model = Product
        fields = [
            'id',
            'distributor',
            'distributor_name',
            'name',
            'price',
            'cost_price',
            'stock',
            'stock_value',
            'estimated_margin',
            'low_stock_threshold',
            'is_low_stock',
            'created_at',
            'updated_at',
        ]

    def validate_distributor(self, value):
        if not value:
            return value
        request = self.context.get('request')
        business = getattr(getattr(request.user, 'profile', None), 'business', None)
        if business and value.business_id != business.id:
            raise serializers.ValidationError('Distributor must belong to your business.')
        return value


class StockAdjustmentSerializer(serializers.Serializer):
    movement_type = serializers.ChoiceField(
        choices=[
            StockMovement.TYPE_ADDED,
            StockMovement.TYPE_ADJUSTED,
            StockMovement.TYPE_DAMAGED,
            StockMovement.TYPE_LOST,
        ],
        default=StockMovement.TYPE_ADJUSTED,
    )
    quantity = serializers.IntegerField(min_value=1)
    note = serializers.CharField(max_length=255, allow_blank=True, required=False)


class StockMovementSerializer(serializers.ModelSerializer):
    product_name = serializers.CharField(source='product.name', read_only=True)
    user_name = serializers.CharField(source='user.username', read_only=True)

    class Meta:
        model = StockMovement
        fields = [
            'id',
            'product',
            'product_name',
            'user_name',
            'movement_type',
            'quantity',
            'quantity_change',
            'note',
            'created_at',
        ]


class PurchaseOrderItemSerializer(serializers.ModelSerializer):
    product_name = serializers.CharField(source='product.name', read_only=True)
    line_total = serializers.DecimalField(max_digits=10, decimal_places=2, read_only=True)

    class Meta:
        model = PurchaseOrderItem
        fields = [
            'id',
            'product',
            'product_name',
            'quantity',
            'unit_cost',
            'line_total',
        ]

    def validate_product(self, value):
        request = self.context.get('request')
        business = getattr(getattr(request.user, 'profile', None), 'business', None)
        if business and value.business_id != business.id:
            raise serializers.ValidationError('Product must belong to your business.')
        return value


class PurchaseOrderSerializer(serializers.ModelSerializer):
    distributor_name = serializers.CharField(source='distributor.name', read_only=True)
    items = PurchaseOrderItemSerializer(many=True)
    total_amount = serializers.DecimalField(max_digits=10, decimal_places=2, read_only=True)
    balance_due = serializers.DecimalField(max_digits=10, decimal_places=2, read_only=True)

    class Meta:
        model = PurchaseOrder
        fields = [
            'id',
            'distributor',
            'distributor_name',
            'reference',
            'status',
            'amount_paid',
            'total_amount',
            'balance_due',
            'notes',
            'received_at',
            'created_at',
            'updated_at',
            'items',
        ]
        read_only_fields = ['status', 'received_at']

    def validate_distributor(self, value):
        if not value:
            return value
        request = self.context.get('request')
        business = getattr(getattr(request.user, 'profile', None), 'business', None)
        if business and value.business_id != business.id:
            raise serializers.ValidationError('Distributor must belong to your business.')
        return value

    def validate_items(self, value):
        if not value:
            raise serializers.ValidationError('Add at least one product to receive.')
        return value

    def create(self, validated_data):
        items_data = validated_data.pop('items')
        order = PurchaseOrder.objects.create(**validated_data)
        for item_data in items_data:
            PurchaseOrderItem.objects.create(purchase_order=order, **item_data)
        return order

    def update(self, instance, validated_data):
        items_data = validated_data.pop('items', None)
        for field, value in validated_data.items():
            setattr(instance, field, value)
        instance.save()

        if items_data is not None and instance.status == PurchaseOrder.STATUS_DRAFT:
            instance.items.all().delete()
            for item_data in items_data:
                PurchaseOrderItem.objects.create(purchase_order=instance, **item_data)
        return instance


class ExpenseCategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = ExpenseCategory
        fields = ['id', 'name', 'created_at']


class ExpenseSerializer(serializers.ModelSerializer):
    category_name = serializers.CharField(source='category.name', read_only=True)

    class Meta:
        model = Expense
        fields = [
            'id',
            'category',
            'category_name',
            'title',
            'amount',
            'expense_date',
            'notes',
            'created_at',
        ]

    def validate_category(self, value):
        if not value:
            return value
        request = self.context.get('request')
        business = getattr(getattr(request.user, 'profile', None), 'business', None)
        if business and value.business_id != business.id:
            raise serializers.ValidationError('Expense category must belong to your business.')
        return value
