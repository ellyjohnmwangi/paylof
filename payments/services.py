import base64
import logging
import re
from datetime import datetime, timedelta
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP

import requests
from django.conf import settings
from django.db import transaction
from django.db.models import F
from django.utils import timezone

from products.models import Product, StockMovement
from sales.models import Sale

from .models import MpesaPayment, ReportSubscription, ReportSubscriptionPayment
from .reporting import create_report_subscription

logger = logging.getLogger(__name__)
MPESA_PENDING_TIMEOUT_MINUTES = 3
MPESA_PENDING_TIMEOUT_MESSAGE = 'Payment timed out while waiting for M-Pesa confirmation.'


class MpesaConfigurationError(Exception):
    pass


class MpesaRequestError(Exception):
    pass


def _response_text(response):
    return getattr(response, 'text', '') or ''


def _response_status(response):
    return getattr(response, 'status_code', 'unknown')


def _required_setting(name):
    value = getattr(settings, name, '')
    if value is None or str(value).strip() == '':
        raise MpesaConfigurationError(f'{name} is not configured.')
    return str(value).strip()


def get_mpesa_access_token():
    consumer_key = _required_setting('MPESA_CONSUMER_KEY')
    consumer_secret = _required_setting('MPESA_CONSUMER_SECRET')
    url = f"{settings.MPESA_BASE_URL}/oauth/v1/generate?grant_type=client_credentials"

    try:
        response = requests.get(
            url,
            auth=(consumer_key, consumer_secret),
            timeout=settings.MPESA_REQUEST_TIMEOUT,
        )

        print('TOKEN STATUS:', _response_status(response))
        if _response_status(response) != 200:
            print('TOKEN RESPONSE:', _response_text(response))
            raise MpesaRequestError(
                f'M-Pesa token request failed: HTTP {_response_status(response)}: {_response_text(response)}'
            )

        data = response.json()
    except requests.RequestException as exc:
        raise MpesaRequestError(f'Could not get an M-Pesa access token: {exc}') from exc
    except ValueError as exc:
        raise MpesaRequestError(
            f'Safaricom returned an invalid token response: {_response_text(response)}'
        ) from exc

    token = data.get('access_token')
    if not token:
        raise MpesaRequestError(
            f'Safaricom token response did not include an access token: {_response_text(response)}'
        )
    return token


def format_phone_number(phone):
    phone = str(phone or '').strip()
    if phone.startswith('+'):
        phone = phone[1:]
    phone = re.sub(r'[\s().-]+', '', phone)

    if phone.startswith('07') or phone.startswith('01'):
        phone = f'254{phone[1:]}'
    elif phone.startswith('7') or phone.startswith('1'):
        phone = f'254{phone}'

    if not re.fullmatch(r'254(?:7|1)\d{8}', phone):
        raise ValueError('Enter a valid Safaricom phone number, for example 0712345678.')

    return phone


def normalize_mpesa_amount(amount):
    try:
        value = Decimal(str(amount))
    except (InvalidOperation, TypeError, ValueError) as exc:
        raise ValueError('Amount must be a valid number.') from exc

    if value <= 0:
        raise ValueError('Amount must be greater than zero.')

    return int(value.to_integral_value(rounding=ROUND_HALF_UP))


def generate_password(timestamp=None):
    shortcode = _required_setting('MPESA_SHORTCODE')
    passkey = _required_setting('MPESA_PASSKEY')
    timestamp = timestamp or datetime.now().strftime('%Y%m%d%H%M%S')
    raw_password = f'{shortcode}{passkey}{timestamp}'
    password = base64.b64encode(raw_password.encode()).decode('utf-8')
    return password, timestamp


