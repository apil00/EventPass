import base64

def send_ticket_email(user, ticket):
    from django.core.mail import EmailMessage
    from django.template.loader import render_to_string
    from utils.ticket_pdf import generate_ticket_pdf

    # Read QR code image and encode as base64
    qr_code_base64 = ""
    if ticket.qr_code and ticket.qr_code.path:
        with open(ticket.qr_code.path, "rb") as image_file:
            qr_code_base64 = base64.b64encode(image_file.read()).decode('utf-8')

    subject = f"Your Ticket for {ticket.event.name}"
    message = render_to_string('events/email_ticket.html', {
        'user': user,
        'ticket': ticket,
        'qr_code_base64': qr_code_base64,
    })
    email = EmailMessage(subject, message, to=[user.email])
    email.content_subtype = "html"

    # Attach PDF with QR code
    pdf_buffer = generate_ticket_pdf(ticket)
    email.attach(f"EventPass_Ticket_{ticket.id}.pdf", pdf_buffer.getvalue(), 'application/pdf')
    pdf_buffer.close()
    email.send()

# To get recommended events for a user based on their preferences

from django.utils import timezone
from events.models import Event
from users.models import UserEventPreference

def get_recommended_events(user, limit=5):
    """
    Get events recommended for a user based on their attendance history
    """
    # Get user's preferred categories ordered by interest
    preferences = UserEventPreference.objects.filter(user=user).order_by('-interest_score')
    
    if not preferences.exists():
        # If no preferences yet, return featured upcoming events
        return Event.objects.filter(
            start_date_time__gte=timezone.now(),
            is_featured=True
        ).order_by('start_date_time')[:limit]
    
    # Get events from preferred categories
    preferred_categories = [p.category for p in preferences]
    
    return Event.objects.filter(
        category__in=preferred_categories,
        start_date_time__gte=timezone.now()
    ).exclude(
        # Exclude events user already has tickets for
        tickets__user=user,
        tickets__payment_status='completed'
    ).order_by('start_date_time')[:limit]

