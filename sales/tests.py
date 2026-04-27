from decimal import Decimal
from datetime import timedelta

from django.contrib.auth.models import User
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from payments.models import ReportSubscription
from products.models import Product, StockMovement
from sales.models import Sale
from users.models import Business, UserProfile


class CreateSaleTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.business = Business.objects.create(name='Test Kiosk')
        self.user = User.objects.create_user(username='cashier', password='password123')
        UserProfile.objects.create(
            user=self.user,
            business=self.business,
            role=UserProfile.ROLE_CASHIER,
        )
        self.manager = User.objects.create_user(username='manager', password='password123')
        UserProfile.objects.create(
            user=self.manager,
            business=self.business,
            role=UserProfile.ROLE_MANAGER,
        )
        self.client.force_authenticate(self.user)
        self.product = Product.objects.create(
            business=self.business,
            name='Bread',
            price=Decimal('50.00'),
            stock=10,
        )

    def create_report_subscription(self):
        now = timezone.now()
        return ReportSubscription.objects.create(
            business=self.business,
            user=self.manager,
            plan=ReportSubscription.PLAN_DAILY,
            amount=Decimal('50.00'),
            starts_at=now,
            expires_at=now + timedelta(days=1),
            payment_reference='RPTTEST',
        )

    def test_create_sale_uses_subtotal_total_and_updates_stock(self):
        response = self.client.post(
            '/api/sales/create_sale/',
            {
                'items': [{'product_id': self.product.id, 'quantity': 2}],
                'payment_method': 'cash',
            },
            format='json',
        )

        self.assertEqual(response.status_code, 201)
        self.assertEqual(Decimal(response.data['subtotal_amount']), Decimal('100.00'))
        self.assertEqual(Decimal(response.data['transaction_fee']), Decimal('0.00'))
        self.assertEqual(Decimal(response.data['total_amount']), Decimal('100.00'))

        self.product.refresh_from_db()
        self.assertEqual(self.product.stock, 8)
        self.assertEqual(Sale.objects.get().business, self.business)
        self.assertTrue(
            StockMovement.objects.filter(
                product=self.product,
                movement_type=StockMovement.TYPE_SOLD,
                quantity=2,
                quantity_change=-2,
            ).exists()
        )

    def test_create_sale_rejects_overselling(self):
        response = self.client.post(
            '/api/sales/create_sale/',
            {
                'items': [{'product_id': self.product.id, 'quantity': 20}],
                'payment_method': 'cash',
            },
            format='json',
        )

        self.assertEqual(response.status_code, 400)
        self.assertFalse(Sale.objects.exists())

        self.product.refresh_from_db()
        self.assertEqual(self.product.stock, 10)

    def test_mpesa_sale_requires_customer_phone(self):
        response = self.client.post(
            '/api/sales/create_sale/',
            {
                'items': [{'product_id': self.product.id, 'quantity': 1}],
                'payment_method': 'mpesa',
            },
            format='json',
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn('customer_phone', response.data)

    def test_sales_reports_are_manager_only_and_require_subscription(self):
        self.client.post(
            '/api/sales/create_sale/',
            {
                'items': [{'product_id': self.product.id, 'quantity': 2}],
                'payment_method': 'cash',
            },
            format='json',
        )

        cashier_response = self.client.get('/api/sales/reports/?type=daily')
        self.assertEqual(cashier_response.status_code, 403)

        self.client.force_authenticate(self.manager)
        locked_response = self.client.get('/api/sales/reports/?type=daily')
        self.assertEqual(locked_response.status_code, 402)
        self.assertEqual(locked_response.data['code'], 'report_subscription_required')

        self.create_report_subscription()
        manager_response = self.client.get('/api/sales/reports/?type=daily')

        self.assertEqual(manager_response.status_code, 200)
        self.assertEqual(manager_response.data['number_of_transactions'], 1)
        self.assertEqual(Decimal(manager_response.data['total_sales_amount']), Decimal('100.00'))
        self.assertIn('cash', manager_response.data['cash_vs_mpesa_sales'])