def initiate_stk_push(phone_number, amount, sale_id=None, account_reference='', transaction_desc=''):
    access_token = get_mpesa_access_token()
    password, timestamp = generate_password()
    phone_number = format_phone_number(phone_number)
    mpesa_amount = normalize_mpesa_amount(amount)
    shortcode = _required_setting('MPESA_SHORTCODE')
    callback_url = _required_setting('MPESA_CALLBACK_URL')
    url = f'{settings.MPESA_BASE_URL}/mpesa/stkpush/v1/processrequest'
    account_reference = account_reference or f'{settings.MPESA_ACCOUNT_REFERENCE_PREFIX}-{sale_id}'
    transaction_desc = transaction_desc or f'POS payment for sale {sale_id}'

    payload = {
        'BusinessShortCode': int(shortcode),
        'Password': password,
        'Timestamp': timestamp,
        'TransactionType': settings.MPESA_TRANSACTION_TYPE,
        'Amount': mpesa_amount,
        'PartyA': int(phone_number),
        'PartyB': int(shortcode),
        'PhoneNumber': int(phone_number),
        'CallBackURL': callback_url,
        'AccountReference': account_reference,
        'TransactionDesc': transaction_desc,
    }
    headers = {
        'Authorization': f'Bearer {access_token}',
        'Content-Type': 'application/json',
    }

    safe_payload = {**payload, 'Password': '***'}
    print('STK PUSH URL:', url)
    print('STK PUSH PAYLOAD:', safe_payload)

    try:
        response = requests.post(
            url,
            json=payload,
            headers=headers,
            timeout=settings.MPESA_REQUEST_TIMEOUT,
        )

        print('STK STATUS:', _response_status(response))
        print('STK RESPONSE:', _response_text(response))

        if _response_status(response) != 200:
            raise MpesaRequestError(
                f'STK Push failed: HTTP {_response_status(response)}: {_response_text(response)}'
            )

        data = response.json()
    except requests.RequestException as exc:
        raise MpesaRequestError(f'M-Pesa STK Push request failed: {exc}') from exc
    except ValueError as exc:
        raise MpesaRequestError(
            f'Safaricom returned an invalid STK Push response: {_response_text(response)}'
        ) from exc

    return data, safe_payload


def start_stk_push_for_sale(sale, phone_number=None):
    try:
        phone_number = format_phone_number(phone_number or sale.customer_phone)
    except ValueError as exc:
        fail_sale_payment(sale, str(exc))
        raise

    payment = MpesaPayment.objects.create(
        business=sale.business,
        sale=sale,
        phone_number=phone_number,
        amount=sale.total_amount,
        status=MpesaPayment.STATUS_PENDING,
    )

    try:
        response_data, request_payload = initiate_stk_push(
            phone_number=phone_number,
            amount=sale.total_amount,
            sale_id=sale.id,
        )
    except Exception as exc:
        payment.status = MpesaPayment.STATUS_FAILED
        payment.result_description = str(exc)
        payment.save(update_fields=['status', 'result_description', 'updated_at'])
        fail_sale_payment(sale, str(exc))
        raise

    payment.merchant_request_id = response_data.get('MerchantRequestID', '')
    payment.checkout_request_id = response_data.get('CheckoutRequestID', '')
    payment.response_code = response_data.get('ResponseCode', '')
    payment.response_description = response_data.get('ResponseDescription', '')
    payment.customer_message = response_data.get('CustomerMessage', '')
    payment.request_payload = request_payload
    payment.response_payload = response_data
    payment.save(update_fields=[
        'merchant_request_id',
        'checkout_request_id',
        'response_code',
        'response_description',
        'customer_message',
        'request_payload',
        'response_payload',
        'updated_at',
    ])

    return payment, response_data


def start_report_subscription_payment(business, user, plan, phone_number):
    if plan not in ReportSubscription.PLAN_AMOUNTS:
        raise ValueError('Choose a valid report subscription plan.')

    phone_number = format_phone_number(phone_number)
    amount = ReportSubscription.PLAN_AMOUNTS[plan]
    payment = ReportSubscriptionPayment.objects.create(
        business=business,
        user=user,
        plan=plan,
        phone_number=phone_number,
        amount=amount,
        status=ReportSubscriptionPayment.STATUS_PENDING,
    )
    plan_label = dict(ReportSubscription.PLAN_CHOICES).get(plan, 'Reports')

    try:
        response_data, request_payload = initiate_stk_push(
            phone_number=phone_number,
            amount=amount,
            account_reference=f'RPT-{payment.id}',
            transaction_desc=f'{plan_label} PAYLOFT reports subscription',
        )
    except Exception as exc:
        payment.status = ReportSubscriptionPayment.STATUS_FAILED
        payment.result_description = str(exc)
        payment.save(update_fields=['status', 'result_description', 'updated_at'])
        raise

    payment.merchant_request_id = response_data.get('MerchantRequestID', '')
    payment.checkout_request_id = response_data.get('CheckoutRequestID', '')
    payment.response_code = response_data.get('ResponseCode', '')
    payment.response_description = response_data.get('ResponseDescription', '')
    payment.customer_message = response_data.get('CustomerMessage', '')
    payment.request_payload = request_payload
    payment.response_payload = response_data
    payment.save(update_fields=[
        'merchant_request_id',
        'checkout_request_id',
        'response_code',
        'response_description',
        'customer_message',
        'request_payload',
        'response_payload',
        'updated_at',
    ])

    return payment, response_data


