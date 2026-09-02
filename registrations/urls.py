from django.urls import path
from . import views

app_name = "registrations"

urlpatterns = [
    path("sessions/<int:session_id>/register/", views.registration_create, name="registration_create"),
    path("<int:registration_id>/confirm/", views.registration_confirm, name="registration_confirm"),
    path("<int:registration_id>/check-in/", views.registration_check_in, name="registration_check_in"),
    path("<int:registration_id>/cancel/", views.registration_cancel, name="registration_cancel"),
]