# events/views.py
from django.shortcuts import render, get_object_or_404, redirect
from events.utils import send_ticket_email
from .models import Event, Ticket
from django.contrib import messages
import uuid
import base64
import hmac, hashlib
from django.conf import settings
from django.urls import reverse
import json
from django.contrib.auth.decorators import login_required
from django.utils import timezone
from django.http import HttpResponse
from utils.ticket_pdf import generate_ticket_pdf
import logging
from users.models import Notification
from django.views.decorators.http import require_POST
from django.http import JsonResponse
from .models import Event
from users.models import RecommendationFeedback, UserEventPreference
from django.db.models import F
from .recommendations import EventRecommender


logger = logging.getLogger(__name__)


@require_POST
@login_required
def track_recommendation_feedback(request, event_id):
    event = get_object_or_404(Event, pk=event_id)
    action = request.POST.get('action')
    
    if action in ['click', 'purchase', 'dismiss']:
        liked = action in ['click', 'purchase']
        
        # Update or create feedback
        feedback, created = RecommendationFeedback.objects.update_or_create(
            user=request.user,
            event=event,
            defaults={
                'liked': liked,
                'feedback_type': action
            }
        )
        
        # Update user preferences based on feedback
        if action == 'purchase':
            # Already handled by ticket signal
            pass
        elif action == 'click':
            # Moderate positive reinforcement
            UserEventPreference.objects.update_or_create(
                user=request.user,
                category=event.category,
                defaults={
                    'interest_score': 0.5,
                    'interactions_count': 1
                }
            )
        elif action == 'dismiss':
            # Negative feedback - reduce interest
            UserEventPreference.objects.filter(
                user=request.user,
                category=event.category
            ).update(interest_score=F('interest_score') * 0.7)
        
        return JsonResponse({'status': 'success'})
    
    return JsonResponse({'status': 'error', 'message': 'Invalid action'}, status=400)

@login_required
def recommended_events(request):
    recommender = EventRecommender(request.user)
    recommended_events = recommender.get_recommendations(limit=20)
    
    return render(request, 'events/recommended_events.html', {
        'recommended_events': recommended_events,
        'recommendation_strategy': recommender.get_strategy_explanation()
    })

@login_required
def event_list(request):
    if not request.user.face_registered:
        messages.info(request, "Please register your face before viewing events")
        return redirect('capture_face')
    
    notifications = request.user.notifications.filter(is_read=False).order_by('-created_at')[:5]
    
    now = timezone.now()
    # Get upcoming events (start_date_time > now)
    upcoming_events = Event.objects.filter(start_date_time__gt=now).order_by('start_date_time')
    # Get live and ended events (start_date_time <= now)
    live_ended_events = Event.objects.filter(start_date_time__lte=now).order_by('-start_date_time')
    return render(request, 'events/event_list.html', {'upcoming_events': upcoming_events,'live_ended_events': live_ended_events, 'events': list(upcoming_events) + list(live_ended_events), 'notifications': notifications})

from .forms import MultiTicketBookingForm
@login_required
def ticket_booking(request, event_id):
    event = get_object_or_404(Event, pk=event_id)
    notifications = request.user.notifications.filter(is_read=False).order_by('-created_at')[:5]
    if request.method == 'POST':
        form = MultiTicketBookingForm(request.POST)
        if form.is_valid():
            ticket_type = form.cleaned_data['ticket_type']
            for_self = form.cleaned_data['for_self']
            for_others = form.cleaned_data['for_others']
            others_quantity = form.cleaned_data['others_quantity'] if form.cleaned_data['for_others'] else 0

            if not for_self and not for_others:
                form.add_error(None, "Select at least one: For Myself or For Others")
            elif for_others and not others_quantity:
                form.add_error('others_quantity', "Specify number of guests")
            else:
                request.session['booking'] = {
                    'ticket_type': ticket_type,
                    'for_self': for_self,
                    'for_others': for_others,
                    'others_quantity': others_quantity or 0,
                }
                # If guests, go to guest face registration
                if for_others and others_quantity:
                    return redirect('register_guest_faces', event_id=event_id)
                # If only self, go to confirm
                return redirect('confirm_ticket', event_id=event_id)
    else:
        form = MultiTicketBookingForm()
    return render(request, 'events/ticket_booking.html', {'event': event, 'form': form, 'notifications': notifications})

