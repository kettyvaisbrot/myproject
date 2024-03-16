from django.urls import path 

from appointments.views import get_appointments

from . import views

urlpatterns = [
    path('',views.home, name ='home'),

    path('register/', views.register, name ='register'),

    path('dashboard/',views.dashboard,name='dashboard'),

    path('owner_dashboard/',views.owner_dashboard,name='owner_dashboard'),

    path('login/', views.login_view, name='login'), 

    path('cancel_appointment/<int:appointment_id>/', views.cancel_appointment, name='cancel_appointment'),

    path('get_appointments/', views.get_appointments, name='get_appointments'),

    path('get_available_hours/', views.get_available_hours, name='get_available_hours'),


    path('logout/', views.logout_view, name='logout'),
]