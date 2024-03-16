from django.http import Http404
from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login
from django.contrib import messages 
from django.contrib.auth import get_user_model
from django.utils import timezone
from django.http import HttpResponseBadRequest, HttpResponseForbidden
from django.contrib.auth import logout
from django.http import HttpResponse
from django.shortcuts import get_object_or_404
from .models import ReminderOption
from django.http import JsonResponse
from django.db.models import Count
from django.contrib.auth.decorators import login_required
from .forms import LoginForm, RegistrationForm, AppointmentForm, BusinessHoursForm, ReminderSettingsForm
from django.views import View
from reportlab.pdfgen import canvas
from io import BytesIO
from collections import defaultdict
from datetime import datetime, timedelta
from django import forms
from .models import BusinessHours, Appointment,UserProfile
from django.template.loader import render_to_string
from django.core.mail import send_mail

import logging

logger = logging.getLogger(__name__)

def get_available_hours(request):
    if request.method == 'GET' and request.is_ajax():
        selected_date = request.GET.get('selected_date')
        logger.info(f"Selected date: {selected_date}")

        # Retrieve available hours for the selected date
        business_hours = BusinessHours.objects.first()
        logger.info(f"Business hours: {business_hours}")

        available_hours = business_hours.get_available_hours(selected_date)
        logger.info(f"Available hours: {available_hours}")

        return JsonResponse({'available_hours': available_hours})

    # Handle invalid requests
    return JsonResponse({'error': 'Invalid request'}, status=400)



def is_valid_appointment_time(appointment_time, open_time, close_time):
    # Extract time component from datetime objects
    appointment_time = appointment_time.time() if isinstance(appointment_time, datetime) else appointment_time
    open_time = open_time.time() if isinstance(open_time, datetime) else open_time
    close_time = close_time.time() if isinstance(close_time, datetime) else close_time

    return open_time <= appointment_time <= close_time


@login_required
def save_reminder_settings(request, user_id, appointment_id):
    user = get_object_or_404(UserProfile, pk=user_id)
    appointment = get_object_or_404(Appointment, pk=appointment_id)

    if request.method == 'POST':
        form = ReminderSettingsForm(request.POST, instance=user)
        if form.is_valid():
            form.save()
            messages.success(request, 'Reminder settings saved successfully.')
        else:
            messages.error(request, 'Failed to save reminder settings. Please check the form.')
    else:
        form = ReminderSettingsForm(instance=user)

    return render(request, 'appointments/save_reminder_settings.html', {'form': form, 'user': user, 'appointment': appointment})




def home(request):
    return render(request, 'appointments/index.html')

User = get_user_model()

def logout_view(request):
    logout(request)
    return redirect('home')


def register(request):
    if request.method == 'POST':
        form = RegistrationForm(request.POST)
        if form.is_valid():
            user_type = form.cleaned_data['user_type']

            # Check if there is already an owner
            if user_type == 'owner' and User.objects.filter(user_type='owner').exists():
                messages.error(request, 'Owner registration is only allowed once.')
                return redirect('register')

            # Extract form data
            username = form.cleaned_data['username']
            password = form.cleaned_data['password1']
            full_name = form.cleaned_data['full_name']
            email = form.cleaned_data['email']
            phone_number = form.cleaned_data['phone_number']
            user_type = form.cleaned_data['user_type']

            # Create a new user with the provided data
            user = User.objects.create_user(
                username=username,
                password=password,
                full_name=full_name,  # Add full name
                email=email,  # Add email
                phone_number=phone_number,  # Add phone number
                user_type=user_type,
            )

            # Add a success message
            messages.success(request, 'Registration successful. You can now log in.')

            if user_type == 'owner':
                # Check if business hours fields are provided
                if form.cleaned_data['day'] and form.cleaned_data['open_time'] and form.cleaned_data['close_time']:
                    business_hours_data = {
                        'day': form.cleaned_data['day'],
                        'open_time': form.cleaned_data['open_time'],
                        'close_time': form.cleaned_data['close_time'],
                        'owner': user,
                    }
                    BusinessHours.objects.create(**business_hours_data)

            return redirect('login')  # Redirect to the login page directly
        else:
            # Clear the form data to prevent retaining previous values
            form.data = {}
            # Print form errors for debugging
            print(f"Form errors: {form.errors}")

            # Handle form errors, maybe display them in the template
            return render(request, 'appointments/register.html', {'form': form})

    else:
        form = RegistrationForm()

    return render(request, 'appointments/register.html', {'form': form})

