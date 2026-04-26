from rest_framework import serializers

from .models import MpesaPayment, ReportSubscription, ReportSubscriptionPayment


class MpesaPaymentSerializer(serializers.ModelSerializer):
    payment_id = serializers.IntegerField(source='id', read_only=True)
    sale_id = serializers.IntegerField(source='sale.id', read_only=True)

    class Meta:
        model = MpesaPayment
        fields = [
            'payment_id',
            'sale_id',
            'phone_number',
            'amount',
            'status',
            'merchant_request_id',
            'checkout_request_id',
            'mpesa_receipt_number',
            'response_code',
            'response_description',
            'customer_message',
            'result_code',
            'result_description',
            'created_at',
            'updated_at',
        ]


class ReportSubscriptionSerializer(serializers.ModelSerializer):
    label = serializers.CharField(source='get_plan_display', read_only=True)

    class Meta:
        model = ReportSubscription
        fields = [
            'id',
            'plan',
            'label',
            'amount',
            'status',
            'starts_at',
            'expires_at',
            'payment_reference',
            'created_at',
        ]


class ReportSubscriptionPaymentSerializer(serializers.ModelSerializer):
    payment_id = serializers.IntegerField(source='id', read_only=True)
    label = serializers.CharField(source='get_plan_display', read_only=True)
    subscription_id = serializers.IntegerField(source='subscription.id', read_only=True)

    class Meta:
        model = ReportSubscriptionPayment
        fields = [
            'payment_id',
            'subscription_id',
            'plan',
            'label',
            'phone_number',
            'amount',
            'status',
            'merchant_request_id',
            'checkout_request_id',
            'mpesa_receipt_number',
            'response_code',
            'response_description',
            'customer_message',
            'result_code',
            'result_description',
            'created_at',
            'updated_at',
        ]
