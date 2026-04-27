from datetime import timedelta

from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from payments.models import ReportSubscription
from .models import Distributor, Product, StockMovement
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

    def test_manager_can_import_products_from_csv(self):
        self.client.force_authenticate(self.manager)
        csv_file = SimpleUploadedFile(
            'products.csv',
            b'name,price,cost_price,stock,low_stock_threshold,distributor\nBread,50,35,12,4,Nairobi Wholesale\nMilk,70,55,8,3,Nairobi Wholesale\n',
            content_type='text/csv',
        )

        response = self.client.post('/api/products/import-csv/', {'file': csv_file}, format='multipart')

        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data['created'], 2)
        self.assertEqual(Product.objects.filter(business=self.business).count(), 2)
        bread = Product.objects.get(business=self.business, name='Bread')
        self.assertEqual(bread.stock, 12)
        self.assertEqual(str(bread.cost_price), '35.00')
        self.assertEqual(bread.distributor.name, 'Nairobi Wholesale')
        self.assertTrue(
            StockMovement.objects.filter(
                product=bread,
                movement_type=StockMovement.TYPE_ADDED,
                quantity=12,
                note='CSV product import',
            ).exists()
        )

    def test_cashier_cannot_import_products_from_csv(self):
        self.client.force_authenticate(self.cashier)
        csv_file = SimpleUploadedFile(
            'products.csv',
            b'name,price\nBread,50\n',
            content_type='text/csv',
        )

        response = self.client.post('/api/products/import-csv/', {'file': csv_file}, format='multipart')

        self.assertEqual(response.status_code, 403)

    def test_manager_can_import_distributors_from_csv(self):
        self.client.force_authenticate(self.manager)
        csv_file = SimpleUploadedFile(
            'distributors.csv',
            b'name,contact_person,phone,email,location,notes\nNairobi Wholesale,John Mwangi,254712345678,orders@example.com,Industrial Area,Supplies dry goods\n',
            content_type='text/csv',
        )

        response = self.client.post('/api/distributors/import-csv/', {'file': csv_file}, format='multipart')

        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data['created'], 1)
        distributor = Distributor.objects.get(business=self.business, name='Nairobi Wholesale')
        self.assertEqual(distributor.contact_person, 'John Mwangi')
        self.assertEqual(distributor.phone, '254712345678')
        self.assertEqual(distributor.email, 'orders@example.com')
        self.assertEqual(distributor.location, 'Industrial Area')

    def test_cashier_cannot_import_distributors_from_csv(self):
        self.client.force_authenticate(self.cashier)
        csv_file = SimpleUploadedFile(
            'distributors.csv',
            b'name,phone\nNairobi Wholesale,254712345678\n',
            content_type='text/csv',
        )

        response = self.client.post('/api/distributors/import-csv/', {'file': csv_file}, format='multipart')

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