@login_required
def dashboard(request):
    user = request.user

    if user.user_type == 'customer':
        business_hours = BusinessHours.objects.first()
        current_time = timezone.now()

        # Get future appointments
        future_appointments = Appointment.objects.filter(customer=user, date_time__gte=current_time)

        # Get past appointments
        past_appointments = Appointment.objects.filter(customer=user, date_time__lt=current_time)

        if request.method == 'POST':
            form = AppointmentForm(request.POST, business_hours=business_hours)  # Pass business_hours here

            if form.is_valid():
                appointment = form.save(commit=False)
                appointment.customer = user
                selected_date = form.cleaned_data['date_time']
                selected_time = form.cleaned_data['time']
                appointment.date_time = datetime.combine(selected_date, selected_time)

                if Appointment.objects.filter(date_time=appointment.date_time).exists():
                    messages.error(
                        request, 'An appointment already exists at the selected date and time.'
                    )
                else:
                    open_time = getattr(business_hours, f"{selected_date.strftime('%A').lower()}_open_time")
                    close_time = getattr(business_hours, f"{selected_date.strftime('%A').lower()}_close_time")

                    if not is_valid_appointment_time(selected_time, open_time, close_time):
                        messages.error(
                            request,
                            'Invalid appointment time. Please choose a time within business hours.',
                        )
                    else:
                        appointment.save()
                        # Handle reminder options
                        reminder_options = form.cleaned_data['reminder_options']
                        appointment.reminder_options.set(reminder_options)

                        if user.receive_reminders:
                            # Assuming you have a function to send reminders via email
                            send_appointment_reminder(user, appointment)

                            messages.success(request, 'Appointment scheduled successfully, and reminder sent.')
                        else:
                            messages.success(request, 'Appointment scheduled successfully.')

                        return redirect('dashboard')
            else:
                messages.error(
                    request, 'Failed to schedule appointment. Please correct the errors below.'
                )
        else:
            form = AppointmentForm(initial={'date_time': current_time}, business_hours=business_hours)  # Pass business_hours here
            form.fields['date_time'].widget = forms.SelectDateWidget(
                years=range(current_time.year, current_time.year + 2)
            )

        return render(
            request, 'appointments/dashboard.html', {
                'form': form,
                'business_hours': business_hours,
                'future_appointments': future_appointments,
                'past_appointments': past_appointments
            }
        )
    else:
        messages.error(request, 'Invalid user type. You do not have permission to access this page.')
        return redirect('login')


def send_appointment_reminder(user, appointment):
    subject = 'Appointment Reminder'
    message = f'Your appointment is scheduled for {appointment.date_time}.'
    recipient_list = [user.email]

    send_mail(subject, message, from_email=None, recipient_list=recipient_list)


@login_required
def owner_dashboard(request):
    if request.user.user_type == 'owner':
        # Fetch all appointments for all users
        appointments = Appointment.objects.all()
        print(appointments)

        # Fetch or create the business hours for the current owner with defaults
        business_hours, created = BusinessHours.objects.get_or_create()

        if request.method == 'POST':
            # Process the business hours form submission
            form = BusinessHoursForm(request.POST, instance=business_hours)
            if form.is_valid():
                form.save()
                messages.success(request, 'Business hours updated successfully.')
            else:
                messages.error(request, 'Failed to update business hours. Please check the form.')
        else:
            # Display the business hours form
            form = BusinessHoursForm(instance=business_hours)

        # Check if business_hours is created in this request
        if created:
            messages.warning(request, 'Business hours not set yet. Please set business hours.')

        return render(request, 'appointments/owner_dashboard.html', {'appointments': appointments, 'form': form, 'business_hours': business_hours})
    else:
        messages.error(request, 'You do not have permission to access this page.')
        return redirect('home')


def cancel_appointment(request, appointment_id):
    try:
        appointment = Appointment.objects.get(id=appointment_id)
    except Appointment.DoesNotExist:
        raise Http404("Appointment does not exist")

    # Check if the appointment is in the past
    if appointment.is_past():
        # If appointment is in the past, simply redirect back to the dashboard
        messages.error(request, 'Cannot cancel past appointments.')
        return redirect('dashboard')

    if request.method == 'POST':
        # Fetch details for the cancellation email before canceling the appointment
        customer_name = appointment.customer.full_name
        appointment_datetime = appointment.date_time

        appointment_datetime_tz = timezone.localtime(appointment_datetime)

        # Save the appointment details that will be sent in the cancellation email
        appointment_details = {
            'customer_name': customer_name,
            'appointment_datetime': appointment_datetime_tz,
        }

        # Cancel the appointment
        appointment.delete()

        # Send cancellation email
        send_appointment_cancellation_email(appointment.customer.email, appointment_details)

        # Add a success message
        messages.success(request, 'Appointment canceled successfully.')

        # Redirect to the customer dashboard or another appropriate page
        return redirect('dashboard')

    return redirect('dashboard')


def send_appointment_cancellation_email(customer_email, appointment_details):
    subject = 'Appointment Cancellation'
    
    # Include the appointment details in the context
    context = {
        'customer_name': appointment_details.get('customer_name', ''),
        'appointment_datetime': appointment_details.get('appointment_datetime', ''),
    }

    # Render the HTML content with the context
    message = render_to_string('email/appointment_cancellation.txt', context)

    # Define the recipient list
    recipient_list = [customer_email]

    # Send the email
    send_mail(subject, message, from_email=None, recipient_list=recipient_list)


def login_view(request):
    if request.method == 'POST':
        form = LoginForm(request.POST)
        if form.is_valid():
            username = form.cleaned_data['username']
            password = form.cleaned_data['password']
            user = authenticate(request, username=username, password=password)

            if user is not None:
                login(request, user)

                user_type = user.user_type
                if user_type == 'owner':
                    return redirect('owner_dashboard')
                elif user_type == 'customer':
                    return redirect('dashboard')

            # Invalid login credentials
            error_message = "Invalid login credentials. Please try again."
            return render(request, 'appointments/login.html', {'form': form, 'error_message': error_message})

        else:
            # Invalid form submission
            return render(request, 'appointments/login.html', {'form': form})

    else:
        form = LoginForm()

    return render(request, 'appointments/login.html', {'form': form})


@login_required
def get_appointments(request):
    # Fetch all appointments
    appointments = Appointment.objects.all()

    # Format appointments
    appointments_list = []
    for appointment in appointments:
        appointment_info = {
            'customer': appointment.customer.username,
            'date_time': appointment.date_time.strftime('%Y-%m-%dT%H:%M:%S'),
            'duration': appointment.duration.total_seconds(),
            'status': appointment.status,
        }
        appointments_list.append(appointment_info)

    return JsonResponse({'appointments': appointments_list})