from django.db import models
from django.contrib.auth.models import AbstractUser
from datetime import datetime, timedelta
from django.conf import settings
from django.utils import timezone
import pytz
from django.core.exceptions import ValidationError
from django.contrib.auth import get_user_model


class UserProfile(AbstractUser):
    full_name = models.CharField(max_length=100)
    email = models.EmailField()
    phone_number = models.CharField(max_length=15)
    receive_reminders = models.BooleanField(default=True)
    reminder_options = models.ManyToManyField('ReminderOption', blank=True)

    USER_TYPE_CHOICES = [
        ('owner', 'Owner'),
        ('customer', 'Customer'),
    ]

    user_type = models.CharField(max_length=10, choices=USER_TYPE_CHOICES)

    def __str__(self):
        return self.username



class ReminderOption(models.Model):
    name = models.CharField(max_length=50)

    def __str__(self):
        return self.name
    


class Appointment(models.Model):
    customer = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='customer_appointments')
    date_time = models.DateTimeField()
    time = models.TimeField()
    reminder_options = models.ManyToManyField('ReminderOption', blank=True)
    duration = models.DurationField(blank=True, null=True)

    STATUS_CHOICES = [
        ('scheduled', 'Scheduled'),
        ('canceled', 'Canceled'),
    ]

    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='scheduled')

    def __str__(self):
        return f"{self.customer.username}'s Appointment on {self.date_time.strftime('%Y-%m-%d %H:%M')}"

    class Meta:
        ordering = ['date_time']

    def save(self, *args, **kwargs):
        if not self.date_time.tzinfo:
            tzinfo = pytz.timezone('Asia/Jerusalem')
            self.date_time = timezone.make_aware(self.date_time, tzinfo)
        self.duration = timezone.timedelta(hours=1)

        super().save(*args, **kwargs)

    def is_past(self):
        now = timezone.now()
        return self.date_time < now


User = get_user_model()

class BusinessHours(models.Model):
    
    monday_open_time = models.TimeField(default='08:00')
    monday_close_time = models.TimeField(default='17:00')
    
    tuesday_open_time = models.TimeField(default='08:00')
    tuesday_close_time = models.TimeField(default='17:00')

    wednesday_open_time = models.TimeField(default='08:00')
    wednesday_close_time = models.TimeField(default='17:00')

    thursday_open_time = models.TimeField(default='08:00')
    thursday_close_time = models.TimeField(default='17:00')

    friday_open_time = models.TimeField(default='08:00')
    friday_close_time = models.TimeField(default='17:00')

    saturday_open_time = models.TimeField(default='08:00')
    saturday_close_time = models.TimeField(default='17:00')

    sunday_open_time = models.TimeField(default='08:00')
    sunday_close_time = models.TimeField(default='17:00')

    def __str__(self):
        business_hours_str = "\n".join(
            f"{day.capitalize()}: {self.get_open_hours(day)} - {self.get_close_hours(day)}"
            for day, _ in self.DAYS_OF_WEEK
        )
        return f"Business Hours:\n{business_hours_str}"

    def get_open_hours(self, day_of_week):
        # Validate day_of_week
        if day_of_week.lower() not in [day[0] for day in self.DAYS_OF_WEEK]:
            raise ValidationError("Invalid day of the week for business hours.")
        return getattr(self, f"{day_of_week.lower()}_open_time")

    def get_close_hours(self, day_of_week):
        # Validate day_of_week
        if day_of_week.lower() not in [day[0] for day in self.DAYS_OF_WEEK]:
            raise ValidationError("Invalid day of the week for business hours.")
        return getattr(self, f"{day_of_week.lower()}_close_time")

    def clean(self):
        for day, _ in self.DAYS_OF_WEEK:
            open_time = getattr(self, f"{day.lower()}_open_time")
            close_time = getattr(self, f"{day.lower()}_close_time")

            # Add your custom validation logic here
            if close_time <= open_time:
                raise ValidationError(f"Close time should be after open time for {day}.")
            

    def get_available_hours(self, selected_date):
        # Get the day of the week for the selected date
        day_of_week = selected_date.strftime('%A').lower()

        # Get the open and close times for the selected day
        open_time = getattr(self, f"{day_of_week}_open_time")
        close_time = getattr(self, f"{day_of_week}_close_time")

        # Get existing appointments for the selected date and selected day
        existing_appointments = Appointment.objects.filter(
            date_time__date=selected_date,
            date_time__time__gte=open_time,
            date_time__time__lt=close_time,
            status='scheduled'  # Include only scheduled appointments
        )

        # Include canceled appointments as available hours
        canceled_appointments = Appointment.objects.filter(
            date_time__date=selected_date,
            date_time__time__gte=open_time,
            date_time__time__lt=close_time,
            status='canceled'  # Include only canceled appointments
        )

        # Assuming each appointment has a duration of 1 hour
        appointment_duration = timedelta(hours=1)

        # Generate a list of available hours
        available_hours = []
        current_time = datetime.combine(selected_date, open_time)

        # Filter out past hours
        current_datetime = datetime.now()
        if current_datetime.date() == selected_date:
            current_time = max(current_time, current_datetime)

        while current_time + appointment_duration <= datetime.combine(selected_date, close_time):
            # Check if the current time is not conflicting with existing appointments or canceled appointments
            if not existing_appointments.filter(date_time__time=current_time.time()) and not canceled_appointments.filter(date_time__time=current_time.time()):
                available_hours.append(current_time.time().strftime('%H:%M'))

            current_time += appointment_duration

        return available_hours

        
    DAYS_OF_WEEK = [
        ('monday', 'Monday'),
        ('tuesday', 'Tuesday'),
        ('wednesday', 'Wednesday'),
        ('thursday', 'Thursday'),
        ('friday', 'Friday'),
        ('saturday', 'Saturday'),
        ('sunday', 'Sunday'),
    ]