def callback_items_to_dict(stk_callback):
    items = stk_callback.get('CallbackMetadata', {}).get('Item', [])
    return {
        item.get('Name'): item.get('Value')
        for item in items
        if item.get('Name')
    }


def _status_from_result_code(result_code):
    if result_code == 0:
        return MpesaPayment.STATUS_PAID
    if result_code == 1032:
        return MpesaPayment.STATUS_CANCELLED
    if result_code == 1037:
        return MpesaPayment.STATUS_TIMEOUT
    return MpesaPayment.STATUS_FAILED


def _parse_stk_result(stk_callback):
    result_code = stk_callback.get('ResultCode')
    try:
        result_code = int(result_code)
    except (TypeError, ValueError):
        result_code = None

    metadata = callback_items_to_dict(stk_callback)
    receipt_number = metadata.get('MpesaReceiptNumber', '')
    status = _status_from_result_code(result_code)
    return result_code, receipt_number, status


def handle_stk_callback(callback_data):
    stk_callback = callback_data.get('Body', {}).get('stkCallback', {})
    checkout_request_id = stk_callback.get('CheckoutRequestID', '')

    if not checkout_request_id:
        logger.warning('M-Pesa callback missing CheckoutRequestID: %s', callback_data)
        return None

    payment = MpesaPayment.objects.filter(
        checkout_request_id=checkout_request_id
    ).select_related('sale').first()

    if not payment:
        report_payment = ReportSubscriptionPayment.objects.filter(
            checkout_request_id=checkout_request_id
        ).first()
        if report_payment:
            return handle_report_subscription_callback(report_payment, callback_data, stk_callback)

        logger.warning('M-Pesa callback received for unknown checkout id %s', checkout_request_id)
        return None

    result_code, receipt_number, status = _parse_stk_result(stk_callback)

    with transaction.atomic():
        payment = MpesaPayment.objects.select_for_update().select_related('sale').get(pk=payment.pk)
        payment.merchant_request_id = stk_callback.get('MerchantRequestID', payment.merchant_request_id)
        payment.checkout_request_id = checkout_request_id
        payment.result_code = result_code
        payment.result_description = stk_callback.get('ResultDesc', '')
        payment.status = status
        payment.callback_payload = callback_data
        if receipt_number:
            payment.mpesa_receipt_number = receipt_number
        payment.save(update_fields=[
            'merchant_request_id',
            'checkout_request_id',
            'result_code',
            'result_description',
            'status',
            'callback_payload',
            'mpesa_receipt_number',
            'updated_at',
        ])

    if status == MpesaPayment.STATUS_PAID:
        complete_sale_payment(payment, receipt_number)
    else:
        fail_sale_payment(
            payment.sale,
            payment.result_description,
            sale_status=_sale_status_from_payment_status(status),
        )

    return payment


def handle_report_subscription_callback(payment, callback_data, stk_callback):
    result_code, receipt_number, status = _parse_stk_result(stk_callback)

    with transaction.atomic():
        payment = ReportSubscriptionPayment.objects.select_for_update().get(pk=payment.pk)
        payment.merchant_request_id = stk_callback.get('MerchantRequestID', payment.merchant_request_id)
        payment.checkout_request_id = stk_callback.get('CheckoutRequestID', payment.checkout_request_id)
        payment.result_code = result_code
        payment.result_description = stk_callback.get('ResultDesc', '')
        payment.status = status
        payment.callback_payload = callback_data
        if receipt_number:
            payment.mpesa_receipt_number = receipt_number

        if status == ReportSubscriptionPayment.STATUS_PAID and not payment.subscription_id:
            subscription = create_report_subscription(
                business=payment.business,
                user=payment.user,
                plan=payment.plan,
                payment_reference=receipt_number or f'RPT-{payment.id}',
            )
            payment.subscription = subscription

        payment.save(update_fields=[
            'merchant_request_id',
            'checkout_request_id',
            'result_code',
            'result_description',
            'status',
            'callback_payload',
            'mpesa_receipt_number',
            'subscription',
            'updated_at',
        ])

    return payment


def pending_payment_has_timed_out(payment):
    return payment.created_at <= timezone.now() - timedelta(minutes=MPESA_PENDING_TIMEOUT_MINUTES)


