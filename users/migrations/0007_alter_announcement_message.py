# Generated by Django 5.2 on 2025-06-25 11:37

import django_ckeditor_5.fields
from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('users', '0006_announcement'),
    ]

    operations = [
        migrations.AlterField(
            model_name='announcement',
            name='message',
            field=django_ckeditor_5.fields.CKEditor5Field(verbose_name='Description'),
        ),
    ]
