# events/admin.py
from django.contrib import admin
from django import forms
from .models import Event, Ticket
from django.utils.html import format_html
import csv
from django.http import HttpResponse
from django.urls import reverse
from django.contrib.auth import get_user_model
from users.models import Notification

class EventAdminForm(forms.ModelForm):
    class Meta:
        model = Event
        fields = '__all__'
    
    def clean(self):
        cleaned_data = super().clean()
        is_free = cleaned_data.get('is_free')
        general_price = cleaned_data.get('general_price')
        vip_price = cleaned_data.get('vip_price')
        vvip_price = cleaned_data.get('vvip_price')
        
        # Validate pricing structure
        if not is_free:
            # At least one price tier must be provided
            if general_price is None and vip_price is None and vvip_price is None:
                raise forms.ValidationError(
                    "For paid events, you must provide at least one price (General, VIP, or VVIP)"
                )
            
            # Validate that provided prices are positive
            if general_price is not None and general_price <= 0:
                raise forms.ValidationError("General price must be positive")
            if vip_price is not None and vip_price <= 0:
                raise forms.ValidationError("VIP price must be positive")
            if vvip_price is not None and vvip_price <= 0:
                raise forms.ValidationError("VVIP price must be positive")
            
            # Validate price hierarchy if multiple prices provided
            if general_price and vip_price and vip_price <= general_price:
                raise forms.ValidationError("VIP price must be higher than General price")
            if vip_price and vvip_price and vvip_price <= vip_price:
                raise forms.ValidationError("VVIP price must be higher than VIP price")
            if general_price and vvip_price and vvip_price <= general_price:
                raise forms.ValidationError("VVIP price must be higher than General price")
        
        return cleaned_data

@admin.register(Event)
class EventAdmin(admin.ModelAdmin):
    form = EventAdminForm
    list_display = ('name', 'location', 'start_date_time', 'end_date_time', 
                   'category', 'is_featured', 'status_display', 'price_display', 'is_free')
    list_filter = ('category', 'is_featured', 'start_date_time', 'is_free')
    search_fields = ('name', 'description', 'location')
    list_editable = ('is_featured',)
    readonly_fields = ('capacity_display', 'seats_available_display')
    
    fieldsets = (
        (None, {
            'fields': ('name', 'description', 'image')
        }),
        ('Event Info', {
            'fields': ('location', 'start_date_time', 'end_date_time', 'category', 'is_featured')
        }),
        ('Capacity & Seating', {
            'fields': ('total_capacity', 'general_seats', 'vip_seats', 'vvip_seats',
                      'capacity_display', 'seats_available_display'),
            'classes': ('collapse',),
            'description': "Manage seating capacity for different ticket types"
        }),
        ('Pricing', {
            'fields': ('is_free', 'general_price', 'vip_price', 'vvip_price'),
            'classes': ('collapse',),
            'description': "Either mark as free OR provide at least one price tier"
        }),
    )
    
    def status_display(self, obj):
        status = obj.get_status()
        color = {
            'Live': 'green',
            'Upcoming': 'blue',
            'Ended': 'gray',
            'Cancelled': 'red'
        }.get(status, 'black')
        return format_html('<span style="color: {}">{}</span>', color, status)
    status_display.short_description = 'Status'
    
    def price_display(self, obj):
        if obj.is_free:
            return format_html('<span style="color: green">Free</span>')
        return obj.get_price_display()
    price_display.short_description = 'Price'

    def capacity_display(self, obj):
        return format_html(
            'Total: {}<br>General: {}<br>VIP: {}<br>VVIP: {}',
            obj.total_capacity,
            obj.general_seats,
            obj.vip_seats,
            obj.vvip_seats
        )
    capacity_display.short_description = 'Capacity Allocation'
    capacity_display.allow_tags = True
    
    def seats_available_display(self, obj):
        return format_html(
            'General: {}<br>VIP: {}<br>VVIP: {}<br>Total: {}',
            obj.get_available_seats('general'),
            obj.get_available_seats('vip'),
            obj.get_available_seats('vvip'),
            obj.get_available_seats()
        )
    seats_available_display.short_description = 'Seats Available'
    seats_available_display.allow_tags = True
    
    def save_model(self, request, obj, form, change):
    # Existing price handling
        if obj.is_free:
            obj.general_price = 0
            obj.vip_price = None
            obj.vvip_price = None
        
        is_new = obj.pk is None
        super().save_model(request, obj, form, change)

        # Only notify for new events (remove the updated event notification)
        if is_new:
            # 1. Get users with preference for this event category
            from users.models import UserEventPreference
            interested_users = UserEventPreference.objects.filter(
                category=obj.category,
                interest_score__gte=1.0  # Only users who attended at least one similar event
            ).select_related('user')
            
            # 2. Create notifications and send emails
            for preference in interested_users:
                user = preference.user
                
                # Create in-app notification
                Notification.objects.create(
                    user=user,
                    message=f"New {obj.get_category_display()} event: {obj.name}",
                    url=reverse('event_list')
                )
                
                # Send email notification
                self.send_event_notification_email(user, obj)

    def send_event_notification_email(self, user, event):
        from django.core.mail import send_mail
        from django.conf import settings
        
        subject = f"New event in your favorite category: {event.name}"
        message = f"""
        Hi {user.first_name},
        
        We thought you might be interested in this new {event.get_category_display()} event:
        
        {event.name}
        Location: {event.location}
        Date: {event.start_date_time.strftime('%b %d, %Y')}
        
        Check it out here: {settings.SITE_URL}{reverse('event_list')}
        """
        
        send_mail(
            subject,
            message,
            settings.DEFAULT_FROM_EMAIL,
            [user.email],
            fail_silently=False
        )


