# Generated by Django 5.2 on 2025-05-03 10:59

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('events', '0001_initial'),
    ]

    operations = [
        migrations.RenameField(
            model_name='event',
            old_name='end_date',
            new_name='end_date_time',
        ),
        migrations.RenameField(
            model_name='event',
            old_name='title',
            new_name='name',
        ),
        migrations.RenameField(
            model_name='event',
            old_name='start_date',
            new_name='start_date_time',
        ),
        migrations.AddField(
            model_name='event',
            name='category',
            field=models.CharField(choices=[('conference', 'Conference'), ('workshop', 'Workshop'), ('seminar', 'Seminar'), ('social', 'Social Event'), ('other', 'Other')], default='conference', max_length=20),
        ),
        migrations.AddField(
            model_name='event',
            name='image',
            field=models.ImageField(blank=True, null=True, upload_to='events/'),
        ),
        migrations.AddField(
            model_name='event',
            name='status',
            field=models.CharField(choices=[('draft', 'Draft'), ('published', 'Published'), ('cancelled', 'Cancelled')], default='draft', max_length=20),
        ),
    ]
