# utils/ticket_pdf.py
# This module generates a PDF ticket for an event using ReportLab.
from io import BytesIO
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter
from reportlab.lib.utils import ImageReader
from django.http import HttpResponse
from django.conf import settings
import os

def generate_ticket_pdf(ticket):
    buffer = BytesIO()
    pdf = canvas.Canvas(buffer, pagesize=letter)
    
    # Set up styles
    pdf.setTitle(f"Ticket - {ticket.event.name}")
    pdf.setFont("Helvetica-Bold", 16)
    
    # Add header
    pdf.drawString(100, 750, "EventPass Ticket")
    pdf.line(100, 745, 500, 745)
    
    # Add user info
    pdf.setFont("Helvetica", 12)
    pdf.drawString(100, 720, f"Ticket for: {ticket.user.get_full_name()}")

    # Add event info
    pdf.setFont("Helvetica", 12)
    pdf.drawString(100, 700, f"Event: {ticket.event.name}")
    pdf.drawString(100, 680, f"Date: {ticket.event.start_date_time.strftime('%B %d, %Y %I:%M %p')}")
    pdf.drawString(100, 660, f"Location: {ticket.event.location}")
    
    # Add ticket info
    pdf.drawString(100, 620, f"Ticket Type: {ticket.get_ticket_type_display()}")
    pdf.drawString(100, 600, f"Ticket ID: {ticket.id}")
    pdf.drawString(100, 580, f"Price: Rs. {ticket.price}")
    pdf.drawString(100, 560, f"Status: {ticket.payment_status.upper()}")
    
    # Add QR code if exists
    if ticket.qr_code:
        qr_path = os.path.join(settings.MEDIA_ROOT, ticket.qr_code.name)
        if os.path.exists(qr_path):
            qr_img = ImageReader(qr_path)
            pdf.drawImage(qr_img, 400, 600, width=120, height=120)
            pdf.drawString(400, 580, "Scan at entrance")
    
    # Add footer
    pdf.setFont("Helvetica-Oblique", 10)
    pdf.drawString(100, 100, "Thank you for using EventPass!")
    pdf.drawString(100, 80, "Present this ticket at the event entrance.")
    
    pdf.showPage()
    pdf.save()
    
    buffer.seek(0)
    return buffer