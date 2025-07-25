# Generated by Django 5.2 on 2025-05-10 17:10

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('events', '0008_ticket'),
    ]

    operations = [
        migrations.AddField(
            model_name='ticket',
            name='payment_details',
            field=models.JSONField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='ticket',
            name='payment_status',
            field=models.CharField(choices=[('pending', 'Pending'), ('completed', 'Completed'), ('failed', 'Failed')], default='pending', max_length=10),
        ),
    ]
