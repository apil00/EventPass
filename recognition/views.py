from django.shortcuts import render, redirect
from django.http import JsonResponse
import cv2
import face_recognition
import numpy as np
from PIL import Image
import io
import base64
import os
from users.models import FaceEmbedding
from events.models import Ticket, Event, Attendee
from users.models import CustomUser
from django.utils import timezone

# Path to Haar Cascade using OpenCV's data directory
HAAR_CASCADE_PATH = os.path.join(cv2.data.haarcascades, 'haarcascade_frontalface_default.xml')
face_cascade = cv2.CascadeClassifier(HAAR_CASCADE_PATH)

def select_event(request):
    now = timezone.now()
    events = Event.objects.filter(end_date_time__gte=now).order_by('start_date_time')
    return render(request, 'recognition/select_event.html', {'events': events})

def recognize(request):
    if request.method == 'POST':
        event_id = request.POST.get('event_id')
        if not event_id:
            return JsonResponse({'status': 'error', 'message': 'Event ID not provided'})

        # Decode base64 image
        image_data = request.POST.get('image')
        if not image_data:
            return JsonResponse({'status': 'error', 'message': 'No image data provided'})
        try:
            image_data = image_data.split(',')[1]
            image_bytes = base64.b64decode(image_data)
            image = Image.open(io.BytesIO(image_bytes)).convert('RGB')
            image_array = np.array(image)
        except Exception as e:
            return JsonResponse({'status': 'error', 'message': f'Image decode error: {str(e)}'})

        # Convert RGB to BGR for OpenCV
        image_bgr = cv2.cvtColor(image_array, cv2.COLOR_RGB2BGR)
        gray = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2GRAY)

        # Detect faces using Haar Cascade
        faces = face_cascade.detectMultiScale(gray, scaleFactor=1.1, minNeighbors=5, minSize=(30, 30))
        if len(faces) != 1:
            return JsonResponse({'status': 'error', 'message': 'Exactly one face should be detected'})

        (x, y, w, h) = faces[0]
        cv2.rectangle(image_bgr, (x, y), (x+w, y+h), (0, 255, 0), 2)
        image_rgb = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2RGB)
        detected_face = Image.fromarray(image_rgb)
        buffered = io.BytesIO()
        detected_face.save(buffered, format="JPEG")
        detected_face_base64 = base64.b64encode(buffered.getvalue()).decode('utf-8')

        # Get embedding using face_recognition
        embeddings = face_recognition.face_encodings(image_array, [(y, x+w, y+h, x)])
        if not embeddings:
            return JsonResponse({'status': 'error', 'message': 'Could not generate face embedding', 'detected_face': detected_face_base64})

        input_embedding = embeddings[0]

        # 1. Try to match with registered users (FaceEmbedding)
        all_embeddings = FaceEmbedding.objects.all()
        min_distance = float('inf')
        recognized_user = None

        for emb in all_embeddings:
            stored_embedding = np.array(emb.embedding)
            distance = np.linalg.norm(input_embedding - stored_embedding)
            if distance < min_distance and distance < 0.6:  # Threshold for recognition
                min_distance = distance
                recognized_user = emb.user

        if recognized_user:
            # Find attendee for this user and event
            attendee = Attendee.objects.filter(
                ticket__event_id=event_id,
                is_user=True,
                user=recognized_user
            ).first()
            if attendee:
                if attendee.checked_in:
                    return JsonResponse({
                        'status': 'error',
                        'message': 'Ticket already used!',
                        'detected_face': detected_face_base64
                    })
                attendee.checked_in = True
                attendee.checked_in_method = 'face'
                attendee.checked_in_time = timezone.now()
                attendee.save()
                return JsonResponse({
                    'status': 'success',
                    'message': f'Recognized as {recognized_user.get_full_name()}',
                    'user_details': {
                        'full_name': recognized_user.get_full_name(),
                        'email': recognized_user.email,
                        'photo': '',  # Optionally add profile photo
                    },
                    'event_details': {
                        'name': attendee.ticket.event.name,
                        'date': attendee.ticket.event.start_date_time.strftime('%Y-%m-%d'),
                        'location': attendee.ticket.event.location,
                    },
                    'ticket_status': 'Valid',
                    'detected_face': detected_face_base64
                })
            else:
                return JsonResponse({
                    'status': 'error',
                    'message': 'No valid attendee record for this event',
                    'detected_face': detected_face_base64
                })
        else:
            # 2. Try to match with guests (Attendee with face_embedding)
            attendees = Attendee.objects.filter(
                ticket__event_id=event_id,
                checked_in=False,
                is_user=False,
                face_embedding__isnull=False
            )
            for attendee in attendees:
                guest_embedding = np.array(attendee.face_embedding)
                distance = np.linalg.norm(input_embedding - guest_embedding)
                if distance < 0.6:  # Same threshold
                    # Mark as checked in and delete face embedding
                    attendee.checked_in = True
                    attendee.checked_in_method = 'face'
                    attendee.checked_in_time = timezone.now()
                    attendee.face_embedding = None
                    attendee.save()
                    return JsonResponse({
                        'status': 'success',
                        'message': f'Guest recognized: {attendee.full_name}',
                        'user_details': {
                            'full_name': attendee.full_name,
                            'email': attendee.ticket.user.email if attendee.ticket and attendee.ticket.user else '',
                            'purchased_by': attendee.ticket.user.get_full_name() if attendee.ticket and attendee.ticket.user else '',
                        },
                        'event_details': {
                            'name': attendee.ticket.event.name,
                            'date': attendee.ticket.event.start_date_time.strftime('%Y-%m-%d'),
                            'location': attendee.ticket.event.location,
                        },
                        'ticket_status': 'Valid',
                        'detected_face': detected_face_base64
                    })
            # If no match found
            return JsonResponse({
                'status': 'error',
                'message': 'Face not recognized',
                'detected_face': detected_face_base64
            })

    # For GET, render the recognition page and pass event_id and event_name
    else:
        event_id = request.GET.get('event_id')
        if not event_id:
            return redirect('select_event')
        try:
            event = Event.objects.get(id=event_id)
            event_name = event.name
        except Event.DoesNotExist:
            return redirect('select_event')
        return render(request, 'recognition/recognize.html', {'event_id': event_id, 'event_name': event_name})

