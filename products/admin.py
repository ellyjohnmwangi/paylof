from django.contrib import admin
from .models import Distributor, Product, StockMovement


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ('name', 'business', 'distributor', 'price', 'stock', 'low_stock_threshold', 'is_low_stock', 'updated_at')
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
