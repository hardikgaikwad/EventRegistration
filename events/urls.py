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
    path("<int:event_id>/sessions/create/", views.session_create, name="session_create"),
    path("<int:event_id>/sessions/<int:session_id>/", views.session_detail, name="session_detail"),
    path("<int:event_id>/sessions/<int:session_id>/edit/", views.session_update, name="session_update"),
    path("<int:event_id>/sessions/<int:session_id>/delete/", views.session_delete, name="session_delete"),
    path("<int:event_id>/sessions/<int:session_id>/assignments/", views.session_assignments, name="session_assignments"),
    path("<int:event_id>/sessions/<int:session_id>/assignments/<int:assignment_id>/delete/", views.assignment_delete, name="assignment_delete"),
    path("my-sessions/", views.staff_session_list, name="staff_session_list"),
]