# users/signals.py
from django.db.models.signals import post_save
from django.dispatch import receiver
from events.models import Ticket
from users.models import UserEventPreference
from django.utils import timezone

@receiver(post_save, sender=Ticket)
def update_user_preferences(sender, instance, created, **kwargs):
    if instance.payment_status == 'completed':
        event = instance.event
        user = instance.user
        
        # Get or create the preference
        preference, created = UserEventPreference.objects.get_or_create(
            user=user,
            category=event.category,
            defaults={
                'interest_score': 2.0,  # Higher initial score for purchases
                'interactions_count': 1
            }
        )
        
        if not created:
            # Increase score based on ticket type (VVIP > VIP > General)
            ticket_weight = {
                'general': 1.0,
                'vip': 1.5,
                'vvip': 2.0
            }.get(instance.ticket_type, 1.0)
            
            # Update preference with decay-aware scoring
            days_since = (timezone.now() - preference.last_interaction).days
            decay_factor = max(0.5, 1 - (days_since / 60))  # 60-day full decay
            
            preference.interest_score += ticket_weight * decay_factor
            preference.interactions_count += 1
            preference.save()