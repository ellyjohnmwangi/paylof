from django.db import models
from django.contrib.auth.models import User
from users.models import Business


class Distributor(models.Model):
    business = models.ForeignKey(Business, on_delete=models.CASCADE, related_name='distributors')
    name = models.CharField(max_length=150)
    contact_person = models.CharField(max_length=150, blank=True)
    phone = models.CharField(max_length=30, blank=True)
    email = models.EmailField(blank=True)
    location = models.CharField(max_length=150, blank=True)
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['name']
        unique_together = ('business', 'name')

    def __str__(self):
        return self.name

class Product(models.Model):
    business = models.ForeignKey(Business, on_delete=models.CASCADE, related_name='products', null=True, blank=True)
    distributor = models.ForeignKey(
        Distributor,
        on_delete=models.SET_NULL,
        related_name='products',
        null=True,
        blank=True,
    )
    name = models.CharField(max_length=100)
    price = models.DecimalField(max_digits=10, decimal_places=2)
    cost_price = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    stock = models.PositiveIntegerField(default=0)
    low_stock_threshold = models.PositiveIntegerField(default=5)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['name']

    @property
    def is_low_stock(self):
        return self.stock <= self.low_stock_threshold

    @property
    def stock_value(self):
        return self.cost_price * self.stock

    @property
    def estimated_margin(self):
        return self.price - self.cost_price

    def __str__(self):
        return self.name


class StockMovement(models.Model):
    TYPE_ADDED = 'added'
    TYPE_SOLD = 'sold'
    TYPE_ADJUSTED = 'adjusted'
    TYPE_DAMAGED = 'damaged'
    TYPE_LOST = 'lost'

    MOVEMENT_TYPE_CHOICES = [
        (TYPE_ADDED, 'Stock added'),
        (TYPE_SOLD, 'Stock sold'),
        (TYPE_ADJUSTED, 'Manual adjustment'),
        (TYPE_DAMAGED, 'Damaged stock'),
        (TYPE_LOST, 'Lost stock'),
    ]

    business = models.ForeignKey(Business, on_delete=models.CASCADE, related_name='stock_movements')
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='stock_movements')
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    movement_type = models.CharField(max_length=20, choices=MOVEMENT_TYPE_CHOICES)
    quantity = models.PositiveIntegerField()
    quantity_change = models.IntegerField()
    note = models.CharField(max_length=255, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.product.name}: {self.quantity_change}"


class PurchaseOrder(models.Model):
    STATUS_DRAFT = 'draft'
    STATUS_RECEIVED = 'received'

    STATUS_CHOICES = [
        (STATUS_DRAFT, 'Draft'),
        (STATUS_RECEIVED, 'Received'),
    ]

    business = models.ForeignKey(Business, on_delete=models.CASCADE, related_name='purchase_orders')
    distributor = models.ForeignKey(
        Distributor,
        on_delete=models.SET_NULL,
        related_name='purchase_orders',
        null=True,
        blank=True,
    )
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    reference = models.CharField(max_length=80, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_DRAFT)
    amount_paid = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    notes = models.TextField(blank=True)
    received_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    @property
    def total_amount(self):
        return sum((item.line_total for item in self.items.all()), start=0)

    @property
    def balance_due(self):
        return self.total_amount - self.amount_paid

    def __str__(self):
        return self.reference or f"Purchase order {self.pk}"


class PurchaseOrderItem(models.Model):
    purchase_order = models.ForeignKey(PurchaseOrder, on_delete=models.CASCADE, related_name='items')
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='purchase_order_items')
    quantity = models.PositiveIntegerField()
    unit_cost = models.DecimalField(max_digits=10, decimal_places=2)

    class Meta:
        ordering = ['product__name']

    @property
    def line_total(self):
        return self.quantity * self.unit_cost

    def __str__(self):
        return f"{self.quantity} x {self.product.name}"


class ExpenseCategory(models.Model):
    business = models.ForeignKey(Business, on_delete=models.CASCADE, related_name='expense_categories')
    name = models.CharField(max_length=120)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['name']
        unique_together = ('business', 'name')

    def __str__(self):
        return self.name


class Expense(models.Model):
    business = models.ForeignKey(Business, on_delete=models.CASCADE, related_name='expenses')
    category = models.ForeignKey(
        ExpenseCategory,
        on_delete=models.SET_NULL,
        related_name='expenses',
        null=True,
        blank=True,
    )
    recorded_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    title = models.CharField(max_length=150)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    expense_date = models.DateField()
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-expense_date', '-created_at']

    def __str__(self):
        return f"{self.title} - {self.amount}"