import base64
import numpy as np
import face_recognition
from PIL import Image
import io

@login_required
def register_guest_faces(request, event_id):
    booking = request.session.get('booking')
    if not booking or not booking.get('for_others'):
        return redirect('ticket_booking', event_id=event_id)
    guest_count = booking.get('others_quantity', 0)
    if request.method == 'POST':
        guest_data = []
        for i in range(guest_count):
            name = request.POST.get(f'guest_name_{i}')
            face_data = request.POST.get(f'face_{i}')
            embedding = None
            if face_data and ',' in face_data:
                image_data = face_data.split(',')[1]
                image_bytes = base64.b64decode(image_data)
                image = Image.open(io.BytesIO(image_bytes)).convert('RGB')
                image_array = np.array(image)
                embeddings = face_recognition.face_encodings(image_array)
                if embeddings:
                    embedding = embeddings[0].tolist()
            guest_data.append({
                'full_name': name,
                'face_embedding': embedding,
            })
        request.session['guest_data'] = guest_data
        return redirect('confirm_ticket', event_id=event_id)
    forms = [{'index': i} for i in range(guest_count)]
    return render(request, 'events/register_guest_faces.html', {'forms': forms, 'guest_count': guest_count})

# -- eSewa payment configuration--
ESEWA_CONFIG = {
    'merchant_code': 'EPAYTEST',
    'secret_key': '8gBm/:&EnhH.1/q',
    'success_url': settings.ESEWA_SUCCESS_URL,
    'failure_url': settings.ESEWA_FAILURE_URL,
    'test_url': 'https://rc-epay.esewa.com.np/api/epay/main/v2/form'
}

def generate_esewa_signature(data):
    message = f"total_amount={data['total_amount']}," \
              f"transaction_uuid={data['transaction_uuid']}," \
              f"product_code={data['product_code']}"
    
    signature = hmac.new(
        ESEWA_CONFIG['secret_key'].encode('utf-8'),
        message.encode('utf-8'),
        hashlib.sha256
    ).digest()

    return base64.b64encode(signature).decode('utf-8')

@login_required
def confirm_ticket(request, event_id):
    event = get_object_or_404(Event, pk=event_id)
    booking = request.session.get('booking')
    if not booking:
        return redirect('ticket_booking', event_id=event_id)

    ticket_type = booking['ticket_type']
    for_self = booking['for_self']
    for_others = booking['for_others']
    others_quantity = booking['others_quantity']

    price_tiers = dict((k.lower(), v) for k, v in event.get_price_tiers())
    price = price_tiers[ticket_type]
    total_tickets = (1 if for_self else 0) + (others_quantity if for_others else 0)
    total_price = price * total_tickets

    # Prepare attendee preview
    attendees = []
    if for_self:
        attendees.append({
            'full_name': request.user.get_full_name(),
            'is_user': True,
        })
    if for_others and others_quantity:
        guest_data = request.session.get('guest_data', [])
        for guest in guest_data:
            attendees.append({
                'full_name': guest['full_name'],
                'is_user': False,
            })

    if request.method == 'POST':
        # Create Ticket (purchase)
        ticket = Ticket.objects.create(
            user=request.user,
            event=event,
            ticket_type=ticket_type,
            price=total_price,
            payment_method='esewa',
            payment_status='pending'
        )
        request.session['current_ticket_id'] = ticket.id
        request.session['attendee_info'] = {
            'for_self': for_self,
            'for_others': for_others,
            'others_quantity': others_quantity,
        }

        # Prepare eSewa payment data
        import uuid
        from django.urls import reverse
        transaction_uuid = str(uuid.uuid4())
        payment_data = {
            'amount': str(total_price),
            'tax_amount': '0',
            'total_amount': str(total_price),
            'transaction_uuid': transaction_uuid,
            'product_code': ESEWA_CONFIG['merchant_code'],
            'product_service_charge': '0',
            'product_delivery_charge': '0',
            'success_url': request.build_absolute_uri(reverse('esewa_success')),
            'failure_url': request.build_absolute_uri(reverse('esewa_failure')),
            'signed_field_names': 'total_amount,transaction_uuid,product_code',
        }
        payment_data['signature'] = generate_esewa_signature(payment_data)

        # Store transaction in session for later verification
        request.session['current_transaction'] = {
            'event_id': event_id,
            'ticket_type': ticket_type,
            'price': str(total_price),
            'transaction_uuid': transaction_uuid,
        }

        # Render the eSewa payment form (auto-submit)
        return render(request, 'events/esewa_payment.html', {
            'payment_data': payment_data,
            'esewa_url': ESEWA_CONFIG['test_url'],
        })

    context = {
        'event': event,
        'type': ticket_type.title(),
        'price': price,
        'total_tickets': total_tickets,
        'total_price': total_price,
        'attendees': attendees,
    }
    return render(request, 'events/confirm_ticket.html', context)


