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
    
    now = timezone.now()
    # Get upcoming events (start_date_time > now)
    upcoming_events = Event.objects.filter(start_date_time__gt=now).order_by('start_date_time')
    # Get live and ended events (start_date_time <= now)
    live_ended_events = Event.objects.filter(start_date_time__lte=now).order_by('-start_date_time')
    return render(request, 'events/event_list.html', {'upcoming_events': upcoming_events,'live_ended_events': live_ended_events, 'events': list(upcoming_events) + list(live_ended_events),})

@login_required
def ticket_booking(request, event_id):
    event = get_object_or_404(Event, pk=event_id)

    # check if event has ended
    if event.get_status() == 'Ended':
        messages.error(request, "This event has already ended.")
        return redirect('event_list')
    
    # Handle ticket type selection
    if request.method == 'POST':
        ticket_type = request.POST.get('ticket_type')
        if not ticket_type:
            messages.error(request, "Please select a ticket type")
            return render(request, 'events/ticket_booking.html', {'event': event})
        
        request.session['selected_ticket_type'] = ticket_type
        return redirect('confirm_ticket', event_id=event_id)
    

    return render(request, 'events/ticket_booking.html', {'event': event})

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
    selected_ticket_type = request.session.get('selected_ticket_type')

    # validate ticket type
    if  not selected_ticket_type:
        messages.error(request, "Please select a ticket type first.")
        return redirect('ticket_booking', event_id=event_id)
    
    # In confirm_ticket view:
    price_tiers = dict((k.lower(), v) for k, v in event.get_price_tiers())

    if selected_ticket_type not in price_tiers:
        messages.error(request, "Invalid ticket type selected.")
        return redirect('ticket_booking', event_id=event_id)
    
    price = price_tiers[selected_ticket_type]

    # Remove any previous pending/failed ticket for this user and event
    Ticket.objects.filter(user=request.user, event=event).exclude(payment_status='completed').delete()

    # Prevent duplicate ticket for the same user and event
    if Ticket.objects.filter(user=request.user, event=event, payment_status='completed').exists():
        messages.error(request, "You have already purchased a ticket for this event.")
        return redirect('event_list')

    # Create ticket in PENDING state before payment
    ticket = Ticket.objects.create(
        user=request.user,
        event=event,
        ticket_type=selected_ticket_type,
        price=price,
        payment_method='esewa',
        payment_status='pending'
    )

    # Prepare payment data for both GET and POST requests
    transaction_uuid = str(uuid.uuid4())
    payment_data = {
        'amount': str(price),
        'tax_amount': '0',
        'total_amount': str(price),
        'transaction_uuid': transaction_uuid,
        'product_code': ESEWA_CONFIG['merchant_code'],
        'product_service_charge': '0',
        'product_delivery_charge': '0',
        'success_url': request.build_absolute_uri(reverse('esewa_success')),
        'failure_url': request.build_absolute_uri(reverse('esewa_failure')),
        'signed_field_names': 'total_amount,transaction_uuid,product_code',
    }
    payment_data['signature'] = generate_esewa_signature(payment_data)

    # Store ticket ID in session for later retrieval
    request.session['current_ticket_id'] = ticket.id
    request.session['current_transaction'] = {
        'event_id': event_id,
        'ticket_type': selected_ticket_type,
        'price': str(price),
        'transaction_uuid': transaction_uuid,
    }

    context = {
        'event': event,
        'type': selected_ticket_type.title(),
        'price': price,
        'payment_data': payment_data,
    }

    # Handle payment submission
    if request.method == 'POST':
        # Render the payment form with auto-submit
        return render(request, 'events/esewa_payment.html', {
            'payment_data': payment_data,
            'esewa_url': ESEWA_CONFIG['test_url'],
        })

    return render(request, 'events/confirm_ticket.html', context)



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
        # Remove commas before converting to float
        received_amount = payment_data.get('total_amount', '0').replace(',', '')
        ticket_price = str(ticket.price).replace(',', '')  # Just in case ticket price also has commas

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
        #print(f"Ticket {ticket_id} marked as completed")

        send_ticket_email(request.user, ticket)
        
        Notification.objects.create(
        user=request.user,
        message=f"Your payment for {ticket.event.name} was successful! Your ticket is ready.",
        url=reverse('ticket_detail', args=[ticket.id])
    )

        # Clear session
        request.session.pop('current_ticket_id', None)
        request.session.pop('current_transaction', None)

        return render(request, 'events/payment_success.html', {
            'ticket': ticket,
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
    
    return render(request, 'events/my_tickets.html', {'tickets': tickets})

# -- Ticket detail view --
@login_required
def ticket_detail(request, ticket_id):
    ticket = get_object_or_404(Ticket, pk=ticket_id, user=request.user)
    if ticket.payment_status != 'completed':
        messages.error(request, "Ticket is not available until payment is completed.")
        return redirect('event_list')
    return render(request, 'events/ticket_detail.html', {'ticket': ticket})

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