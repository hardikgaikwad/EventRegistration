from django.test import TestCase
from django.urls import reverse
from django.core.exceptions import PermissionDenied

from accounts.models import User
from .models import Event, Session, StaffAssignment
from .permissions import user_can_manage_session, require_session_access

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
        
class SessionPermissionTests(TestCase):
    def setUp(self):
        self.organizer = User.objects.create_user(
            email="organizer2@example.com", password="pass12345", role=User.Role.ORGANIZER
        )
        self.staff = User.objects.create_user(
            email="staff2@example.com", password="pass12345", role=User.Role.STAFF
        )
        self.event = Event.objects.create(
            name="Test Conference",
            start_date="2026-01-01",
            end_date="2026-01-02",
            venue="Main Hall",
        )
        self.session = Session.objects.create(
            event=self.event,
            title="Opening Keynote",
            start_time="2026-01-01T09:00:00Z",
            duration_minutes=60,
            location="Hall A",
            capacity=100,
        )

    def test_staff_cannot_create_session(self):
        self.client.force_login(self.staff)
        response = self.client.post(
            reverse("events:session_create", args=[self.event.id]),
            {
                "title": "Unauthorized Session",
                "start_time": "2026-01-01T10:00:00",
                "duration_minutes": 30,
                "location": "Hall B",
                "capacity": 50,
            },
        )
        self.assertEqual(response.status_code, 403)
        self.assertFalse(Session.objects.filter(title="Unauthorized Session").exists())

    def test_staff_cannot_edit_session_capacity(self):
        self.client.force_login(self.staff)
        response = self.client.post(
            reverse("events:session_update", args=[self.event.id, self.session.id]),
            {
                "title": "Opening Keynote",
                "start_time": "2026-01-01T09:00:00",
                "duration_minutes": 60,
                "location": "Hall A",
                "capacity": 9999,
            },
        )
        self.assertEqual(response.status_code, 403)
        self.session.refresh_from_db()
        self.assertEqual(self.session.capacity, 100)  # unchanged

    def test_staff_cannot_delete_session(self):
        self.client.force_login(self.staff)
        response = self.client.post(
            reverse("events:session_delete", args=[self.event.id, self.session.id])
        )
        self.assertEqual(response.status_code, 403)
        self.assertTrue(Session.objects.filter(id=self.session.id).exists())

    def test_organizer_can_create_session(self):
        self.client.force_login(self.organizer)
        response = self.client.post(
            reverse("events:session_create", args=[self.event.id]),
            {
                "title": "Authorized Session",
                "start_time": "2026-01-01T10:00:00",
                "duration_minutes": 30,
                "location": "Hall B",
                "capacity": 50,
            },
        )
        self.assertEqual(response.status_code, 302)
        self.assertTrue(Session.objects.filter(title="Authorized Session").exists())

    def test_staff_can_view_session_via_event_detail(self):
        self.client.force_login(self.staff)
        response = self.client.get(reverse("events:event_detail", args=[self.event.id]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Opening Keynote")
        
from django.core.exceptions import PermissionDenied
from .permissions import user_can_manage_session, require_session_access


class SessionAccessPermissionTests(TestCase):
    def setUp(self):
        self.organizer = User.objects.create_user(
            email="organizer3@example.com", password="pass12345", role=User.Role.ORGANIZER
        )
        self.assigned_staff = User.objects.create_user(
            email="assigned@example.com", password="pass12345", role=User.Role.STAFF
        )
        self.unassigned_staff = User.objects.create_user(
            email="unassigned@example.com", password="pass12345", role=User.Role.STAFF
        )
        self.event = Event.objects.create(
            name="Test Conference", start_date="2026-01-01", end_date="2026-01-02", venue="Main Hall"
        )
        self.session = Session.objects.create(
            event=self.event, title="Keynote", start_time="2026-01-01T09:00:00Z",
            duration_minutes=60, location="Hall A", capacity=100,
        )
        StaffAssignment.objects.create(staff=self.assigned_staff, session=self.session)

    def test_organizer_can_manage_any_session(self):
        self.assertTrue(user_can_manage_session(self.organizer, self.session))

    def test_assigned_staff_can_manage_their_session(self):
        self.assertTrue(user_can_manage_session(self.assigned_staff, self.session))

    def test_unassigned_staff_cannot_manage_session(self):
        self.assertFalse(user_can_manage_session(self.unassigned_staff, self.session))

    def test_require_session_access_raises_for_unassigned_staff(self):
        with self.assertRaises(PermissionDenied):
            require_session_access(self.unassigned_staff, self.session)

    def test_require_session_access_passes_silently_for_assigned_staff(self):
        # Should not raise
        require_session_access(self.assigned_staff, self.session)