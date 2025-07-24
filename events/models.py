# events/models.py

from django.db import models
from django.utils import timezone
from django.core.validators import MinValueValidator
from django_ckeditor_5.fields import CKEditor5Field
from django.conf import settings
import qrcode
from django.core.files import File
from io import BytesIO
from django.core.exceptions import ValidationError
from django.urls import reverse
import uuid


class Event(models.Model):
    STATUS_CHOICES = [
        ('Live','Live'),
        ('Upcoming', 'Upcoming'),
        ('Ended', 'Ended'),
        ('Cancelled', 'Cancelled'),
    ]

    CATEGORY_CHOICES = [
        ('music', 'Music'),
        ('art', 'Art'),
        ('theater', 'Theater'),
        ('sports', 'Sports'),
        ('technology', 'Technology'),
        ('education', 'Education'),
        ('networking', 'Networking'),
        ('business', 'Business'),
        ('health', 'Health'),
        ('food', 'Food & Drink'),
        ('conference', 'Conference'),
        ('workshop', 'Workshop'),
        ('seminar', 'Seminar'),
        ('social', 'Social Event'),
        ('other', 'Other'),
    ]

    # Basic Information
    name = models.CharField(max_length=200)
    description = CKEditor5Field('Description', config_name='extends')
    location = models.CharField(max_length=255)

    # Event Timing
    start_date_time = models.DateTimeField()
    end_date_time = models.DateTimeField()

    # Category
    category = models.CharField(max_length=20, choices=CATEGORY_CHOICES, default='other')
    is_featured = models.BooleanField(default=False)

    # Pricing
    is_free = models.BooleanField(default=False)
    general_price = models.DecimalField(
        max_digits=8,
        decimal_places=2,
        validators=[MinValueValidator(0)],
        null=True,
        blank=True
    )
    vip_price = models.DecimalField(
        max_digits=8,
        decimal_places=2,
        validators=[MinValueValidator(0)],
        null=True,
        blank=True
    )
    vvip_price = models.DecimalField(
        max_digits=8,
        decimal_places=2,
        validators=[MinValueValidator(0)],
        null=True,
        blank=True
    )

    # Media
    image = models.ImageField(upload_to='events/', blank=False, null=False)

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['start_date_time']
        verbose_name = 'Event'
        verbose_name_plural = 'Events'
        indexes = [
            models.Index(fields=['start_date_time']),
            models.Index(fields=['is_featured']),
            models.Index(fields=['category']),
        ]

    def __str__(self):
        return self.name
    
    def clean(self):
        """Validate model before saving"""
        super().clean()
        
        # Ensure end date is after start date
        if self.start_date_time and self.end_date_time:
            if self.end_date_time <= self.start_date_time:
                raise ValidationError("End date/time must be after start date/time")
        
        # Validate pricing structure
        if not self.is_free:
            if (self.general_price is None and 
                self.vip_price is None and 
                self.vvip_price is None):
                raise ValidationError(
                    "For paid events, you must provide at least one price tier"
        )
            
            # Validate price hierarchy
            prices = {
                'general': self.general_price or 0,
                'vip': self.vip_price or 0,
                'vvip': self.vvip_price or 0
            }
            
            if prices['vip'] > 0 and prices['vip'] <= prices['general']:
                raise ValidationError("VIP price must be higher than General price")
                
            if prices['vvip'] > 0 and prices['vvip'] <= prices['vip']:
                raise ValidationError("VVIP price must be higher than VIP price")
    
    def get_absolute_url(self):
        return reverse('event_detail', kwargs={'pk': self.pk})

    def get_status(self):
        now = timezone.now()
        if now < self.start_date_time:
            return 'Upcoming'
        elif now > self.end_date_time:
            return 'Ended'
        else:
            return 'Live'

    def get_price_tiers(self):
        if self.is_free:
            return [('Free', 0)]
        tiers = [('General', self.general_price)]
        if self.vip_price:
            tiers.append(('VIP', self.vip_price))
        if self.vvip_price:
            tiers.append(('VVIP', self.vvip_price))
        return tiers

    def get_price_display(self):
        if self.is_free:
            return "Free"
        if self.vvip_price:
            return f"Rs. {self.general_price} - {self.vvip_price}"
        if self.vip_price:
            return f"Rs. {self.general_price} - {self.vip_price}"
        return f"Rs. {self.general_price}"

    def save(self, *args, **kwargs):
        """Ensure pricing is handled correctly for free events"""
        if self.is_free:
            self.general_price = 0
            self.vip_price = None
            self.vvip_price = None
        super().save(*args, **kwargs)


class Ticket(models.Model):
    TICKET_TYPES = [
        ('general', 'General'),
        ('vip', 'VIP'),
        ('vvip', 'VVIP'),
    ]
    
    PAYMENT_METHODS = [
        ('esewa', 'eSewa'),
    ]

    PAYMENT_STATUS = [
        ('pending', 'Pending'),
        ('completed', 'Completed'),
        ('failed', 'Failed'),
    ]
    
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='tickets')
    event = models.ForeignKey(Event, on_delete=models.CASCADE, related_name='tickets')
    ticket_type = models.CharField(max_length=10, choices=TICKET_TYPES)
    price = models.DecimalField(max_digits=8, decimal_places=2)
    payment_method = models.CharField(max_length=10, choices=PAYMENT_METHODS)
    payment_completed = models.BooleanField(default=False)
    payment_status = models.CharField(max_length=10,choices=PAYMENT_STATUS, default='pending')
    payment_details = models.JSONField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    qr_code = models.ImageField(upload_to='tickets/qr_codes/', blank=True, null=True)

    qr_code_value = models.CharField(max_length=100, unique=True, null=True, blank=True)
    checked_in = models.BooleanField(default=False)
    checked_in_method = models.CharField(max_length=10, choices=[('face', 'Face'), ('qr', 'QR')], null=True, blank=True)
    checked_in_time = models.DateTimeField(null=True, blank=True)

    class Meta:
        unique_together = ('user', 'event')

    def __str__(self):
        return f"{self.user.email} - {self.event.name} ({self.get_ticket_type_display()})"
    
    def save(self, *args, **kwargs):
        if not self.qr_code_value:
            self.qr_code_value = str(uuid.uuid4())
        if not self.qr_code and self.payment_completed:
            self.generate_qr_code()
        super().save(*args, **kwargs)
    
    def generate_qr_code(self):
        qr = qrcode.QRCode(
            version=1,
            error_correction=qrcode.constants.ERROR_CORRECT_L,
            box_size=10,
            border=4,
        )
        # qr.add_data(ticket_data)
        qr.add_data(self.qr_code_value)
        qr.make(fit=True)
        
        img = qr.make_image(fill_color="black", back_color="white")
        
        # Create a BytesIO buffer to save the image
        buffer = BytesIO()
        img.save(buffer, 'PNG')
        
        # Generate filename
        filename = f'ticket_{self.id}_qr.png'
        
        # Save to model
        self.qr_code.save(filename, File(buffer), save=False)
        buffer.close()