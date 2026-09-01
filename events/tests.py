from django.test import TestCase
from django.urls import reverse

from accounts.models import User
from .models import Event

# Create your tests here.

class EventPermissionTests(TestCase):
    def setUp(self):
        self.organizer = User.objects.create_user(
            email="organizer@example.com", password="demo1234", role=User.Role.ORGANIZER
        )
        self.staff = User.objects.create_user(
            email="staff@example.com", password="test1234", role=User.Role.STAFF
        )
        self.event = Event.objects.create(
            name="Test Conference",
            start_date="2027-01-01",
            end_date="2027-01-02",
            venue="Main Hall",
        )
        
    def test_staff_cannot_create_event(self):
        self.client.force_login(self.staff)
        response = self.client.post(reverse("events:event_create"), {
            "name": "Unauthorized Event",
            "start_date": "2027-02-01",
            "end_date": "2027-02-02",
            "venue": "Side Room",
        })
        self.assertEqual(response.status_code, 403)
        self.assertFalse(Event.objects.filter(name="Unauthorized Event").exists())
        
    def test_staff_cannot_edit_evemt(self):
        self.client.force_login(self.staff)
        response = self.client.post(
            reverse("events:event_update", args=[self.event.id]),
            {"name": "Renamed", "start_date": "2026-01-01", "end_date": "2026-01-02", "venue": "Main Hall"},
        )
        self.assertEqual(response.status_code, 403)
        self.event.refresh_from_db()
        self.assertEqual(self.event.name, "Test Conference")  # unchanged
        
    def test_staff_cannot_archive_event(self):
        self.client.force_login(self.staff)
        response = self.client.post(reverse("events:event_archive", args=[self.event.id]))
        self.assertEqual(response.status_code, 403)
        self.event.refresh_from_db()
        self.assertFalse(self.event.is_archived)  # unchanged
        
    def test_organizer_can_create_event(self):
        self.client.force_login(self.organizer)
        response = self.client.post(reverse("events:event_create"), {
            "name": "Authorized Event",
            "start_date": "2026-02-01",
            "end_date": "2026-02-02",
            "venue": "Side Room",
        })
        self.assertEqual(response.status_code, 302)  # redirect on success
        self.assertTrue(Event.objects.filter(name="Authorized Event").exists())
        
    def test_staff_can_view_event_list_and_detail(self):
        self.client.force_login(self.staff)
        self.assertEqual(self.client.get(reverse("events:event_list")).status_code, 200)
        self.assertEqual(self.client.get(reverse("events:event_detail", args=[self.event.id])).status_code, 200)