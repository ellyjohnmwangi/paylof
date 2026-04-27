from rest_framework import serializers
from .models import Sale, SaleItem

class SaleItemSerializer(serializers.ModelSerializer):
    product_name = serializers.CharField(source='product.name', read_only=True)

    class Meta:
        model = SaleItem
        fields = ['id', 'product', 'product_name', 'quantity', 'price', 'unit_cost', 'gross_profit']

class SaleSerializer(serializers.ModelSerializer):
    items = SaleItemSerializer(many=True, read_only=True)
    user_name = serializers.CharField(source='user.username', read_only=True)

    class Meta:
        model = Sale
        fields = [
            'id',
            'business',
            'user',
            'user_name',
            'subtotal_amount',
            'transaction_fee',
            'total_amount',
            'payment_method',
            'payment_status',
            'customer_phone',
            'mpesa_receipt_number',
            'offline_reference',
            'created_at',
            'items',
        ]


class SaleItemInputSerializer(serializers.Serializer):
    product_id = serializers.IntegerField(min_value=1)
    quantity = serializers.IntegerField(min_value=1)


class SaleCreateSerializer(serializers.Serializer):
    items = SaleItemInputSerializer(many=True)
    payment_method = serializers.ChoiceField(choices=Sale.PAYMENT_METHOD_CHOICES, default='cash')
    customer_phone = serializers.CharField(max_length=20, allow_blank=True, required=False)
    offline_reference = serializers.CharField(max_length=80, allow_blank=True, required=False)

    def validate_items(self, value):
        if not value:
            raise serializers.ValidationError('At least one item is required.')
        return value

    def validate(self, attrs):
        payment_method = attrs.get('payment_method', 'cash')
        customer_phone = attrs.get('customer_phone', '').strip()

        if payment_method == 'mpesa' and not customer_phone:
            raise serializers.ValidationError({
                'customer_phone': 'Customer phone number is required for M-Pesa payments.'
            })

        attrs['customer_phone'] = customer_phone
        attrs['offline_reference'] = attrs.get('offline_reference', '').strip() or None
        return attrs
