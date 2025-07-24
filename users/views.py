# users/ views.py

from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from .forms import UserRegisterForm
from django.contrib import messages
from events.models import Event
from django.utils import timezone
from .forms import ProfileUpdateForm
from .models import Announcement
from django.urls import reverse
from django.core.mail import send_mail
from django.conf import settings
from .models import CustomUser
from django.views.decorators.http import require_POST
from events.utils import get_recommended_events

def user_signup_view(request):
    if request.method == 'POST':
        form = UserRegisterForm(request.POST, request.FILES)
        if form.is_valid():
            user = form.save(commit=False)
            user.is_active = False
            form.save()
            token = user.generate_email_verification_token()
            verification_link = request.build_absolute_uri(
                reverse('verify_email', args=[token])
            )

            subject = 'Verify your email address'

            message = f"""
                Hi {user.first_name},
                
                Please click the following link to verify your email address:
                {verification_link}
                
                If you didn't create an account, you can safely ignore this email.
                """
            send_mail(
                subject,
                message,
                settings.DEFAULT_FROM_EMAIL,
                [user.email],
                fail_silently=False,
            )
            messages.success(request, 'Account created! Please check your email to verify your account.')
            return redirect('login') 
        else:
            print("Form errors:", form.errors)  
    else:
        form = UserRegisterForm()      
    return render(request,'users/user_register.html', {'form': form})

@require_POST
def resend_verification_email(request):
    email = request.POST.get('email')
    try:
        user = CustomUser.objects.get(email=email)
        if user.is_email_verified:
            messages.info(request, 'Your email is already verified.')
        else:
            token = user.generate_email_verification_token()
            verification_link = request.build_absolute_uri(
                reverse('verify_email', args=[token])
            )
            subject = 'Verify your email address'
            message = f"""
                Hi {user.first_name},

                Please click the following link to verify your email address:
                {verification_link}

                If you didn't create an account, you can safely ignore this email.
                EventPass Team
                """
            send_mail(
                subject,
                message,
                settings.DEFAULT_FROM_EMAIL,
                [user.email],
                fail_silently=False,
            )
            messages.success(request, 'Verification email resent! Please check your inbox.')
    except CustomUser.DoesNotExist:
        messages.error(request, 'No account found with that email.')
    return redirect('login')

def verify_email(request, token):
    try:
        user = CustomUser.objects.get(email_verification_token=token)
        user.is_active = True
        user.is_email_verified = True
        user.email_verification_token = None
        user.save()
        messages.success(request, 'Email verified! You can now log in.')
        return redirect('login')
    except CustomUser.DoesNotExist:
        messages.error(request, 'Invalid or expired verification link.')
        return redirect('login')


def user_login_view(request):
    logout(request)
    if request.method == 'POST':
        email = request.POST.get('email')
        password = request.POST.get('password')
        user = authenticate(request, email=email, password=password)
        if user is not None:
            if not user.is_active or not user.is_email_verified:
                messages.error(request, 'Please verify your email before logging in.')
                return render(request, 'users/user_login.html', {'show_resend_verification': True, 'email': email})
            
            login(request, user)
                
            return redirect('user_dashboard')
        else:
            messages.info(request, 'Invalid email or password')
    return render(request, 'users/user_login.html')

@login_required
def user_dashboard_view(request):
    face_registered = request.user.face_registered
    if not face_registered:
        messages.info(request, "Please register your face to access all features")

    user = request.user
    
    # Get upcoming events through tickets (distinct events)
    upcoming_events = Event.objects.filter(
        tickets__user=user,
        start_date_time__gte=timezone.now()
    ).distinct().order_by('start_date_time')[:5]  # Get first 5 upcoming

    # Calculate stats
    upcoming_events_count = upcoming_events.count()  # Reuse the same queryset
    booked_events_count = user.tickets.count()
    attended_events_count = user.tickets.filter(
        event__end_date_time__lte=timezone.now()
    ).count()

    featured_events = Event.objects.filter(
        is_featured=True,
        start_date_time__gte=timezone.now()
    ).order_by('start_date_time')[:3]

    announcements = Announcement.objects.order_by('-created_at')[:5]
    notifications = request.user.notifications.filter(is_read=False).order_by('-created_at')[:5]

    recommended_events = get_recommended_events(request.user, limit=3)
    
    context = {
        'upcoming_events': upcoming_events,  # Add this to context
        'upcoming_events_count': upcoming_events_count,
        'booked_events_count': booked_events_count,
        'attended_events_count': attended_events_count,
        'featured_events': featured_events,
        'announcements': announcements,
        'notifications': notifications,
        'face_registered': face_registered,
        'recommended_events': recommended_events,
    }
    return render(request, 'users/user_dashboard.html', context)

