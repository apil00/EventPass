from django.shortcuts import redirect
from django.urls import reverse

class FaceRegistrationMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response
        self.exempt_urls = [
            reverse('capture_face'),  # Typo fixed: 'capture_face'
            reverse('logout'),
            reverse('user_dashboard'),
            reverse('login'),
            # Admin URLs (explicitly exempt)
            '/admin/',
            '/admin/login/',
        ]

    def __call__(self, request):
        response = self.get_response(request)
        return response

    def process_view(self, request, view_func, view_args, view_kwargs):
        # Skip if user is not authenticated
        if not request.user.is_authenticated:
            return None

        # Skip for admin users (is_staff=True)
        if request.user.is_staff:
            return None

        # Skip for exempt URLs
        if any(request.path.startswith(url) for url in self.exempt_urls):
            return None

        # Skip for static/media files
        if request.path.startswith(('/static/', '/media/')):
            return None

        # Redirect to face registration if not registered
        if not request.user.face_registered:
            return redirect('capture_face')

        return None