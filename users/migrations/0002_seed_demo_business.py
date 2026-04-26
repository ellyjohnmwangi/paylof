from django.db import migrations


def seed_demo_business(apps, schema_editor):
    User = apps.get_model('auth', 'User')
    Business = apps.get_model('users', 'Business')
    UserProfile = apps.get_model('users', 'UserProfile')

    business, _ = Business.objects.get_or_create(
        name='PAYLOFT Demo SME',
        defaults={
            'phone': '+254700000000',
            'location': 'Nairobi',
        },
    )

    for user in User.objects.all():
        role = 'owner' if user.is_superuser or user.username == 'admin' else 'cashier'
        UserProfile.objects.get_or_create(
            user=user,
            defaults={
                'business': business,
                'role': role,
            },
        )


def reverse_seed_demo_business(apps, schema_editor):
    Business = apps.get_model('users', 'Business')
    Business.objects.filter(name='PAYLOFT Demo SME').delete()


class Migration(migrations.Migration):

    dependencies = [
        ('users', '0001_initial'),
    ]

    operations = [
        migrations.RunPython(seed_demo_business, reverse_seed_demo_business),
    ]
