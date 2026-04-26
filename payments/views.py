from decimal import Decimal, InvalidOperation

from rest_framework import status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt

from sales.models import Sale
from users.permissions import CanSell, CanViewReports, HasBusinessProfile

from .models import MpesaPayment, ReportSubscriptionPayment
from .reporting import report_subscription_payload
from .serializers import MpesaPaymentSerializer, ReportSubscriptionPaymentSerializer
from .services import (
    MpesaConfigurationError,
    MpesaRequestError,
    format_phone_number,
    handle_stk_callback,
    start_report_subscription_payment,
    start_stk_push_for_sale,
    timeout_stale_mpesa_payment,
    timeout_stale_report_subscription_payment,
)


class StkPushPaymentView(APIView):
    permission_classes = [IsAuthenticated, HasBusinessProfile, CanSell]

    def post(self, request):
        sale_id = request.data.get('sale_id')
        phone_number = request.data.get('phone_number')

        if not sale_id or not phone_number:
            return Response(
                {'detail': 'sale_id and phone_number are required.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            sale = Sale.objects.get(
                id=sale_id,
                business=request.user.profile.business,
                payment_method='mpesa',
            )
        except Sale.DoesNotExist:
            return Response({'detail': 'M-Pesa sale not found.'}, status=status.HTTP_404_NOT_FOUND)

        amount = request.data.get('amount')
        if amount not in (None, ''):
            try:
                if Decimal(str(amount)) != sale.total_amount:
                    return Response(
                        {'detail': 'Amount must match the sale total.'},
                        status=status.HTTP_400_BAD_REQUEST,
                    )
            except (InvalidOperation, TypeError, ValueError):
                return Response({'detail': 'Amount must be valid.'}, status=status.HTTP_400_BAD_REQUEST)

        if sale.payment_status != Sale.PAYMENT_STATUS_PENDING:
            return Response(
                {'detail': 'Only pending M-Pesa sales can receive an STK Push.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            sale.customer_phone = format_phone_number(phone_number)
            sale.save(update_fields=['customer_phone'])
            payment, mpesa_response = start_stk_push_for_sale(sale, sale.customer_phone)
        except ValueError as exc:
            return Response({'detail': str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        except MpesaConfigurationError as exc:
            return Response({'detail': str(exc)}, status=status.HTTP_503_SERVICE_UNAVAILABLE)
        except MpesaRequestError as exc:
            return Response({'detail': str(exc)}, status=status.HTTP_502_BAD_GATEWAY)

        return Response({
            'message': 'STK Push sent successfully.',
            'payment_id': payment.id,
            'payment': MpesaPaymentSerializer(payment).data,
            'mpesa_response': mpesa_response,
        }, status=status.HTTP_201_CREATED)


class MpesaPaymentStatusView(APIView):
    permission_classes = [IsAuthenticated, HasBusinessProfile]

    def get(self, request, payment_id):
        try:
            payment = MpesaPayment.objects.select_related('sale').get(
                id=payment_id,
                business=request.user.profile.business,
            )
        except MpesaPayment.DoesNotExist:
            return Response({'detail': 'Payment not found.'}, status=status.HTTP_404_NOT_FOUND)

        payment = timeout_stale_mpesa_payment(payment)
        return Response(MpesaPaymentSerializer(payment).data)


@method_decorator(csrf_exempt, name='dispatch')
class MpesaCallbackView(APIView):
    authentication_classes = []
    permission_classes = [AllowAny]

    def post(self, request):
        raw_body = request._request.body.decode("utf-8", errors="replace")
        print("===== MPESA CALLBACK HIT =====")
        print("METHOD:", request.method)
        print("BODY:", raw_body)

        try:
            callback_data = request.data
            stk_callback = callback_data.get('Body', {}).get('stkCallback', {})
            checkout_request_id = stk_callback.get('CheckoutRequestID')

            payment = handle_stk_callback(callback_data)
            if payment:
                print("PAYMENT UPDATED:", payment.id, payment.status)
            else:
                print("PAYMENT NOT FOUND FOR:", checkout_request_id)

            return Response({
                'ResultCode': 0,
                'ResultDesc': 'Callback received successfully',
            })
        except Exception as exc:
            print("CALLBACK ERROR:", str(exc))
            return Response({
                'ResultCode': 0,
                'ResultDesc': 'Callback received with internal error',
            })


class ReportSubscriptionView(APIView):
    permission_classes = [IsAuthenticated, HasBusinessProfile, CanViewReports]

    def get(self, request):
        return Response(report_subscription_payload(request.user.profile.business))

    def post(self, request):
        plan = request.data.get('plan')
        phone_number = request.data.get('phone_number')

        if not phone_number:
            return Response(
                {'detail': 'phone_number is required.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            payment, mpesa_response = start_report_subscription_payment(
                business=request.user.profile.business,
                user=request.user,
                plan=plan,
                phone_number=phone_number,
            )
        except ValueError as exc:
            return Response({'detail': str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        except MpesaConfigurationError as exc:
            return Response({'detail': str(exc)}, status=status.HTTP_503_SERVICE_UNAVAILABLE)
        except MpesaRequestError as exc:
            return Response({'detail': str(exc)}, status=status.HTTP_502_BAD_GATEWAY)

        data = report_subscription_payload(request.user.profile.business)
        data.update({
            'message': 'STK Push sent successfully.',
            'payment_id': payment.id,
            'payment': ReportSubscriptionPaymentSerializer(payment).data,
            'mpesa_response': mpesa_response,
        })
        return Response(data, status=status.HTTP_201_CREATED)


class ReportSubscriptionPaymentStatusView(APIView):
    permission_classes = [IsAuthenticated, HasBusinessProfile, CanViewReports]

    def get(self, request, payment_id):
        try:
            payment = ReportSubscriptionPayment.objects.get(
                id=payment_id,
                business=request.user.profile.business,
            )
        except ReportSubscriptionPayment.DoesNotExist:
            return Response({'detail': 'Payment not found.'}, status=status.HTTP_404_NOT_FOUND)

        payment = timeout_stale_report_subscription_payment(payment)
        data = report_subscription_payload(request.user.profile.business)
        data['payment'] = ReportSubscriptionPaymentSerializer(payment).data
        return Response(data)
