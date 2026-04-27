from django.contrib import admin
from .models import (
    Distributor,
    Expense,
    ExpenseCategory,
    Product,
    PurchaseOrder,
    PurchaseOrderItem,
    StockMovement,
)


class PurchaseOrderItemInline(admin.TabularInline):
    model = PurchaseOrderItem
    extra = 0


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ('name', 'business', 'distributor', 'price', 'cost_price', 'stock', 'low_stock_threshold', 'is_low_stock', 'updated_at')
    search_fields = ('name', 'business__name', 'distributor__name')
    list_filter = ('business', 'distributor', 'created_at', 'updated_at')


@admin.register(Distributor)
class DistributorAdmin(admin.ModelAdmin):
    list_display = ('name', 'business', 'contact_person', 'phone', 'location', 'updated_at')
    search_fields = ('name', 'business__name', 'contact_person', 'phone')
    list_filter = ('business', 'created_at', 'updated_at')


@admin.register(StockMovement)
class StockMovementAdmin(admin.ModelAdmin):
    list_display = ('product', 'business', 'movement_type', 'quantity', 'quantity_change', 'user', 'created_at')
    search_fields = ('product__name', 'business__name', 'user__username', 'note')
    list_filter = ('business', 'movement_type', 'created_at')


@admin.register(PurchaseOrder)
class PurchaseOrderAdmin(admin.ModelAdmin):
    list_display = ('reference', 'business', 'distributor', 'status', 'amount_paid', 'created_by', 'created_at')
    search_fields = ('reference', 'business__name', 'distributor__name')
    list_filter = ('business', 'status', 'created_at', 'received_at')
    inlines = [PurchaseOrderItemInline]


@admin.register(ExpenseCategory)
class ExpenseCategoryAdmin(admin.ModelAdmin):
    list_display = ('name', 'business', 'created_at')
    search_fields = ('name', 'business__name')
    list_filter = ('business', 'created_at')


@admin.register(Expense)
class ExpenseAdmin(admin.ModelAdmin):
    list_display = ('title', 'business', 'category', 'amount', 'expense_date', 'recorded_by')
    search_fields = ('title', 'business__name', 'category__name', 'notes')
    list_filter = ('business', 'category', 'expense_date')