# @admin.register(Ticket)
# class TicketAdmin(admin.ModelAdmin):
#     list_display = (
#         'user','event', 'ticket_type', 'checked_in', 'checked_in_method', 'checked_in_time',
#     )
#     list_filter = ('event', 'ticket_type',)
#     search_fields = ('user__email', 'user__first_name', 'user__last_name', 'event__name')
#     fields = ( 'user', 'event', 'ticket_type', 'price')

#     def get_readonly_fields(self, request, obj=None):
#         return self.fields


@admin.register(Ticket)
class TicketAdmin(admin.ModelAdmin):
    list_display = (
        'user', 'event', 'ticket_type', 'attendee_count', 'payment_status', 'checked_in', 'checked_in_method', 'checked_in_time',
    )
    list_filter = ('event', 'ticket_type', 'payment_status', 'checked_in')
    search_fields = ('user__email', 'user__first_name', 'user__last_name', 'event__name')
    fields = ('user', 'event', 'ticket_type', 'price', 'payment_status', 'checked_in', 'checked_in_method', 'checked_in_time')

    actions = ['show_sales', 'show_checked_in', 'export_as_csv']

    def get_readonly_fields(self, request, obj=None):
        return self.fields 

    def show_sales(self, request, queryset):
        sales = queryset.filter(payment_status='completed')
        # You can render a template or export CSV here
        self.message_user(request, f"{sales.count()} tickets sold (completed payment).")
    show_sales.short_description = "Show only ticket sales (paid)"

    def show_checked_in(self, request, queryset):
        checked = queryset.filter(checked_in=True)
        self.message_user(request, f"{checked.count()} tickets checked in.")
    show_checked_in.short_description = "Show only checked-in tickets"

    def export_as_csv(self, request, queryset):
        meta = self.model._meta
        field_names = ['user', 'user_email', 'event', 'ticket_type', 'price', 'payment_status', 'checked_in', 'checked_in_method', 'checked_in_time']
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = f'attachment; filename=tickets_report.csv'
        writer = csv.writer(response)
        writer.writerow(field_names)
        for obj in queryset:
            writer.writerow([
                str(obj.user),
                obj.user.email,
                str(obj.event),
                obj.get_ticket_type_display(),
                obj.price,
                obj.payment_status,
                obj.checked_in,
                obj.checked_in_method,
                obj.checked_in_time,
            ])
        return response
    export_as_csv.short_description = "Export Selected as CSV"

    def attendee_count(self, obj):
        return obj.attendees.count()
    attendee_count.short_description = 'Attendees'

from django.contrib import admin
from django.urls import path
from django.shortcuts import render
from django.db.models import Count, Avg
from users.models import RecommendationFeedback
from django.db.models import Q, Case, When, FloatField

@admin.register(RecommendationFeedback)
class RecommendationFeedbackAdmin(admin.ModelAdmin):
    list_display = ('user', 'event', 'liked', 'feedback_type', 'created_at')
    list_filter = ('liked', 'feedback_type', 'created_at')
    search_fields = ('user__email', 'event__name')
    
    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path('stats/', self.admin_site.admin_view(self.recommendation_stats), name='recommendation_stats'),
        ]
        return custom_urls + urls
    
    def recommendation_stats(self, request):
        # Calculate recommendation success rates
        feedback_stats = (
            RecommendationFeedback.objects
            .values('event__category')
            .annotate(
                total=Count('id'),
                positive=Count('id', filter=Q(liked=True)),
                negative=Count('id', filter=Q(liked=False)),
                success_rate=Avg(Case(When(liked=True, then=1), default=0, output_field=FloatField()))
            )
            .order_by('-success_rate')
        )
        
        context = {
            'feedback_stats': feedback_stats,
            **self.admin_site.each_context(request)
        }
        return render(request, 'admin/recommendation_stats.html', context)
    
from .models import Attendee

@admin.register(Attendee)
class AttendeeAdmin(admin.ModelAdmin):
    list_display = (
        'full_name', 'is_user', 'get_purchaser', 'get_purchaser_email', 'event', 'checked_in', 'checked_in_method', 'checked_in_time'
    )
    list_filter = ('is_user', 'checked_in', 'checked_in_method', 'ticket__event')
    search_fields = ('full_name', 'ticket__user__email', 'ticket__user__first_name', 'ticket__user__last_name', 'ticket__event__name')
    readonly_fields = ('qr_code', 'checked_in', 'checked_in_method', 'checked_in_time')
    actions = ['export_attendees_csv']

    def event(self, obj):
        return obj.ticket.event

    def get_purchaser(self, obj):
        return obj.ticket.user.get_full_name() if obj.ticket and obj.ticket.user else ''
    get_purchaser.short_description = 'Purchased By'

    def get_purchaser_email(self, obj):
        return obj.ticket.user.email if obj.ticket and obj.ticket.user else ''
    get_purchaser_email.short_description = 'Purchaser Email'

    def export_attendees_csv(self, request, queryset):
        field_names = ['full_name', 'is_user', 'get_purchaser', 'get_purchaser_email', 'event', 'checked_in', 'checked_in_method', 'checked_in_time']
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = 'attachment; filename=attendees_report.csv'
        writer = csv.writer(response)
        writer.writerow(field_names)
        for obj in queryset:
            writer.writerow([
                obj.full_name,
                obj.is_user,
                self.get_purchaser(obj),
                self.get_purchaser_email(obj),
                obj.ticket.event,
                obj.checked_in,
                obj.checked_in_method,
                obj.checked_in_time,
            ])
        return response
    export_attendees_csv.short_description = "Export Selected Attendees as CSV"