#!/usr/bin/env python
"""
Reset report subscriptions for every business in the local PAYLOFT database.

Usage:
    ./venv/bin/python subscriptionreset.py
    ./venv/bin/python subscriptionreset.py --dry-run
    ./venv/bin/python subscriptionreset.py --delete-payments
"""

import argparse
import os
from datetime import timedelta

import django


os.environ.setdefault("DJANGO_SETTINGS_MODULE", "pos_backend.settings")
django.setup()

from django.utils import timezone  # noqa: E402
from payments.models import ReportSubscription, ReportSubscriptionPayment  # noqa: E402
from users.models import Business  # noqa: E402


def reset_subscriptions(delete_payments=False, dry_run=False):
    expired_at = timezone.now() - timedelta(minutes=1)
    businesses = Business.objects.order_by("name")
    all_subscriptions = ReportSubscription.objects.all()
    report_payments = ReportSubscriptionPayment.objects.all()

    print(f"Businesses found: {businesses.count()}")
    for business in businesses:
        business_subs = all_subscriptions.filter(business=business)
        print(f"- {business.name}: {business_subs.count()} subscription(s)")

    print(f"Subscriptions to reset: {all_subscriptions.count()}")
    if delete_payments:
        print(f"Report payment records to delete: {report_payments.count()}")

    if dry_run:
        print("Dry run only. No database changes were made.")
        return

    updated = all_subscriptions.update(
        status=ReportSubscription.STATUS_EXPIRED,
        expires_at=expired_at,
    )

    deleted_payments = None
    if delete_payments:
        deleted_payments = report_payments.delete()

    print(f"Expired {updated} subscription(s).")
    if deleted_payments is not None:
        print(f"Deleted report payment records: {deleted_payments}")
    print("All report subscriptions are now reset for testing.")


def main():
    parser = argparse.ArgumentParser(
        description="Expire report subscriptions for every PAYLOFT business."
    )
    parser.add_argument(
        "--delete-payments",
        action="store_true",
        help="Also delete report subscription payment attempts.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be reset without changing the database.",
    )
    args = parser.parse_args()

    reset_subscriptions(
        delete_payments=args.delete_payments,
        dry_run=args.dry_run,
    )


if __name__ == "__main__":
    main()
