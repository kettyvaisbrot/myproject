from django import forms
from .models import UserProfile, Appointment, BusinessHours, ReminderOption
from datetime import datetime
from django.contrib.auth import get_user_model
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.password_validation import validate_password
from django.utils.translation import gettext_lazy as _


class RegistrationForm(UserCreationForm):
    full_name = forms.CharField(max_length=100)  # Include the full_name field
    email = forms.EmailField()
    phone_number = forms.CharField(max_length=15)  # Include the phone_number field
    user_type = forms.ChoiceField(choices=UserProfile.USER_TYPE_CHOICES)
    day = forms.ChoiceField(choices=BusinessHours.DAYS_OF_WEEK, required=False)
    open_time = forms.TimeField(required=False)
    close_time = forms.TimeField(required=False)

    password1 = forms.CharField(
        label="Password",
        strip=False,
        widget=forms.PasswordInput,
        help_text="Your password must be between 8 and 20 characters long and contain at least one special character (!, $, %, etc.), one uppercase letter, one lowercase letter, and one digit.",
    )
    password2 = forms.CharField(
        label="Confirm Password",
        strip=False,
        widget=forms.PasswordInput,
        help_text="Enter the same password as before, for verification.",
    )

    class Meta:
        model = get_user_model()
        fields = ['full_name', 'email', 'phone_number', 'username', 'user_type', 'day', 'open_time', 'close_time', 'password1', 'password2']

    def clean_email(self):
        email = self.cleaned_data.get('email')
        if email and get_user_model().objects.filter(email=email).exists():
            raise forms.ValidationError('This email address is already in use.')
        return email

    def save(self, commit=True):
        user = super().save(commit=False)
        user.email = self.cleaned_data['email']
        user.full_name = self.cleaned_data['full_name']  # Save full_name
        user.phone_number = self.cleaned_data['phone_number']  # Save phone_number
        if commit:
            user.save()
        return user


class LoginForm(forms.Form):
    username = forms.CharField(max_length=150)
    password = forms.CharField(widget=forms.PasswordInput())

class ReminderSettingsForm(forms.ModelForm):
    class Meta:
        model = UserProfile
        fields = ['receive_reminders', 'reminder_options']

        
class AppointmentForm(forms.ModelForm):
    send_reminder = forms.BooleanField(required=False)
    reminder_options = forms.ModelMultipleChoiceField(
        queryset=ReminderOption.objects.all(),
        widget=forms.CheckboxSelectMultiple,
        required=False
    )

    class Meta:
        model = Appointment
        fields = ['date_time', 'time', 'reminder_options']

    def __init__(self, *args, **kwargs):
        business_hours = kwargs.pop('business_hours', None)
        super(AppointmentForm, self).__init__(*args, **kwargs)
        
        # Set initial choices for date_time and time fields
        self.fields['date_time'].widget = forms.SelectDateWidget(
            years=range(datetime.now().year, datetime.now().year + 2)
        )
        
        if business_hours:
            selected_date = self.initial.get('date_time') or datetime.now().date()
            available_hours = business_hours.get_available_hours(selected_date)
            self.fields['time'].widget = forms.Select(choices=[(hour, hour) for hour in available_hours])


class BusinessHoursForm(forms.ModelForm):
    class Meta:
        model = BusinessHours
        fields = ['monday_open_time', 'monday_close_time', 'tuesday_open_time', 'tuesday_close_time',
                  'wednesday_open_time', 'wednesday_close_time', 'thursday_open_time', 'thursday_close_time',
                  'friday_open_time', 'friday_close_time', 'saturday_open_time', 'saturday_close_time',
                  'sunday_open_time', 'sunday_close_time']