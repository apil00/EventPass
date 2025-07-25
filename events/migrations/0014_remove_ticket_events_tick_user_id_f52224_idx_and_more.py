# Generated by Django 5.2 on 2025-05-12 10:16

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('events', '0013_alter_ticket_unique_together_ticket_status_and_more'),
    ]

    operations = [
        migrations.RemoveIndex(
            model_name='ticket',
            name='events_tick_user_id_f52224_idx',
        ),
        migrations.RemoveIndex(
            model_name='ticket',
            name='events_tick_event_i_706fce_idx',
        ),
        migrations.AlterUniqueTogether(
            name='ticket',
            unique_together=set(),
        ),
        migrations.AddField(
            model_name='ticket',
            name='payment_completed',
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name='ticket',
            name='price',
            field=models.DecimalField(decimal_places=2, default=200, max_digits=8),
            preserve_default=False,
        ),
        migrations.AlterField(
            model_name='event',
            name='category',
            field=models.CharField(choices=[('music', 'Music'), ('art', 'Art'), ('theater', 'Theater'), ('sports', 'Sports'), ('technology', 'Technology'), ('education', 'Education'), ('networking', 'Networking'), ('business', 'Business'), ('health', 'Health'), ('food', 'Food & Drink'), ('conference', 'Conference'), ('workshop', 'Workshop'), ('seminar', 'Seminar'), ('social', 'Social Event'), ('other', 'Other')], default='other', max_length=20),
        ),
        migrations.RemoveField(
            model_name='ticket',
            name='status',
        ),
    ]
