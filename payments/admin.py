from django.contrib import admin

from .models import MpesaPayment, ReportSubscription, ReportSubscriptionPayment


@admin.register(MpesaPayment)
class MpesaPaymentAdmin(admin.ModelAdmin):
    list_display = (
        'id',
        'business',
        'sale',
        'phone_number',
        'amount',
        'status',
        'mpesa_receipt_number',
        'created_at',
    )
    list_filter = ('business', 'status', 'created_at')
    search_fields = (
        'sale__id',
        'phone_number',
        'merchant_request_id',
        'checkout_request_id',
        'mpesa_receipt_number',
    )
    readonly_fields = (
        'merchant_request_id',
        'checkout_request_id',
        'response_code',
        'response_description',
        'customer_message',
        'result_code',
        'result_description',
        'request_payload',
        'response_payload',
        'callback_payload',
        'created_at',
        'updated_at',
    )


@admin.register(ReportSubscription)
class ReportSubscriptionAdmin(admin.ModelAdmin):
    list_display = ('id', 'business', 'user', 'plan', 'amount', 'status', 'expires_at')
    list_filter = ('plan', 'status', 'expires_at')
    search_fields = ('business__name', 'user__username', 'payment_reference')
    readonly_fields = ('created_at',)


@admin.register(ReportSubscriptionPayment)
class ReportSubscriptionPaymentAdmin(admin.ModelAdmin):
    list_display = (
        'id',
        'business',
        'user',
        'plan',
        'phone_number',
        'amount',
        'status',
        'mpesa_receipt_number',
        'created_at',
    )
    list_filter = ('business', 'plan', 'status', 'created_at')
    search_fields = (
        'business__name',
        'user__username',
        'phone_number',
        'merchant_request_id',
        'checkout_request_id',
        'mpesa_receipt_number',
    )
    readonly_fields = (
        'merchant_request_id',
        'checkout_request_id',
        'response_code',
        'response_description',
        'customer_message',
        'result_code',
        'result_description',
        'request_payload',
        'response_payload',
        'callback_payload',
        'created_at',
        'updated_at',
    )