from .models import Attendee
@login_required
def esewa_payment_success(request):
    # Handle both GET and POST
    payment_data = {}
    if request.method == 'GET' and 'data' in request.GET:
        try:
            decoded = base64.b64decode(request.GET['data']).decode('utf-8')
            payment_data = json.loads(decoded)
            print(f"Decoded payment data: {payment_data}")
        except Exception as e:
            print(f"Error decoding payment data: {str(e)}")
            messages.error(request, "Invalid payment data")
            return redirect('event_list')
    elif request.method == 'POST':
        payment_data = request.POST.dict()
    else:
        return redirect('event_list')

    # Verify required fields
    required_fields = ['transaction_uuid', 'total_amount', 'status']
    if not all(field in payment_data for field in required_fields):
        print("Missing required payment fields")
        return redirect('event_list')

    # Verify payment status
    if payment_data.get('status') != 'COMPLETE':
        print(f"Payment not completed. Status: {payment_data.get('status')}")
        return redirect('event_list')

    # Get ticket from session
    ticket_id = request.session.get('current_ticket_id')
    if not ticket_id:
        print("No ticket_id in session")
        messages.error(request, "Session expired. Please check your tickets.")
        return redirect('event_list')

    try:
        ticket = Ticket.objects.get(id=ticket_id)
        
        # Verify payment amount
        received_amount = payment_data.get('total_amount', '0').replace(',', '')
        ticket_price = str(ticket.price).replace(',', '')

        if float(received_amount) != float(ticket_price):
            print(f"Amount mismatch: {received_amount} vs {ticket_price}")
            messages.error(request, "Payment verification failed")
            return redirect('event_list')

        # Update ticket
        ticket.payment_status = 'completed'
        ticket.payment_completed = True
        ticket.payment_details = {
            'transaction_id': payment_data.get('transaction_uuid'),
            'amount': payment_data.get('total_amount'),
            'product_code': payment_data.get('product_code'),
            'raw_response': payment_data
        }
        ticket.save()

        # --- NEW: Create Attendees for self and guests ---
        attendee_info = request.session.get('attendee_info', {})
        for_self = attendee_info.get('for_self')
        for_others = attendee_info.get('for_others')
        others_quantity = attendee_info.get('others_quantity', 0)

        created_attendees = []

        # For self
        if for_self:
            created_attendees.append(
                Attendee.objects.create(
                    ticket=ticket,
                    full_name=request.user.get_full_name(),
                    is_user=True,
                    user=request.user,
                    qr_code_value=str(uuid.uuid4()),
                )
            )

        # For guests
        if for_others and others_quantity > 0:
            guest_data = request.session.get('guest_data', [])
            for guest in guest_data:
                created_attendees.append(
                    Attendee.objects.create(
                        ticket=ticket,
                        full_name=guest['full_name'],
                        is_user=False,
                        face_embedding=guest['face_embedding'],
                        qr_code_value=str(uuid.uuid4()),
                    )
                )

        # --- END NEW ---

        send_ticket_email(request.user, ticket)
        
        Notification.objects.create(
            user=request.user,
            message=f"Your payment for {ticket.event.name} was successful! Your ticket is ready.",
            url=reverse('ticket_detail', args=[ticket.id])
        )

        # Clear session
        for key in ['current_ticket_id', 'current_transaction', 'attendee_info', 'guest_data', 'booking']:
            if key in request.session:
                del request.session[key]

        return render(request, 'events/payment_success.html', {
            'ticket': ticket,
            'attendees': created_attendees,
            'transaction_uuid': payment_data.get('transaction_uuid'),
            'amount': payment_data.get('total_amount')
        })

    except Ticket.DoesNotExist:
        print(f"Ticket {ticket_id} not found")
        messages.error(request, "Ticket not found")
        return redirect('event_list')

