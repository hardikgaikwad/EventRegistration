import threading
from django.test import TestCase, TransactionTestCase
from django.db import connection
from django.urls import reverse
from events.models import StaffAssignment

from accounts.models import User
from events.models import Event, Session
from .models import Registration, RegistrationEvent
from .services import transition, TransitionError, reserve_seat, CapacityFullError

# Create your tests here.

class TransitionTests(TestCase):
    def setUp(self):
        self.organizer = User.objects.create_user(
            email="organizer@example.com", password="pass12345", role=User.Role.ORGANIZER
        )
        event = Event.objects.create(
            name="Test Conference", start_date="2026-01-01", end_date="2026-01-02", venue="Main Hall"
        )
        self.session = Session.objects.create(
            event=event, title="Keynote", start_time="2026-01-01T09:00:00Z",
            duration_minutes=60, location="Hall A", capacity=10,
        )
        self.registration = Registration.objects.create(
            session=self.session, attendee_name="Jane Doe", attendee_email="jane@example.com",
            status=Registration.Status.RESERVED,
        )

    def test_reserved_to_confirmed_is_legal(self):
        transition(self.registration, Registration.Status.CONFIRMED, changed_by=self.organizer)
        self.registration.refresh_from_db()
        self.assertEqual(self.registration.status, Registration.Status.CONFIRMED)

    def test_confirmed_to_checked_in_is_legal(self):
        transition(self.registration, Registration.Status.CONFIRMED, changed_by=self.organizer)
        transition(self.registration, Registration.Status.CHECKED_IN, changed_by=self.organizer)
        self.registration.refresh_from_db()
        self.assertEqual(self.registration.status, Registration.Status.CHECKED_IN)

    def test_checked_in_to_reserved_is_illegal(self):
        transition(self.registration, Registration.Status.CONFIRMED, changed_by=self.organizer)
        transition(self.registration, Registration.Status.CHECKED_IN, changed_by=self.organizer)
        with self.assertRaises(TransitionError):
            transition(self.registration, Registration.Status.RESERVED, changed_by=self.organizer)
        self.registration.refresh_from_db()
        self.assertEqual(self.registration.status, Registration.Status.CHECKED_IN)  # unchanged

    def test_checked_in_to_cancelled_is_illegal(self):
        transition(self.registration, Registration.Status.CONFIRMED, changed_by=self.organizer)
        transition(self.registration, Registration.Status.CHECKED_IN, changed_by=self.organizer)
        with self.assertRaises(TransitionError):
            transition(self.registration, Registration.Status.CANCELLED, changed_by=self.organizer)

    def test_illegal_transition_writes_no_audit_row(self):
        with self.assertRaises(TransitionError):
            transition(self.registration, Registration.Status.CHECKED_IN, changed_by=self.organizer)
        # reserved -> checked_in directly is illegal (must go through confirmed first)
        self.assertEqual(RegistrationEvent.objects.filter(registration=self.registration).count(), 0)

    def test_legal_transition_writes_exactly_one_audit_row(self):
        transition(self.registration, Registration.Status.CONFIRMED, changed_by=self.organizer, note="looks good")
        events = RegistrationEvent.objects.filter(registration=self.registration)
        self.assertEqual(events.count(), 1)
        event = events.first()
        self.assertEqual(event.old_status, Registration.Status.RESERVED)
        self.assertEqual(event.new_status, Registration.Status.CONFIRMED)
        self.assertEqual(event.changed_by, self.organizer)
        self.assertEqual(event.note, "looks good")
        
class ReserveSeatTests(TestCase):
    def setUp(self):
        event = Event.objects.create(
            name="Small Meetup", start_date="2026-01-01", end_date="2026-01-01", venue="Cafe"
        )
        self.session = Session.objects.create(
            event=event, title="Workshop", start_time="2026-01-01T09:00:00Z",
            duration_minutes=60, location="Back room", capacity=2,
        )

    def test_reserve_up_to_capacity_succeeds(self):
        reserve_seat(self.session, "Alice", "alice@example.com")
        reserve_seat(self.session, "Bob", "bob@example.com")
        self.assertEqual(Registration.objects.filter(session=self.session).count(), 2)

    def test_reserve_beyond_capacity_is_refused(self):
        reserve_seat(self.session, "Alice", "alice@example.com")
        reserve_seat(self.session, "Bob", "bob@example.com")
        with self.assertRaises(CapacityFullError):
            reserve_seat(self.session, "Carol", "carol@example.com")
        # exactly 2 registrations exist - the refused 3rd never got created
        self.assertEqual(Registration.objects.filter(session=self.session).count(), 2)

    def test_cancelled_registration_frees_a_seat(self):
        reserve_seat(self.session, "Alice", "alice@example.com")
        bob = reserve_seat(self.session, "Bob", "bob@example.com")
        transition(bob, Registration.Status.CANCELLED)
        # a seat freed up, so a 3rd reservation should now succeed
        reserve_seat(self.session, "Carol", "carol@example.com")
        self.assertEqual(Registration.objects.filter(session=self.session).count(), 3)
        