@login_required
def view_profile(request):
    return render(request, 'users/view_profile.html', {'user': request.user})

@login_required
def update_profile(request):
    if request.method == 'POST':
        form = ProfileUpdateForm(request.POST, request.FILES, instance=request.user)
        if form.is_valid():
            form.save()
            messages.success(request, 'Profile updated successfully!')
            return redirect('view_profile')
    else:
        form = ProfileUpdateForm(instance=request.user)
    
    context = {'form': form,}
    return render(request, 'users/update_profile.html', context)


import os
import cv2
import base64
import io
import numpy as np
import face_recognition
from django.http import JsonResponse
from PIL import Image
from .models import FaceEmbedding
from django.conf import settings


from django.views.decorators.http import require_GET
from django.utils.timezone import localtime

@login_required
@require_GET
def check_face_registration(request):
    try:
        face_embedding = FaceEmbedding.objects.filter(user=request.user).first()
        if face_embedding:
            return JsonResponse({
                'registered': True,
                'registration_date': localtime(face_embedding.created_at).strftime("%B %d, %Y at %I:%M %p")
            })
        return JsonResponse({'registered': False})
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


# Path to Haar Cascade using OpenCV's data directory
HAAR_CASCADE_PATH = os.path.join(cv2.data.haarcascades, 'haarcascade_frontalface_default.xml')
face_cascade = cv2.CascadeClassifier(HAAR_CASCADE_PATH)

@login_required
def capture_face(request):
    if request.method == 'POST':
        # Check if user already has a face embedding
        if FaceEmbedding.objects.filter(user=request.user).exists():
            return JsonResponse({
                'status': 'error',
                'message': 'You have already registered your face. Please contact support to update it.'
            }, status=400)
        
        # Validate image data
        image_data = request.POST.get('image')
        if not image_data or ',' not in image_data:
            return JsonResponse({
                'status': 'error',
                'message': 'Invalid image data format'
            }, status=400)
            
        try:
            # Decode base64 image from frontend
            image_data = image_data.split(',')[1]
            image_bytes = base64.b64decode(image_data)
            image = Image.open(io.BytesIO(image_bytes)).convert('RGB')
            
            # Validate image dimensions
            if image.size[0] < 100 or image.size[1] < 100:
                return JsonResponse({
                    'status': 'error',
                    'message': 'Image resolution too low. Please capture a closer image.'
                }, status=400)
            
            # Convert to numpy array for OpenCV
            image_array = np.array(image)
            # Convert RGB to BGR for OpenCV
            image_bgr = cv2.cvtColor(image_array, cv2.COLOR_RGB2BGR)
            # Convert to grayscale for Haar Cascade
            gray = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2GRAY)
            
            # Detect faces using Haar Cascade with stricter parameters
            faces = face_cascade.detectMultiScale(
                gray, 
                scaleFactor=1.1, 
                minNeighbors=7, 
                minSize=(100, 100),
                flags=cv2.CASCADE_SCALE_IMAGE
            )
            
            if len(faces) == 0:
                return JsonResponse({
                    'status': 'error',
                    'message': 'No face detected. Please ensure your face is clearly visible.'
                }, status=400)
                
            if len(faces) > 1:
                return JsonResponse({
                    'status': 'error',
                    'message': 'Multiple faces detected. Please ensure only your face is in the frame.'
                }, status=400)
            
            # Extract face region
            (x, y, w, h) = faces[0]
            
            # Validate face size (should be at least 20% of image)
            if w < image_array.shape[1] * 0.2 or h < image_array.shape[0] * 0.2:
                return JsonResponse({
                    'status': 'error',
                    'message': 'Face too small in image. Please move closer.'
                }, status=400)
            
            # Get embedding using face_recognition
            embeddings = face_recognition.face_encodings(image_array, [(y, x+w, y+h, x)])
            if not embeddings:
                return JsonResponse({
                    'status': 'error',
                    'message': 'Could not generate face features. Please try again with better lighting.'
                }, status=400)
            
            embedding = embeddings[0].tolist()
            
            # Save embedding to database
            FaceEmbedding.objects.create(user=request.user, embedding=embedding)

            request.user.face_registered = True
            request.user.save()
            
            return JsonResponse({
                'status': 'success',
                'message': 'Face registered successfully!',
                'redirect_url': reverse('event_list'),
            })
            
        except Exception as e:
            return JsonResponse({
                'status': 'error',
                'message': f'An error occurred: {str(e)}'
            }, status=500)
    
    return render(request, 'users/face_capture.html')


@login_required
def user_logout_view(request):
    logout(request)
    messages.success(request, 'You have been successfully logged out.')
    return redirect('login')

