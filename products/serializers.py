from rest_framework import serializers
from .models import Distributor, Product, StockMovement


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

    class Meta:
        model = Product
        fields = [
            'id',
            'distributor',
            'distributor_name',
            'name',
            'price',
            'stock',
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
