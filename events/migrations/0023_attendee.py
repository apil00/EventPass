# Generated by Django 5.2 on 2025-07-25 10:07

import django.db.models.deletion
import uuid
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('events', '0022_alter_guestinvitation_unique_together_and_more'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='Attendee',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('full_name', models.CharField(max_length=100)),
                ('is_user', models.BooleanField(default=False)),
                ('face_embedding', models.JSONField(blank=True, null=True)),
                ('qr_code_value', models.CharField(default=uuid.uuid4, max_length=100, unique=True)),
                ('checked_in', models.BooleanField(default=False)),
                ('checked_in_method', models.CharField(blank=True, choices=[('face', 'Face'), ('qr', 'QR')], max_length=10, null=True)),
                ('checked_in_time', models.DateTimeField(blank=True, null=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('ticket', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='attendees', to='events.ticket')),
                ('user', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to=settings.AUTH_USER_MODEL)),
            ],
        ),
    ]
