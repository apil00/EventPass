# recognition/urls.py
from django.urls import path
from . import views

urlpatterns = [
    path('select_event/', views.select_event, name='select_event'),
    path('recognize/', views.recognize, name='recognize'),
    path('qr_checkin/', views.qr_checkin, name='qr_checkin'),
]