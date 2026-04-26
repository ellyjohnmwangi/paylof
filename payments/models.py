from django.db import models

from sales.models import Sale
from users.models import Business


class MpesaPayment(models.Model):
    STATUS_PENDING = 'PENDING'
    STATUS_PAID = 'PAID'
    STATUS_FAILED = 'FAILED'
    STATUS_CANCELLED = 'CANCELLED'
    STATUS_TIMEOUT = 'TIMEOUT'

    STATUS_CHOICES = [
        (STATUS_PENDING, 'Pending'),
        (STATUS_PAID, 'Paid'),
        (STATUS_FAILED, 'Failed'),
        (STATUS_CANCELLED, 'Cancelled'),
        (STATUS_TIMEOUT, 'Timeout'),
    ]

    sale = models.ForeignKey(Sale, on_delete=models.CASCADE, related_name='mpesa_payments')
    business = models.ForeignKey(Business, on_delete=models.CASCADE, related_name='mpesa_payments')
    phone_number = models.CharField(max_length=20)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    merchant_request_id = models.CharField(max_length=100, blank=True, db_index=True)
    checkout_request_id = models.CharField(max_length=100, blank=True, db_index=True)
    mpesa_receipt_number = models.CharField(max_length=100, blank=True)
    response_code = models.CharField(max_length=20, blank=True)
    response_description = models.TextField(blank=True)
    customer_message = models.TextField(blank=True)
    result_code = models.IntegerField(blank=True, null=True)
    result_description = models.TextField(blank=True)
    request_payload = models.JSONField(default=dict, blank=True)
    response_payload = models.JSONField(default=dict, blank=True)
    callback_payload = models.JSONField(default=dict, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_PENDING)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['business', 'status']),
            models.Index(fields=['sale', 'status']),
        ]

    @property
    def is_terminal(self):
        return self.status in {
            self.STATUS_PAID,
            self.STATUS_FAILED,
            self.STATUS_CANCELLED,
            self.STATUS_TIMEOUT,
        }

    def __str__(self):
        return f"Sale {self.sale_id} - {self.status}"


class ReportSubscription(models.Model):
    PLAN_DAILY = 'daily'
    PLAN_WEEKLY = 'weekly'
    PLAN_MONTHLY = 'monthly'

    STATUS_ACTIVE = 'active'
    STATUS_EXPIRED = 'expired'

    PLAN_CHOICES = [
        (PLAN_DAILY, 'Daily'),
        (PLAN_WEEKLY, 'Weekly'),
        (PLAN_MONTHLY, 'Monthly'),
    ]
    STATUS_CHOICES = [
        (STATUS_ACTIVE, 'Active'),
        (STATUS_EXPIRED, 'Expired'),
    ]
    PLAN_AMOUNTS = {
        PLAN_DAILY: 30,
        PLAN_WEEKLY: 180,
        PLAN_MONTHLY: 700,
    }
    PLAN_DAYS = {
        PLAN_DAILY: 1,
        PLAN_WEEKLY: 7,
        PLAN_MONTHLY: 30,
    }

    business = models.ForeignKey(Business, on_delete=models.CASCADE, related_name='report_subscriptions')
    user = models.ForeignKey('auth.User', on_delete=models.SET_NULL, null=True, blank=True)
    plan = models.CharField(max_length=20, choices=PLAN_CHOICES)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_ACTIVE)
    starts_at = models.DateTimeField()
    expires_at = models.DateTimeField()
    payment_reference = models.CharField(max_length=80, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-expires_at']
        indexes = [
            models.Index(fields=['business', 'status', 'expires_at']),
        ]

    def __str__(self):
        return f"{self.business} {self.plan} reports until {self.expires_at:%Y-%m-%d}"


class ReportSubscriptionPayment(models.Model):
    STATUS_PENDING = 'PENDING'
    STATUS_PAID = 'PAID'
    STATUS_FAILED = 'FAILED'
    STATUS_CANCELLED = 'CANCELLED'
    STATUS_TIMEOUT = 'TIMEOUT'

    STATUS_CHOICES = [
        (STATUS_PENDING, 'Pending'),
        (STATUS_PAID, 'Paid'),
        (STATUS_FAILED, 'Failed'),
        (STATUS_CANCELLED, 'Cancelled'),
        (STATUS_TIMEOUT, 'Timeout'),
    ]

    business = models.ForeignKey(Business, on_delete=models.CASCADE, related_name='report_subscription_payments')
    user = models.ForeignKey('auth.User', on_delete=models.SET_NULL, null=True, blank=True)
    subscription = models.ForeignKey(
        ReportSubscription,
        on_delete=models.SET_NULL,
        related_name='payments',
        null=True,
        blank=True,
    )
    plan = models.CharField(max_length=20, choices=ReportSubscription.PLAN_CHOICES)
    phone_number = models.CharField(max_length=20)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    merchant_request_id = models.CharField(max_length=100, blank=True, db_index=True)
    checkout_request_id = models.CharField(max_length=100, blank=True, db_index=True)
    mpesa_receipt_number = models.CharField(max_length=100, blank=True)
    response_code = models.CharField(max_length=20, blank=True)
    response_description = models.TextField(blank=True)
    customer_message = models.TextField(blank=True)
    result_code = models.IntegerField(blank=True, null=True)
    result_description = models.TextField(blank=True)
    request_payload = models.JSONField(default=dict, blank=True)
    response_payload = models.JSONField(default=dict, blank=True)
    callback_payload = models.JSONField(default=dict, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_PENDING)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['business', 'status']),
            models.Index(fields=['checkout_request_id']),
        ]

    @property
    def is_terminal(self):
        return self.status in {
            self.STATUS_PAID,
            self.STATUS_FAILED,
            self.STATUS_CANCELLED,
            self.STATUS_TIMEOUT,
        }

    def __str__(self):
        return f"{self.get_plan_display()} reports - {self.status}"
