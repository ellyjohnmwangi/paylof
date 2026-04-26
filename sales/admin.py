from django.contrib import admin
from .models import Sale, SaleItem


class SaleItemInline(admin.TabularInline):
    model = SaleItem
    extra = 0
    readonly_fields = ('product', 'quantity', 'price')


@admin.register(Sale)
class SaleAdmin(admin.ModelAdmin):
    list_display = (
        'id',
        'business',
        'user',
        'subtotal_amount',
        'transaction_fee',
        'total_amount',
        'payment_method',
        'payment_status',
        'created_at',
    )
    list_filter = ('business', 'payment_method', 'payment_status', 'created_at')
    search_fields = ('id', 'user__username', 'customer_phone', 'mpesa_receipt_number')
    inlines = [SaleItemInline]


@admin.register(SaleItem)
class SaleItemAdmin(admin.ModelAdmin):
    list_display = ('sale', 'product', 'quantity', 'price')
    search_fields = ('product__name', 'sale__id')
