# events/urls.py

from django.urls import path
from . import views

urlpatterns = [
    path('', views.event_list, name='event_list'),
    # path('<int:event_id>/', views.event_detail, name='event_detail'),
    path('book/<int:event_id>/', views.ticket_booking, name='ticket_booking'),
    path('confirm/<int:event_id>/', views.confirm_ticket, name='confirm_ticket'),
    path('payment/success/', views.esewa_payment_success, name='esewa_success'),
    path('payment/failure/', views.esewa_payment_failure, name='esewa_failure'),
    path('my-tickets/', views.my_tickets, name='my_tickets'),
    path('ticket/<int:ticket_id>/', views.ticket_detail, name='ticket_detail'),
    path('ticket/<int:ticket_id>/download/', views.download_ticket, name='download_ticket'),
    path('<int:event_id>/feedback/', views.track_recommendation_feedback, name='event_feedback'),
]