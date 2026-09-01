from django.urls import path
from . import views

app_name = "events"

urlpatterns = [
    path("", views.event_list, name="event_list"),
    path("create/", views.event_create, name="event_create"),
    path("<int:event_id>/", views.event_detail, name="event_detail"),
    path("<int:event_id>/edit/", views.event_update, name="event_update"),
    path("<int:event_id>/archive/", views.event_archive, name="event_archive"),
    path("<int:event_id>/restore/", views.event_restore, name="event_restore"),
]