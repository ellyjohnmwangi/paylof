from django.db import migrations


def backfill_product_business(apps, schema_editor):
    Business = apps.get_model('users', 'Business')
    Distributor = apps.get_model('products', 'Distributor')
    Product = apps.get_model('products', 'Product')

    business = Business.objects.order_by('id').first()
    if not business:
        return

    distributor, _ = Distributor.objects.get_or_create(
        business=business,
        name='General Supplier',
        defaults={
            'contact_person': 'Demo supplier',
            'phone': '+254711000000',
            'location': 'Nairobi',
        },
    )

    Product.objects.filter(business__isnull=True).update(
        business=business,
        distributor=distributor,
    )


def reverse_backfill_product_business(apps, schema_editor):
    Product = apps.get_model('products', 'Product')
    Product.objects.update(business=None, distributor=None)


class Migration(migrations.Migration):

    dependencies = [
        ('users', '0002_seed_demo_business'),
        ('products', '0003_product_business_distributor_product_distributor'),
    ]

    operations = [
        migrations.RunPython(backfill_product_business, reverse_backfill_product_business),
    ]