def qr_checkin(request):
    if request.method == 'POST':
        qr_code = request.POST.get('qr_code')
        event_id = request.POST.get('event_id')
        # 1. Try user ticket QR (legacy, for backward compatibility)
        ticket = Ticket.objects.filter(qr_code_value=qr_code, event_id=event_id, payment_status='completed').first()
        if ticket:
            # Find attendee for this user and event
            attendee = Attendee.objects.filter(ticket=ticket, is_user=True, user=ticket.user).first()
            if attendee:
                if attendee.checked_in:
                    return JsonResponse({'status': 'error', 'message': 'Ticket already used!'})
                attendee.checked_in = True
                attendee.checked_in_method = 'qr'
                attendee.checked_in_time = timezone.now()
                attendee.save()
                # Get user's profile picture if exists
                encoded_photo = None
                if ticket.user.profile_picture:
                    try:
                        with ticket.user.profile_picture.open('rb') as image_file:
                            encoded_photo = base64.b64encode(image_file.read()).decode('utf-8')
                    except Exception as e:
                        print(f"Error processing profile picture: {e}")
                return JsonResponse({
                    'status': 'success',
                    'message': 'Entry Granted!',
                    'user_details': {
                        'full_name': ticket.user.get_full_name(),
                        'email': ticket.user.email,
                        'profile_picture': encoded_photo
                    },
                    'event_details': {
                        'name': ticket.event.name,
                        'date': ticket.event.start_date_time.strftime('%Y-%m-%d'),
                        'location': ticket.event.location,
                    },
                    'ticket_status': 'Valid'
                })
            else:
                return JsonResponse({'status': 'error', 'message': 'No attendee record found for this ticket!'})
        else:
            # 2. Try attendee QR (user or guest)
            attendee = Attendee.objects.filter(qr_code_value=qr_code, ticket__event_id=event_id).first()
            if attendee:
                if attendee.checked_in:
                    return JsonResponse({'status': 'error', 'message': 'Ticket already used!'})
                attendee.checked_in = True
                attendee.checked_in_method = 'qr'
                attendee.checked_in_time = timezone.now()
                if not attendee.is_user:
                    attendee.face_embedding = None
                attendee.save()
                return JsonResponse({
                    'status': 'success',
                    'message': 'Entry Granted!',
                    'user_details': {
                        'full_name': attendee.full_name,
                        'email': attendee.ticket.user.email if attendee.ticket and attendee.ticket.user else '',
                        'purchased_by': attendee.ticket.user.get_full_name() if attendee.ticket and attendee.ticket.user else '',
                        'profile_picture': '',  # You can add if you want
                    },
                    'event_details': {
                        'name': attendee.ticket.event.name,
                        'date': attendee.ticket.event.start_date_time.strftime('%Y-%m-%d'),
                        'location': attendee.ticket.event.location,
                    },
                    'ticket_status': 'Valid'
                })
            else:
                return JsonResponse({'status': 'error', 'message': 'Invalid or already used QR code!'})
    return JsonResponse({'status': 'error', 'message': 'Invalid request'})