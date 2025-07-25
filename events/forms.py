from django import forms

class MultiTicketBookingForm(forms.Form):
    ticket_type = forms.ChoiceField(choices=[('general', 'General'), ('vip', 'VIP'), ('vvip', 'VVIP')])
    for_self = forms.BooleanField(required=False, label="For Myself")
    for_others = forms.BooleanField(required=False, label="For Others")
    others_quantity = forms.IntegerField(required=False, min_value=1, label="Number of Guests")