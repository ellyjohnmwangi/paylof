from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ('sales', '0005_backfill_sale_business'),
        ('users', '0002_seed_demo_business'),
    ]

    operations = [
        migrations.CreateModel(
            name='MpesaPayment',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('phone_number', models.CharField(max_length=20)),
                ('amount', models.DecimalField(decimal_places=2, max_digits=10)),
                ('merchant_request_id', models.CharField(blank=True, db_index=True, max_length=100)),
                ('checkout_request_id', models.CharField(blank=True, db_index=True, max_length=100)),
                ('mpesa_receipt_number', models.CharField(blank=True, max_length=100)),
                ('response_code', models.CharField(blank=True, max_length=20)),
                ('response_description', models.TextField(blank=True)),
                ('customer_message', models.TextField(blank=True)),
                ('result_code', models.IntegerField(blank=True, null=True)),
                ('result_description', models.TextField(blank=True)),
                ('request_payload', models.JSONField(blank=True, default=dict)),
                ('response_payload', models.JSONField(blank=True, default=dict)),
                ('callback_payload', models.JSONField(blank=True, default=dict)),
                ('status', models.CharField(choices=[('PENDING', 'Pending'), ('PAID', 'Paid'), ('FAILED', 'Failed'), ('CANCELLED', 'Cancelled'), ('TIMEOUT', 'Timeout')], default='PENDING', max_length=20)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('business', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='mpesa_payments', to='users.business')),
                ('sale', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='mpesa_payments', to='sales.sale')),
            ],
            options={
                'ordering': ['-created_at'],
            },
        ),
        migrations.AddIndex(
            model_name='mpesapayment',
            index=models.Index(fields=['business', 'status'], name='payments_mp_busines_77e684_idx'),
        ),
        migrations.AddIndex(
            model_name='mpesapayment',
            index=models.Index(fields=['sale', 'status'], name='payments_mp_sale_id_b36f29_idx'),
        ),
    ]