class ConcurrentReservationTests(TransactionTestCase):
    def setUp(self):
        event = Event.objects.create(
            name="Popular Talk", start_date="2026-01-01", end_date="2026-01-01", venue="Auditorium"
        )
        self.session = Session.objects.create(
            event=event, title="Sold Out Session", start_time="2026-01-01T09:00:00Z",
            duration_minutes=60, location="Main stage", capacity=1,
        )

    def test_two_simultaneous_reservations_for_last_seat_only_one_succeeds(self):
        results = []

        def attempt_reservation(attendee_name, attendee_email):
            try:
                reserve_seat(self.session, attendee_name, attendee_email)
                results.append("success")
            except CapacityFullError:
                results.append("rejected")
            finally:
                # Each thread opened its own DB connection; close it explicitly
                # when the thread is done, or Django will warn about leaked
                # connections after the test.
                connection.close()

        thread_a = threading.Thread(target=attempt_reservation, args=("Alice", "alice@example.com"))
        thread_b = threading.Thread(target=attempt_reservation, args=("Bob", "bob@example.com"))

        thread_a.start()
        thread_b.start()
        thread_a.join()
        thread_b.join()

        self.assertEqual(results.count("success"), 1)
        self.assertEqual(results.count("rejected"), 1)
        self.assertEqual(Registration.objects.filter(session=self.session).count(), 1)
        
class RegistrationViewPermissionTests(TestCase):
    def setUp(self):
        self.organizer = User.objects.create_user(
            email="organizer4@example.com", password="pass12345", role=User.Role.ORGANIZER
        )
        self.assigned_staff = User.objects.create_user(
            email="assigned2@example.com", password="pass12345", role=User.Role.STAFF
        )
        self.unassigned_staff = User.objects.create_user(
            email="unassigned2@example.com", password="pass12345", role=User.Role.STAFF
        )
        event = Event.objects.create(
            name="Test Conference", start_date="2026-01-01", end_date="2026-01-02", venue="Main Hall"
        )
        self.session = Session.objects.create(
            event=event, title="Keynote", start_time="2026-01-01T09:00:00Z",
            duration_minutes=60, location="Hall A", capacity=10,
        )
        StaffAssignment.objects.create(staff=self.assigned_staff, session=self.session)
        self.registration = Registration.objects.create(
            session=self.session, attendee_name="Jane Doe", attendee_email="jane@example.com",
            status=Registration.Status.RESERVED,
        )

    def test_unassigned_staff_cannot_view_session_detail(self):
        self.client.force_login(self.unassigned_staff)
        response = self.client.get(reverse("events:session_detail", args=[self.session.event_id, self.session.id]))
        self.assertEqual(response.status_code, 403)

    def test_unassigned_staff_cannot_register_attendee(self):
        self.client.force_login(self.unassigned_staff)
        response = self.client.post(
            reverse("registrations:registration_create", args=[self.session.id]),
            {"attendee_name": "Intruder", "attendee_email": "intruder@example.com"},
        )
        self.assertEqual(response.status_code, 403)
        self.assertFalse(Registration.objects.filter(attendee_email="intruder@example.com").exists())

    def test_unassigned_staff_cannot_confirm_registration(self):
        self.client.force_login(self.unassigned_staff)
        response = self.client.post(reverse("registrations:registration_confirm", args=[self.registration.id]))
        self.assertEqual(response.status_code, 403)
        self.registration.refresh_from_db()
        self.assertEqual(self.registration.status, Registration.Status.RESERVED)  # unchanged

    def test_assigned_staff_can_register_attendee(self):
        self.client.force_login(self.assigned_staff)
        response = self.client.post(
            reverse("registrations:registration_create", args=[self.session.id]),
            {"attendee_name": "Legit Attendee", "attendee_email": "legit@example.com"},
        )
        self.assertEqual(response.status_code, 302)
        self.assertTrue(Registration.objects.filter(attendee_email="legit@example.com").exists())

    def test_organizer_can_act_on_any_session_unassigned_or_not(self):
        self.client.force_login(self.organizer)
        response = self.client.post(reverse("registrations:registration_confirm", args=[self.registration.id]))
        self.assertEqual(response.status_code, 302)
        self.registration.refresh_from_db()
        self.assertEqual(self.registration.status, Registration.Status.CONFIRMED)