# events/recommendations.py
from django.utils import timezone
from django.db.models import Case, When, FloatField, F, Count
from django.core.cache import cache
from .models import Event
from users.models import UserEventPreference, RecommendationFeedback
import math
from datetime import timedelta

class EventRecommender:
    def __init__(self, user):
        self.user = user
        self.now = timezone.now()
    
    def get_recommendations(self, limit=5):
        cache_key = f'user_{self.user.id}_recommendations_v2'
        cached = cache.get(cache_key)
        if cached:
            return cached
            
        recommendations = self._generate_recommendations(limit)
        cache.set(cache_key, recommendations, timeout=3600)  # Cache for 1 hour
        return recommendations
    
    def _generate_recommendations(self, limit):
        # Get user preferences with time-decayed scores
        preferences = self._get_weighted_preferences()
        
        if not preferences:
            return self._get_fallback_recommendations(limit)
        
        # Get events from preferred categories
        events = self._get_events_from_preferences(preferences)
        
        if len(events) < limit:
            # If not enough recommendations, supplement with fallback
            extra_needed = limit - len(events)
            fallback = self._get_fallback_recommendations(extra_needed)
            events.extend(fallback)
        
        return events[:limit]
    
    def _get_weighted_preferences(self):
        """Calculate preferences with time decay and interaction count"""
        preferences = UserEventPreference.objects.filter(user=self.user)
        
        weighted_prefs = []
        for pref in preferences:
            # Time decay - reduce weight of older interactions
            days_since = (self.now - pref.last_interaction).days
            time_decay = math.exp(-days_since / 30)  # 30-day half-life
            
            # Interaction boost - more interactions = stronger signal
            interaction_boost = math.log(pref.interactions_count + 1) + 1
            
            # Calculate final weight
            weight = pref.interest_score * time_decay * interaction_boost
            
            weighted_prefs.append({
                'category': pref.category,
                'weight': weight,
                'original_score': pref.interest_score,
                'last_interaction': pref.last_interaction,
                'interactions': pref.interactions_count
            })
        
        # Sort by weight descending
        return sorted(weighted_prefs, key=lambda x: -x['weight'])
    
    def _get_events_from_preferences(self, preferences):
        """Get events based on weighted preferences"""
        categories = [p['category'] for p in preferences]
        weights = [p['weight'] for p in preferences]
        
        # Get upcoming events in preferred categories
        events = Event.objects.filter(
            start_date_time__gte=self.now
        ).exclude(
            tickets__user=self.user,
            tickets__payment_status='completed'
        ).annotate(
            popularity=Count('tickets'),
            preference_weight=Case(
                *[When(category=cat, then=weight) 
                  for cat, weight in zip(categories, weights)],
                default=1.0,
                output_field=FloatField()
            )
        ).order_by('-preference_weight', '-popularity', 'start_date_time')
        
        return list(events)
    
    def _get_fallback_recommendations(self, limit):
        """Fallback when no preferences exist"""
        return list(Event.objects.filter(
            start_date_time__gte=self.now,
            is_featured=True
        ).exclude(
            tickets__user=self.user,
            tickets__payment_status='completed'
        ).order_by('-is_featured', 'start_date_time')[:limit])