from decimal import Decimal

from django.db import models
from django.contrib.auth.models import User
from products.models import Product
from users.models import Business

class Sale(models.Model):
    PAYMENT_STATUS_PAID = 'paid'
    PAYMENT_STATUS_PENDING = 'pending'
    PAYMENT_STATUS_FAILED = 'failed'
    PAYMENT_STATUS_CANCELLED = 'cancelled'
    PAYMENT_STATUS_TIMEOUT = 'timeout'

    PAYMENT_METHOD_CHOICES = [
        ('cash', 'Cash'),
        ('mpesa', 'M-Pesa'),
    ]
    PAYMENT_STATUS_CHOICES = [
        (PAYMENT_STATUS_PAID, 'Paid'),
        (PAYMENT_STATUS_PENDING, 'Pending'),
        (PAYMENT_STATUS_FAILED, 'Failed'),
        (PAYMENT_STATUS_CANCELLED, 'Cancelled'),
        (PAYMENT_STATUS_TIMEOUT, 'Timeout'),
    ]

    business = models.ForeignKey(Business, on_delete=models.CASCADE, related_name='sales', null=True, blank=True)
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    subtotal_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    transaction_fee = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    total_amount = models.DecimalField(max_digits=10, decimal_places=2)
    payment_method = models.CharField(max_length=20, choices=PAYMENT_METHOD_CHOICES)
    payment_status = models.CharField(max_length=20, choices=PAYMENT_STATUS_CHOICES, default='paid')
    customer_phone = models.CharField(max_length=20, blank=True)
    mpesa_receipt_number = models.CharField(max_length=50, blank=True)
    offline_reference = models.CharField(max_length=80, blank=True, null=True, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    @staticmethod
    def calculate_transaction_fee(subtotal_amount):
        subtotal = Decimal(str(subtotal_amount))
        if subtotal <= 0:
            return Decimal('0.00')
        if subtotal <= Decimal('500.00'):
            return Decimal('2.00')
        if subtotal <= Decimal('2000.00'):
            return Decimal('3.00')
        return Decimal('5.00')

    def __str__(self):
        return f"Sale {self.id} by {self.user.username}"

class SaleItem(models.Model):
    sale = models.ForeignKey(Sale, on_delete=models.CASCADE, related_name='items')
    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    quantity = models.IntegerField()
    price = models.DecimalField(max_digits=10, decimal_places=2)

    def __str__(self):
        return f"{self.quantity} x {self.product.name}"