def timeout_stale_mpesa_payment(payment):
    if payment.status != MpesaPayment.STATUS_PENDING or not pending_payment_has_timed_out(payment):
        return payment

    with transaction.atomic():
        payment = MpesaPayment.objects.select_for_update().select_related('sale').get(pk=payment.pk)
        if payment.status != MpesaPayment.STATUS_PENDING or not pending_payment_has_timed_out(payment):
            return payment

        payment.status = MpesaPayment.STATUS_TIMEOUT
        payment.result_code = 1037
        payment.result_description = MPESA_PENDING_TIMEOUT_MESSAGE
        payment.save(update_fields=['status', 'result_code', 'result_description', 'updated_at'])

    fail_sale_payment(
        payment.sale,
        MPESA_PENDING_TIMEOUT_MESSAGE,
        sale_status=Sale.PAYMENT_STATUS_TIMEOUT,
    )
    payment.refresh_from_db()
    return payment


def timeout_stale_report_subscription_payment(payment):
    if (
        payment.status != ReportSubscriptionPayment.STATUS_PENDING
        or not pending_payment_has_timed_out(payment)
    ):
        return payment

    with transaction.atomic():
        payment = ReportSubscriptionPayment.objects.select_for_update().get(pk=payment.pk)
        if (
            payment.status != ReportSubscriptionPayment.STATUS_PENDING
            or not pending_payment_has_timed_out(payment)
        ):
            return payment

        payment.status = ReportSubscriptionPayment.STATUS_TIMEOUT
        payment.result_code = 1037
        payment.result_description = MPESA_PENDING_TIMEOUT_MESSAGE
        payment.save(update_fields=['status', 'result_code', 'result_description', 'updated_at'])

    payment.refresh_from_db()
    return payment


def complete_sale_payment(payment, receipt_number=''):
    with transaction.atomic():
        sale = Sale.objects.select_for_update().get(pk=payment.sale_id)
        if sale.payment_status in {
            Sale.PAYMENT_STATUS_FAILED,
            Sale.PAYMENT_STATUS_CANCELLED,
            Sale.PAYMENT_STATUS_TIMEOUT,
        }:
            logger.warning('Paid M-Pesa callback received for already failed sale %s', sale.id)
            return sale

        update_fields = []
        if sale.payment_status != Sale.PAYMENT_STATUS_PAID:
            sale.payment_status = Sale.PAYMENT_STATUS_PAID
            update_fields.append('payment_status')
        if receipt_number and sale.mpesa_receipt_number != receipt_number:
            sale.mpesa_receipt_number = receipt_number
            update_fields.append('mpesa_receipt_number')

        if update_fields:
            sale.save(update_fields=update_fields)

        return sale


def _sale_status_from_payment_status(payment_status):
    if payment_status == MpesaPayment.STATUS_CANCELLED:
        return Sale.PAYMENT_STATUS_CANCELLED
    if payment_status == MpesaPayment.STATUS_TIMEOUT:
        return Sale.PAYMENT_STATUS_TIMEOUT
    return Sale.PAYMENT_STATUS_FAILED


def fail_sale_payment(sale, result_description='', sale_status=Sale.PAYMENT_STATUS_FAILED):
    with transaction.atomic():
        sale = Sale.objects.select_for_update().get(pk=sale.pk)
        unpaid_terminal_statuses = {
            Sale.PAYMENT_STATUS_FAILED,
            Sale.PAYMENT_STATUS_CANCELLED,
            Sale.PAYMENT_STATUS_TIMEOUT,
        }
        if sale.payment_status in unpaid_terminal_statuses:
            return sale
        if sale.payment_status == Sale.PAYMENT_STATUS_PAID:
            logger.warning('Ignoring failed M-Pesa callback for already paid sale %s', sale.id)
            return sale

        for item in sale.items.select_related('product').all():
            Product.objects.filter(pk=item.product_id).update(stock=F('stock') + item.quantity)
            StockMovement.objects.create(
                business=sale.business,
                product=item.product,
                user=sale.user,
                movement_type=StockMovement.TYPE_ADJUSTED,
                quantity=item.quantity,
                quantity_change=item.quantity,
                note=f'M-Pesa payment {sale_status} for sale #{sale.id}',
            )

        sale.payment_status = sale_status
        if result_description and not sale.mpesa_receipt_number:
            sale.mpesa_receipt_number = ''
        sale.save(update_fields=['payment_status', 'mpesa_receipt_number'])
        return sale
