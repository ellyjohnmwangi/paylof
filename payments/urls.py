from django.urls import path

from .views import (
    MpesaCallbackView,
    MpesaPaymentStatusView,
    ReportSubscriptionPaymentStatusView,
    ReportSubscriptionView,
    StkPushPaymentView,
)

urlpatterns = [
    path('mpesa/stk-push/', StkPushPaymentView.as_view(), name='stk-push-payment'),
    path('mpesa/callback/', MpesaCallbackView.as_view(), name='mpesa-callback'),
    path(
        'mpesa/payment-status/<int:payment_id>/',
        MpesaPaymentStatusView.as_view(),
        name='mpesa-payment-status',
    ),
    path('reports/subscription/', ReportSubscriptionView.as_view(), name='report-subscription'),
    path(
        'reports/subscription/payment-status/<int:payment_id>/',
        ReportSubscriptionPaymentStatusView.as_view(),
        name='report-subscription-payment-status',
    ),
]
