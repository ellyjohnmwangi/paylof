from django.db import migrations


def backfill_sale_business(apps, schema_editor):
    Business = apps.get_model('users', 'Business')
    UserProfile = apps.get_model('users', 'UserProfile')
    Sale = apps.get_model('sales', 'Sale')

    fallback_business = Business.objects.order_by('id').first()
    if not fallback_business:
        return

    for sale in Sale.objects.filter(business__isnull=True).select_related('user'):
        profile = UserProfile.objects.filter(user_id=sale.user_id).first()
        sale.business = profile.business if profile else fallback_business
        sale.save(update_fields=['business'])


def reverse_backfill_sale_business(apps, schema_editor):
    Sale = apps.get_model('sales', 'Sale')
    Sale.objects.update(business=None)


class Migration(migrations.Migration):

    dependencies = [
        ('users', '0002_seed_demo_business'),
        ('sales', '0004_sale_business'),
    ]

    operations = [
        migrations.RunPython(backfill_sale_business, reverse_backfill_sale_business),
    ]
