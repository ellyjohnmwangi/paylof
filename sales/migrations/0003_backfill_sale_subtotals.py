from django.db import migrations


def backfill_sale_subtotals(apps, schema_editor):
    Sale = apps.get_model('sales', 'Sale')
    for sale in Sale.objects.filter(subtotal_amount=0, total_amount__gt=0):
        sale.subtotal_amount = sale.total_amount
        sale.save(update_fields=['subtotal_amount'])


def reverse_backfill_sale_subtotals(apps, schema_editor):
    Sale = apps.get_model('sales', 'Sale')
    Sale.objects.filter(transaction_fee=0).update(subtotal_amount=0)


class Migration(migrations.Migration):

    dependencies = [
        ('sales', '0002_alter_sale_options_sale_customer_phone_and_more'),
    ]

    operations = [
        migrations.RunPython(backfill_sale_subtotals, reverse_backfill_sale_subtotals),
    ]
