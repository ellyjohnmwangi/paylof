from datetime import timedelta
from decimal import Decimal
from unittest.mock import patch

from django.contrib.auth.models import User
from django.test import TestCase, override_settings
from django.utils import timezone
from rest_framework.test import APIClient

from payments.models import MpesaPayment, ReportSubscription, ReportSubscriptionPayment
from products.models import Product
from sales.models import Sale
from users.models import Business, UserProfile


class FakeDarajaResponse:
    def __init__(self, payload, status_code=200, text=''):
        self.payload = payload
        self.status_code = status_code
        self.text = text

    def raise_for_status(self):
        return None

    def json(self):
        return self.payload


@override_settings(
    MPESA_CONSUMER_KEY='consumer-key',
    MPESA_CONSUMER_SECRET='consumer-secret',
    MPESA_PASSKEY='passkey',
    MPESA_CALLBACK_URL='https://example.com/api/mpesa/callback/',
)
class MpesaPaymentTests(TestCase):
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

    def stub_daraja(self, post_mock, get_mock):
        get_mock.return_value = FakeDarajaResponse({'access_token': 'test-token'})
        post_mock.return_value = FakeDarajaResponse({
            'MerchantRequestID': '29115-34620561-1',
            'CheckoutRequestID': 'ws_CO_260420261320000001',
            'ResponseCode': '0',
            'ResponseDescription': 'Success. Request accepted for processing',
            'CustomerMessage': 'Success. Request accepted for processing',
        })

    def create_mpesa_sale(self):
        with patch('payments.services.requests.get') as get_mock, \
                patch('payments.services.requests.post') as post_mock:
            self.stub_daraja(post_mock, get_mock)
            return self.client.post(
                '/api/sales/create_sale/',
                {
                    'items': [{'product_id': self.product.id, 'quantity': 1}],
                    'payment_method': 'mpesa',
                    'customer_phone': '0712345678',
                },
                format='json',
            )

    def test_mpesa_sale_starts_pending_payment(self):
        response = self.create_mpesa_sale()

        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data['payment_status'], Sale.PAYMENT_STATUS_PENDING)
        self.assertIn('mpesa_payment', response.data)

        payment = MpesaPayment.objects.get()
        self.assertEqual(payment.status, MpesaPayment.STATUS_PENDING)
        self.assertEqual(payment.phone_number, '254712345678')
        self.assertEqual(payment.amount, Decimal('52.00'))
        self.assertEqual(payment.checkout_request_id, 'ws_CO_260420261320000001')

        self.product.refresh_from_db()
        self.assertEqual(self.product.stock, 9)

    def test_successful_callback_marks_sale_paid(self):
        self.create_mpesa_sale()
        payment = MpesaPayment.objects.get()

        response = self.client.post(
            '/api/mpesa/callback/',
            {
                'Body': {
                    'stkCallback': {
                        'MerchantRequestID': payment.merchant_request_id,
                        'CheckoutRequestID': payment.checkout_request_id,
                        'ResultCode': 0,
                        'ResultDesc': 'The service request is processed successfully.',
                        'CallbackMetadata': {
                            'Item': [
                                {'Name': 'Amount', 'Value': 52},
                                {'Name': 'MpesaReceiptNumber', 'Value': 'TQH7RT61SV'},
                                {'Name': 'PhoneNumber', 'Value': 254712345678},
                            ],
                        },
                    },
                },
            },
            format='json',
        )

        self.assertEqual(response.status_code, 200)
        payment.refresh_from_db()
        sale = payment.sale
        sale.refresh_from_db()

        self.assertEqual(payment.status, MpesaPayment.STATUS_PAID)
        self.assertEqual(payment.mpesa_receipt_number, 'TQH7RT61SV')
        self.assertEqual(sale.payment_status, Sale.PAYMENT_STATUS_PAID)
        self.assertEqual(sale.mpesa_receipt_number, 'TQH7RT61SV')

        self.product.refresh_from_db()
        self.assertEqual(self.product.stock, 9)

    def test_cancelled_callback_marks_sale_cancelled_and_restores_stock(self):
        self.create_mpesa_sale()
        payment = MpesaPayment.objects.get()

        response = self.client.post(
            '/api/mpesa/callback/',
            {
                'Body': {
                    'stkCallback': {
                        'MerchantRequestID': payment.merchant_request_id,
                        'CheckoutRequestID': payment.checkout_request_id,
                        'ResultCode': 1032,
                        'ResultDesc': 'Request cancelled by user.',
                    },
                },
            },
            format='json',
        )

        self.assertEqual(response.status_code, 200)
        payment.refresh_from_db()
        sale = payment.sale
        sale.refresh_from_db()

        self.assertEqual(payment.status, MpesaPayment.STATUS_CANCELLED)
        self.assertEqual(sale.payment_status, Sale.PAYMENT_STATUS_CANCELLED)

        self.product.refresh_from_db()
        self.assertEqual(self.product.stock, 10)

    def test_timeout_callback_marks_sale_timeout_and_restores_stock(self):
        self.create_mpesa_sale()
        payment = MpesaPayment.objects.get()

        response = self.client.post(
            '/api/mpesa/callback/',
            {
                'Body': {
                    'stkCallback': {
                        'MerchantRequestID': payment.merchant_request_id,
                        'CheckoutRequestID': payment.checkout_request_id,
                        'ResultCode': 1037,
                        'ResultDesc': 'DS timeout.',
                    },
                },
            },
            format='json',
        )

        self.assertEqual(response.status_code, 200)
        payment.refresh_from_db()
        sale = payment.sale
        sale.refresh_from_db()

        self.assertEqual(payment.status, MpesaPayment.STATUS_TIMEOUT)
        self.assertEqual(sale.payment_status, Sale.PAYMENT_STATUS_TIMEOUT)

        self.product.refresh_from_db()
        self.assertEqual(self.product.stock, 10)

    def test_payment_status_is_scoped_to_user_business(self):
        self.create_mpesa_sale()
        payment = MpesaPayment.objects.get()

        response = self.client.get(f'/api/mpesa/payment-status/{payment.id}/')

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['payment_id'], payment.id)
        self.assertEqual(response.data['status'], MpesaPayment.STATUS_PENDING)

    def test_stale_pending_payment_status_times_out_sale_and_restores_stock(self):
        self.create_mpesa_sale()
        payment = MpesaPayment.objects.get()
        MpesaPayment.objects.filter(pk=payment.pk).update(
            created_at=timezone.now() - timedelta(minutes=5)
        )

        response = self.client.get(f'/api/mpesa/payment-status/{payment.id}/')

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['status'], MpesaPayment.STATUS_TIMEOUT)

        payment.refresh_from_db()
        sale = payment.sale
        sale.refresh_from_db()
        self.assertEqual(payment.status, MpesaPayment.STATUS_TIMEOUT)
        self.assertEqual(sale.payment_status, Sale.PAYMENT_STATUS_TIMEOUT)

        self.product.refresh_from_db()
        self.assertEqual(self.product.stock, 10)

    def test_report_subscription_purchase_unlocks_reports_after_stk_callback(self):
        self.client.force_authenticate(self.manager)

        with patch('payments.services.requests.get') as get_mock, \
                patch('payments.services.requests.post') as post_mock:
            self.stub_daraja(post_mock, get_mock)
            response = self.client.post(
                '/api/reports/subscription/',
                {'plan': 'weekly', 'phone_number': '0712345678'},
                format='json',
            )

        self.assertEqual(response.status_code, 201)
        self.assertFalse(response.data['has_active_subscription'])
        self.assertEqual(response.data['payment']['status'], ReportSubscriptionPayment.STATUS_PENDING)
        self.assertFalse(ReportSubscription.objects.exists())

        payment = ReportSubscriptionPayment.objects.get()
        callback_response = self.client.post(
            '/api/mpesa/callback/',
            {
                'Body': {
                    'stkCallback': {
                        'MerchantRequestID': payment.merchant_request_id,
                        'CheckoutRequestID': payment.checkout_request_id,
                        'ResultCode': 0,
                        'ResultDesc': 'The service request is processed successfully.',
                        'CallbackMetadata': {
                            'Item': [
                                {'Name': 'Amount', 'Value': 180},
                                {'Name': 'MpesaReceiptNumber', 'Value': 'TQH7PLUS01'},
                                {'Name': 'PhoneNumber', 'Value': 254712345678},
                            ],
                        },
                    },
                },
            },
            format='json',
        )

        self.assertEqual(callback_response.status_code, 200)
        payment.refresh_from_db()
        subscription = ReportSubscription.objects.get()
        self.assertEqual(payment.status, ReportSubscriptionPayment.STATUS_PAID)
        self.assertEqual(payment.subscription, subscription)
        self.assertEqual(subscription.plan, ReportSubscription.PLAN_WEEKLY)
        self.assertEqual(subscription.amount, Decimal('180.00'))
        self.assertEqual(subscription.payment_reference, 'TQH7PLUS01')

        status_response = self.client.get(
            f'/api/reports/subscription/payment-status/{payment.id}/'
        )
        self.assertEqual(status_response.status_code, 200)
        self.assertTrue(status_response.data['has_active_subscription'])
        self.assertEqual(status_response.data['payment']['status'], ReportSubscriptionPayment.STATUS_PAID)

    def test_cancelled_report_subscription_payment_does_not_unlock_reports(self):
        self.client.force_authenticate(self.manager)

        with patch('payments.services.requests.get') as get_mock, \
                patch('payments.services.requests.post') as post_mock:
            self.stub_daraja(post_mock, get_mock)
            response = self.client.post(
                '/api/reports/subscription/',
                {'plan': 'weekly', 'phone_number': '0712345678'},
                format='json',
            )

        self.assertEqual(response.status_code, 201)
        payment = ReportSubscriptionPayment.objects.get()

        callback_response = self.client.post(
            '/api/mpesa/callback/',
            {
                'Body': {
                    'stkCallback': {
                        'MerchantRequestID': payment.merchant_request_id,
                        'CheckoutRequestID': payment.checkout_request_id,
                        'ResultCode': 1032,
                        'ResultDesc': 'Request cancelled by user.',
                    },
                },
            },
            format='json',
        )

        self.assertEqual(callback_response.status_code, 200)
        payment.refresh_from_db()
        self.assertEqual(payment.status, ReportSubscriptionPayment.STATUS_CANCELLED)
        self.assertFalse(ReportSubscription.objects.exists())

        status_response = self.client.get(
            f'/api/reports/subscription/payment-status/{payment.id}/'
        )
        self.assertEqual(status_response.status_code, 200)
        self.assertFalse(status_response.data['has_active_subscription'])
        self.assertEqual(status_response.data['payment']['status'], ReportSubscriptionPayment.STATUS_CANCELLED)

    def test_stale_pending_report_payment_status_times_out_without_unlocking_reports(self):
        self.client.force_authenticate(self.manager)

        with patch('payments.services.requests.get') as get_mock, \
                patch('payments.services.requests.post') as post_mock:
            self.stub_daraja(post_mock, get_mock)
            response = self.client.post(
                '/api/reports/subscription/',
                {'plan': 'weekly', 'phone_number': '0712345678'},
                format='json',
            )

        self.assertEqual(response.status_code, 201)
        payment = ReportSubscriptionPayment.objects.get()
        ReportSubscriptionPayment.objects.filter(pk=payment.pk).update(
            created_at=timezone.now() - timedelta(minutes=5)
        )

        status_response = self.client.get(
            f'/api/reports/subscription/payment-status/{payment.id}/'
        )

        self.assertEqual(status_response.status_code, 200)
        self.assertFalse(status_response.data['has_active_subscription'])
        self.assertEqual(status_response.data['payment']['status'], ReportSubscriptionPayment.STATUS_TIMEOUT)
        self.assertFalse(ReportSubscription.objects.exists())

    def test_stk_error_returns_safaricom_response_body(self):
        with patch('payments.services.requests.get') as get_mock, \
                patch('payments.services.requests.post') as post_mock:
            get_mock.return_value = FakeDarajaResponse({'access_token': 'test-token'})
            post_mock.return_value = FakeDarajaResponse(
                {'errorCode': '400.002.02'},
                status_code=400,
                text='{"errorCode":"400.002.02","errorMessage":"Bad Request"}',
            )

            response = self.client.post(
                '/api/sales/create_sale/',
                {
                    'items': [{'product_id': self.product.id, 'quantity': 1}],
                    'payment_method': 'mpesa',
                    'customer_phone': '0712345678',
                },
                format='json',
            )

        self.assertEqual(response.status_code, 502)
        self.assertIn('HTTP 400', response.data['detail'])
        self.assertIn('Bad Request', response.data['detail'])
