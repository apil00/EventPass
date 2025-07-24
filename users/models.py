# users/models.py

from django.db import models
from django.contrib.auth.models import AbstractUser
from django.contrib.auth.base_user import BaseUserManager
from django.contrib.postgres.fields import ArrayField
from django_ckeditor_5.fields import CKEditor5Field
from django.conf import settings
from django.utils.crypto import get_random_string
from events.models import Event

class CustomUserManager(BaseUserManager):
    def create_user(self, email, password=None, **extra_fields):
        if not email:
            raise ValueError('The Email must be set')
        email = self.normalize_email(email)
        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, email, password=None, **extra_fields):
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)

        if extra_fields.get('is_staff') is not True:
            raise ValueError('Superuser must have is_staff=True.')
        if extra_fields.get('is_superuser') is not True:
            raise ValueError('Superuser must have is_superuser=True.')

        return self.create_user(email, password, **extra_fields)


class CustomUser(AbstractUser):
    GENDER_CHOICES = [
        ('M', 'Male'),
        ('F', 'Female'),
        ('O', 'Other'),
        ('P', 'Prefer not to say'),
    ]
    
    username = None
    email = models.EmailField(unique=True)
    first_name = models.CharField(max_length=30)
    last_name = models.CharField(max_length=30)
    gender = models.CharField(max_length=1,choices=GENDER_CHOICES,blank=False, default='P')

    mobile_number = models.CharField(unique=True,
        max_length=10,
        blank=False)

    date_of_birth = models.DateField(blank=True, null=True)
    profile_picture = models.ImageField(upload_to='profile_pictures/', blank=True, null=True)
    address = models.CharField(max_length=255, blank=True, null=True)

    face_registered = models.BooleanField(default=False)

    is_email_verified = models.BooleanField(default=False)
    email_verification_token = models.CharField(max_length=64, blank=True, null=True)

    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['first_name', 'last_name', 'mobile_number']

    objects = CustomUserManager()

    def __str__(self):
        return f"{self.first_name} {self.last_name}"
    
    def get_full_name(self):
        return f"{self.first_name} {self.last_name}"
    
    def generate_email_verification_token(self):
        token = get_random_string(length=64)
        self.email_verification_token = token
        self.save(update_fields=['email_verification_token'])
        return token
    

class FaceEmbedding(models.Model):
    user = models.OneToOneField(CustomUser, on_delete=models.CASCADE, related_name='face_embedding')
    embedding = ArrayField(models.FloatField(), blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Face Embedding for {self.user.get_full_name()}"
    

class Announcement(models.Model):
    title = models.CharField(max_length=255)
    message = CKEditor5Field('Description', config_name='extends')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.title

    class Meta:
        ordering = ['-created_at']


class Notification(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='notifications')
    message = models.CharField(max_length=255)
    url = models.URLField(blank=True, null=True)
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.user.email}: {self.message}"
    

class UserEventPreference(models.Model):
    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name='event_preferences')
    category = models.CharField(max_length=20, choices=Event.CATEGORY_CHOICES)
    interest_score = models.FloatField(default=1.0)  # Base interest score
    last_interaction = models.DateTimeField(auto_now=True)  # Track when preference was last updated
    interactions_count = models.IntegerField(default=1)  # Track total interactions
    
    # Add index for better performance
    class Meta:
        unique_together = ('user', 'category')
        indexes = [
            models.Index(fields=['user', '-interest_score']),
            models.Index(fields=['category', '-interest_score']),
        ]

    def __str__(self):
        return f"{self.user.email} - {self.category} (score: {self.interest_score})"

class RecommendationFeedback(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    event = models.ForeignKey(Event, on_delete=models.CASCADE)
    liked = models.BooleanField()  # True for positive, False for negative feedback
    feedback_type = models.CharField(max_length=20, choices=[
        ('click', 'Clicked'),
        ('purchase', 'Purchased'),
        ('dismiss', 'Dismissed'),
        ('manual', 'Manual Rating'),
    ])
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        unique_together = ('user', 'event')