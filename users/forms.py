# users/forms.py
from django import forms
from django.contrib.auth.forms import UserCreationForm
from .models import CustomUser
import os
from datetime import date
from django.core.exceptions import ValidationError

class UserRegisterForm(UserCreationForm):
    
    first_name = forms.CharField(max_length=30, required=True, widget=forms.TextInput(attrs={
        'class': 'form-control',
        'placeholder': 'First Name'
        }))


    last_name = forms.CharField(max_length=30, required=True, widget=forms.TextInput(attrs={
        'class': 'form-control',
        'placeholder': 'Last Name'
        }))
    
    profile_picture = forms.ImageField(
    required=True,
    widget=forms.ClearableFileInput(attrs={'class': 'form-control', 'required': 'required'}),
    label="Profile Picture",
    help_text="Required. Upload your profile picture."
)

    email = forms.EmailField(max_length=254, required=True, widget=forms.EmailInput(attrs={
        'class': 'form-control',
        'placeholder': 'Email'
        }))
    
    gender = forms.ChoiceField(
        choices=CustomUser.GENDER_CHOICES,
        required=True,
        initial='P',
        widget=forms.Select(attrs={
            'class': 'form-control',
        })
    )

    mobile_number = forms.CharField(
        max_length=10,
        required=True,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Mobile Number'
        })
    )

    password1 = forms.CharField(widget=forms.PasswordInput(attrs={
        'class': 'form-control',
        'placeholder': 'Password'
        }))

    password2 = forms.CharField(widget=forms.PasswordInput(attrs={
        'class': 'form-control',
        'placeholder': 'Confirm Password'
        }))


    class Meta:
        model = CustomUser
        fields = ('first_name', 'last_name', 'profile_picture', 'email', 'gender', 'mobile_number', 'password1', 'password2')

    def clean_email(self):
        email = self.cleaned_data.get('email')
        if CustomUser.objects.filter(email=email).exists():
            raise forms.ValidationError("This email is already in use.")
        return email
        
    def clean(self):
        cleaned_data = super().clean()
        password1 = cleaned_data.get("password1")
        password2 = cleaned_data.get("password2")
        
        if password1 and password2 and password1 != password2:
            self.add_error('password2', "Passwords don't match")
            
        return cleaned_data
    
    def clean_mobile_number(self):
        mobile_number = self.cleaned_data.get('mobile_number')
        if not mobile_number.isdigit():
            raise forms.ValidationError("Mobile number should contain only digits.")
        if len(mobile_number) != 10:
            raise forms.ValidationError("Mobile number should be 10 digits long.")
        if CustomUser.objects.filter(mobile_number=mobile_number).exists():
            raise forms.ValidationError("This mobile number is already in use.")
        return mobile_number
    
    def clean_profile_picture(self):
        picture = self.cleaned_data.get('profile_picture')
        if not picture:
            raise forms.ValidationError("Profile picture is required")
        
        # Validate file size (4MB max)
        if picture.size > 4 * 1024 * 1024:
            raise forms.ValidationError("Image file too large ( > 4MB )")
        
        # Validate file extension
        valid_extensions = ['.jpg', '.jpeg', '.png', '.gif']
        ext = os.path.splitext(picture.name)[1].lower()
        if ext not in valid_extensions:
            raise forms.ValidationError("Unsupported file extension. Please upload a JPG, JPEG, PNG, or GIF image.")
        
        return picture

class ProfileUpdateForm(forms.ModelForm):
    date_of_birth = forms.DateField(
        widget=forms.DateInput(attrs={
            'class': 'form-control',
            'type': 'date'
        }),
        required=False
    )

    def clean_profile_picture(self):
        picture = self.cleaned_data.get('profile_picture')
        if picture:
            # Validate file size (4MB max)
            if picture.size > 4 * 1024 * 1024:
                raise forms.ValidationError("Image file too large ( > 4MB )")
            # Validate file extension
            valid_extensions = ['.jpg', '.jpeg', '.png', '.gif']
            ext = os.path.splitext(picture.name)[1].lower()
            if ext not in valid_extensions:
                raise forms.ValidationError("Unsupported file extension. Please upload a JPG, JPEG, PNG, or GIF image.")
        return picture
    
    def clean_date_of_birth(self):
        dob = self.cleaned_data.get('date_of_birth')
        if dob:
            if dob > date.today():
                raise ValidationError("Date of birth cannot be in the future")
            # Additional validation if needed (e.g., minimum age)
            min_age = 13
            if (date.today() - dob).days < min_age * 365:
                raise ValidationError(f"You must be at least {min_age} years old")
        return dob
    
    def clean_mobile_number(self):
        mobile_number = self.cleaned_data.get('mobile_number')
        if not mobile_number.isdigit():
            raise forms.ValidationError("Mobile number should contain only digits.")
        if len(mobile_number) != 10:
            raise forms.ValidationError("Mobile number should be 10 digits long.")
        return mobile_number
    
    class Meta:
        model = CustomUser
        fields = [
            'first_name',
            'last_name',
            'mobile_number',
            'gender',
            'date_of_birth',
            'address',
            'profile_picture'
        ]

        widgets = {
            'gender': forms.Select(attrs={'class': 'form-select'}),
            'mobile_number': forms.TextInput(attrs={'class': 'form-control', 'placeholder': '98XXXXXXXX'}),
            'first_name': forms.TextInput(attrs={'class': 'form-control'}),
            'last_name': forms.TextInput(attrs={'class': 'form-control'}),
            'address': forms.TextInput(attrs={'class': 'form-control'}),
        }
