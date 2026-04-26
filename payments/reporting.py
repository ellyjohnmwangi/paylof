from datetime import timedelta
from uuid import uuid4

from django.utils import timezone
from rest_framework.response import Response

from .models import ReportSubscription
from .serializers import ReportSubscriptionSerializer


def report_plan_options():
    return [
        {
            'plan': ReportSubscription.PLAN_DAILY,
            'label': 'Daily',
            'amount': ReportSubscription.PLAN_AMOUNTS[ReportSubscription.PLAN_DAILY],
            'duration_days': ReportSubscription.PLAN_DAYS[ReportSubscription.PLAN_DAILY],
        },
        {
            'plan': ReportSubscription.PLAN_WEEKLY,
            'label': 'Weekly',
            'amount': ReportSubscription.PLAN_AMOUNTS[ReportSubscription.PLAN_WEEKLY],
            'duration_days': ReportSubscription.PLAN_DAYS[ReportSubscription.PLAN_WEEKLY],
        },
        {
            'plan': ReportSubscription.PLAN_MONTHLY,
            'label': 'Monthly',
            'amount': ReportSubscription.PLAN_AMOUNTS[ReportSubscription.PLAN_MONTHLY],
            'duration_days': ReportSubscription.PLAN_DAYS[ReportSubscription.PLAN_MONTHLY],
        },
    ]


def active_report_subscription(business):
    return ReportSubscription.objects.filter(
        business=business,
        status=ReportSubscription.STATUS_ACTIVE,
        expires_at__gt=timezone.now(),
    ).order_by('-expires_at').first()


def report_subscription_payload(business):
    subscription = active_report_subscription(business)
    return {
        'has_active_subscription': bool(subscription),
        'active_subscription': (
            ReportSubscriptionSerializer(subscription).data
            if subscription
            else None
        ),
        'plans': report_plan_options(),
    }


def report_subscription_required_response(request):
    payload = report_subscription_payload(request.user.profile.business)
    payload.update({
        'detail': 'A report subscription is required to view reports.',
        'code': 'report_subscription_required',
    })
    return Response(payload, status=402)


def create_report_subscription(business, user, plan, payment_reference=''):
    if plan not in ReportSubscription.PLAN_AMOUNTS:
        raise ValueError('Choose a valid report subscription plan.')

    now = timezone.now()
    active = active_report_subscription(business)
    starts_at = max(now, active.expires_at) if active else now
    expires_at = starts_at + timedelta(days=ReportSubscription.PLAN_DAYS[plan])

    return ReportSubscription.objects.create(
        business=business,
        user=user,
        plan=plan,
        amount=ReportSubscription.PLAN_AMOUNTS[plan],
        starts_at=starts_at,
        expires_at=expires_at,
        payment_reference=payment_reference or f'RPT{uuid4().hex[:10].upper()}',
    )