@login_required
def esewa_payment_failure(request):
    failure_reason = "Unknown error"
    if request.method == 'POST':
        failure_reason = request.POST.get('reason', 'Unknown error')
    elif request.method == 'GET':
        failure_reason = request.GET.get('reason', 'Unknown error')
    
    ticket_id = request.session.get('current_ticket_id')
    if ticket_id:
        try:
            ticket = Ticket.objects.get(id=ticket_id)
            ticket.payment_status = 'failed'
            ticket.payment_details = {
                'failure_reason': failure_reason,
                'esewa_response': dict(request.POST.items() if request.method == 'POST' else request.GET.items())
            }
            ticket.save()

            Notification.objects.create(
            user=request.user,
            message=f"Your payment for {ticket.event.name} failed or was canceled. Reason: {failure_reason}",
            url=reverse('event_list')
        )
            
            # Clear session data
            request.session.pop('current_ticket_id', None)
            request.session.pop('current_transaction', None)
        except Ticket.DoesNotExist:
            pass
    
    messages.error(request, f"Payment failed: {failure_reason}")
    return render(request, 'events/payment_failed.html')

#################
#################

# -- Ticket list view --
@login_required
def my_tickets(request):
    notifications = request.user.notifications.filter(is_read=False).order_by('-created_at')[:5]
    # Get all tickets for the current user, ordered by event date
    tickets = Ticket.objects.filter(user=request.user, payment_status='completed').order_by('-event__start_date_time')
    
    # Categorize tickets by status
    now = timezone.now()
    for ticket in tickets:
        if ticket.event.end_date_time < now:
            ticket.status = 'ended'
        elif ticket.event.start_date_time > now:
            ticket.status = 'upcoming'
        else:
            ticket.status = 'active'
        ticket.attendees_list = ticket.attendees.all()
    return render(request, 'events/my_tickets.html', {'tickets': tickets, 'notifications': notifications})

# -- Ticket detail view --
@login_required
def ticket_detail(request, ticket_id):
    notifications = request.user.notifications.filter(is_read=False).order_by('-created_at')[:5]
    ticket = get_object_or_404(Ticket, pk=ticket_id, user=request.user)
    if ticket.payment_status != 'completed':
        messages.error(request, "Ticket is not available until payment is completed.")
        return redirect('event_list')
    attendees = ticket.attendees.all()
    return render(request, 'events/ticket_detail.html', {'ticket': ticket, 'attendees': attendees, 'notifications': notifications})

def download_ticket(request, ticket_id):
    ticket = get_object_or_404(Ticket, pk=ticket_id, user=request.user)
    if ticket.payment_status != 'completed':
        messages.error(request, "Ticket is not available until payment is completed.")
        return redirect('event_list')
    
    # Generate PDF
    buffer = generate_ticket_pdf(ticket)
    
    # Create response
    response = HttpResponse(content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="EventPass_Ticket_{ticket.id}.pdf"'
    response.write(buffer.getvalue())
    buffer.close()
    
    return response


from datetime import timedelta

def send_event_reminders():
    now = timezone.now()
    soon = now + timedelta(hours=24)
    tickets = Ticket.objects.filter(
        event__start_date_time__range=(now, soon),
        payment_status='completed'
    )
    for ticket in tickets:
        # Check if a reminder was already sent (optional: add a flag in Ticket or Notification)
        if not Notification.objects.filter(
            user=ticket.user,
            message__icontains=f"reminder for {ticket.event.name}",
            url__icontains=str(ticket.event.id)
        ).exists():
            Notification.objects.create(
                user=ticket.user,
                message=f"Reminder: The event '{ticket.event.name}' starts on {ticket.event.start_date_time.strftime('%b %d, %Y at %I:%M %p')}.",
                url=reverse('event_list')
            )