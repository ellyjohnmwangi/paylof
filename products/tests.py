from datetime import timedelta

from django.contrib.auth.models import User
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from payments.models import ReportSubscription
from .models import Product, StockMovement
from users.models import Business, UserProfile


class InventoryPermissionTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.business = Business.objects.create(name='Inventory Test Shop')
        self.manager = User.objects.create_user(username='manager', password='password123')
        UserProfile.objects.create(
            user=self.manager,
            business=self.business,
            role=UserProfile.ROLE_MANAGER,
        )
        self.cashier = User.objects.create_user(username='cashier', password='password123')
        UserProfile.objects.create(
            user=self.cashier,
            business=self.business,
            role=UserProfile.ROLE_CASHIER,
        )

    def create_report_subscription(self):
        now = timezone.now()
        return ReportSubscription.objects.create(
            business=self.business,
            user=self.manager,
            plan=ReportSubscription.PLAN_DAILY,
            amount='50.00',
            starts_at=now,
            expires_at=now + timedelta(days=1),
            payment_reference='RPTTEST',
        )

    def test_manager_can_create_product(self):
        self.client.force_authenticate(self.manager)

        response = self.client.post(
            '/api/products/',
            {
                'name': 'Sugar',
                'price': '150.00',
                'stock': 10,
                'low_stock_threshold': 3,
            },
            format='json',
        )

        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data['name'], 'Sugar')

    def test_cashier_cannot_create_product(self):
        self.client.force_authenticate(self.cashier)

        response = self.client.post(
            '/api/products/',
            {
                'name': 'Sugar',
                'price': '150.00',
                'stock': 10,
                'low_stock_threshold': 3,
            },
            format='json',
        )

        self.assertEqual(response.status_code, 403)

    def test_manager_can_adjust_stock_but_stock_reports_require_subscription(self):
        product = Product.objects.create(
            business=self.business,
            name='Rice',
            price='180.00',
            stock=5,
            low_stock_threshold=3,
        )
        self.client.force_authenticate(self.manager)

        adjust_response = self.client.post(
            f'/api/products/{product.id}/adjust_stock/',
            {
                'movement_type': StockMovement.TYPE_ADDED,
                'quantity': 7,
                'note': 'Supplier delivery',
            },
            format='json',
        )

        self.assertEqual(adjust_response.status_code, 201)
        product.refresh_from_db()
        self.assertEqual(product.stock, 12)

        locked_response = self.client.get('/api/products/reports/?type=current_stock')
        self.assertEqual(locked_response.status_code, 402)
        self.assertEqual(locked_response.data['code'], 'report_subscription_required')

        self.create_report_subscription()
        report_response = self.client.get('/api/products/reports/?type=current_stock')
        self.assertEqual(report_response.status_code, 200)
        self.assertEqual(report_response.data['summary']['stock_added'], 7)
        self.assertEqual(report_response.data['products'][0]['product_name'], 'Rice')
        self.assertEqual(report_response.data['products'][0]['reorder_level'], 3)

    def test_cashier_cannot_view_stock_reports(self):
        self.client.force_authenticate(self.cashier)

        response = self.client.get('/api/products/reports/?type=current_stock')

        self.assertEqual(response.status_code, 403)
