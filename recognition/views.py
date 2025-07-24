# recognition/views.py
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
from events.models import Ticket, Event
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

        # Compare with stored embeddings
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
            ticket = Ticket.objects.filter(
                user=recognized_user,
                event_id=event_id,
                payment_status='completed'
            ).first()
            if ticket:
                if ticket.checked_in:
                    return JsonResponse({
                        'status': 'error',
                        'message': 'Ticket already used!',
                        'detected_face': detected_face_base64
                    })
                ticket.checked_in = True
                ticket.checked_in_method = 'face'
                ticket.checked_in_time = timezone.now()
                ticket.save()
                return JsonResponse({
                    'status': 'success',
                    'message': f'Recognized as {recognized_user.get_full_name()}',
                    'detected_face': detected_face_base64,
                    'user_details': {
                        'full_name': recognized_user.get_full_name(),
                        'email': recognized_user.email,
                    },
                    'event_details': {
                        'name': ticket.event.name,
                        'date': ticket.event.start_date_time.strftime('%Y-%m-%d'),
                        'location': ticket.event.location,
                    },
                    'ticket_status': 'Valid'
                })
            else:
                return JsonResponse({
                    'status': 'error',
                    'message': 'No valid ticket for this event',
                    'detected_face': detected_face_base64
                })
        else:
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
        try:
            ticket = Ticket.objects.get(qr_code_value=qr_code, event_id=event_id, payment_status='completed')
            if ticket.checked_in:
                return JsonResponse({'status': 'error', 'message': 'Ticket already used!'})
            ticket.checked_in = True
            ticket.checked_in_method = 'qr'
            ticket.checked_in_time = timezone.now()
            ticket.save()

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
        except Ticket.DoesNotExist:
            return JsonResponse({'status': 'error', 'message': 'Invalid or already used QR code!'})
    return JsonResponse({'status': 'error', 'message': 'Invalid request'})