import threading
from datetime import timedelta
from django.test import override_settings, TestCase, TransactionTestCase
from django.db import connection
from django.urls import reverse
from django.utils import timezone
from django.core.management import call_command
from django.core.files.uploadedfile import SimpleUploadedFile

from events.models import StaffAssignment
from accounts.models import User
from events.models import Event, Session
from .models import Registration, RegistrationEvent
from .services import (
    CapacityFullError,
    DuplicateRegistrationError,
    TransitionError,
    build_session_roster_csv_rows,
    expire_stale_reservations,
    import_registrations_from_csv,
    reserve_seat,
    transition,
)

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
    
class ExpiryTests(TestCase):
    def setUp(self):
        event = Event.objects.create(
            name="Expiry Test Event", start_date="2026-01-01", end_date="2026-01-01", venue="Hall"
        )
        self.session = Session.objects.create(
            event=event, title="Session", start_time="2026-01-01T09:00:00Z",
            duration_minutes=60, location="Room 1", capacity=2,
        )

    def make_stale_reservation(self, minutes_old):
        registration = Registration.objects.create(
            session=self.session, attendee_name="Old Reservation", attendee_email="old@example.com",
            status=Registration.Status.RESERVED,
        )
        stale_time = timezone.now() - timedelta(minutes=minutes_old)
        Registration.objects.filter(pk=registration.pk).update(reserved_at=stale_time)
        registration.refresh_from_db()
        return registration

    @override_settings(RESERVATION_HOLD_MINUTES=30)
    def test_reservation_older_than_hold_window_is_expired(self):
        stale = self.make_stale_reservation(minutes_old=31)
        expired_count = expire_stale_reservations(self.session)
        self.assertEqual(expired_count, 1)
        stale.refresh_from_db()
        self.assertEqual(stale.status, Registration.Status.EXPIRED)

    @override_settings(RESERVATION_HOLD_MINUTES=30)
    def test_reservation_within_hold_window_is_not_expired(self):
        fresh = self.make_stale_reservation(minutes_old=10)
        expired_count = expire_stale_reservations(self.session)
        self.assertEqual(expired_count, 0)
        fresh.refresh_from_db()
        self.assertEqual(fresh.status, Registration.Status.RESERVED)

    @override_settings(RESERVATION_HOLD_MINUTES=30)
    def test_expiring_frees_a_seat_for_a_new_reservation(self):
        self.make_stale_reservation(minutes_old=31)
        reserve_seat(self.session, "Bob", "bob@example.com")  # capacity=2, 1 stale + this = fine
        self.assertEqual(
            Registration.objects.filter(session=self.session, status=Registration.Status.RESERVED).count(), 1
        )
        self.assertEqual(
            Registration.objects.filter(session=self.session, status=Registration.Status.EXPIRED).count(), 1
        )

    @override_settings(RESERVATION_HOLD_MINUTES=30)
    def test_expire_reservations_command_runs_and_expires_stale_ones(self):
        self.make_stale_reservation(minutes_old=45)
        call_command("expire_reservations")
        self.assertEqual(
            Registration.objects.filter(session=self.session, status=Registration.Status.EXPIRED).count(), 1
        )
        
class RegistrationListTests(TestCase):
    def setUp(self):
        self.organizer = User.objects.create_user(
            email="organizer5@example.com", password="pass12345", role=User.Role.ORGANIZER
        )
        self.staff_a = User.objects.create_user(
            email="staffA@example.com", password="pass12345", role=User.Role.STAFF
        )
        self.staff_b = User.objects.create_user(
            email="staffB@example.com", password="pass12345", role=User.Role.STAFF
        )

        self.event_1 = Event.objects.create(
            name="Event One", start_date="2026-01-01", end_date="2026-01-01", venue="Hall A"
        )
        self.event_2 = Event.objects.create(
            name="Event Two", start_date="2026-02-01", end_date="2026-02-01", venue="Hall B"
        )

        self.session_1 = Session.objects.create(
            event=self.event_1, title="Session One", start_time="2026-01-01T09:00:00Z",
            duration_minutes=60, location="Room 1", capacity=10,
        )
        self.session_2 = Session.objects.create(
            event=self.event_2, title="Session Two", start_time="2026-02-01T09:00:00Z",
            duration_minutes=60, location="Room 2", capacity=10,
        )

        # staff_a is only assigned to session_1; staff_b isn't assigned to anything
        StaffAssignment.objects.create(staff=self.staff_a, session=self.session_1)

        Registration.objects.create(
            session=self.session_1, attendee_name="Alice Adams", attendee_email="alice@example.com",
            status=Registration.Status.RESERVED,
        )
        Registration.objects.create(
            session=self.session_1, attendee_name="Bob Baker", attendee_email="bob@example.com",
            status=Registration.Status.CONFIRMED,
        )
        Registration.objects.create(
            session=self.session_2, attendee_name="Carol Carter", attendee_email="carol@example.com",
            status=Registration.Status.RESERVED,
        )

    def test_organizer_sees_all_registrations(self):
        self.client.force_login(self.organizer)
        response = self.client.get(reverse("registrations:registration_list"))
        self.assertEqual(response.context["total_count"], 3)

    def test_staff_only_sees_registrations_for_assigned_sessions(self):
        self.client.force_login(self.staff_a)
        response = self.client.get(reverse("registrations:registration_list"))
        # staff_a is assigned to session_1 only -> Alice + Bob, not Carol
        self.assertEqual(response.context["total_count"], 2)
        names = [r.attendee_name for r in response.context["page"]]
        self.assertIn("Alice Adams", names)
        self.assertIn("Bob Baker", names)
        self.assertNotIn("Carol Carter", names)

    def test_unassigned_staff_sees_nothing(self):
        self.client.force_login(self.staff_b)
        response = self.client.get(reverse("registrations:registration_list"))
        self.assertEqual(response.context["total_count"], 0)

    def test_search_by_partial_name(self):
        self.client.force_login(self.organizer)
        response = self.client.get(reverse("registrations:registration_list"), {"q": "ali"})
        self.assertEqual(response.context["total_count"], 1)
        self.assertEqual(response.context["page"][0].attendee_name, "Alice Adams")

    def test_search_by_partial_email(self):
        self.client.force_login(self.organizer)
        response = self.client.get(reverse("registrations:registration_list"), {"q": "bob@"})
        self.assertEqual(response.context["total_count"], 1)
        self.assertEqual(response.context["page"][0].attendee_email, "bob@example.com")

    def test_filter_by_status(self):
        self.client.force_login(self.organizer)
        response = self.client.get(reverse("registrations:registration_list"), {"status": "confirmed"})
        self.assertEqual(response.context["total_count"], 1)
        self.assertEqual(response.context["page"][0].attendee_name, "Bob Baker")

    def test_filter_by_event(self):
        self.client.force_login(self.organizer)
        response = self.client.get(reverse("registrations:registration_list"), {"event": self.event_2.id})
        self.assertEqual(response.context["total_count"], 1)
        self.assertEqual(response.context["page"][0].attendee_name, "Carol Carter")

    def test_filter_by_session(self):
        self.client.force_login(self.organizer)
        response = self.client.get(reverse("registrations:registration_list"), {"session": self.session_1.id})
        self.assertEqual(response.context["total_count"], 2)

    def test_staff_cannot_leak_into_unassigned_event_via_url_tampering(self):
        # staff_a is only assigned to session_1 (event_1). Manually requesting
        # event_2's id in the URL should NOT surface event_2's registrations -
        # the role-scoping happens before the filter is ever applied.
        self.client.force_login(self.staff_a)
        response = self.client.get(reverse("registrations:registration_list"), {"event": self.event_2.id})
        self.assertEqual(response.context["total_count"], 0)

    def test_pagination_limits_page_size(self):
        # Create enough registrations to force a second page, using a small
        # override so the test doesn't need to create hundreds of rows.
        for i in range(5):
            Registration.objects.create(
                session=self.session_1, attendee_name=f"Extra {i}", attendee_email=f"extra{i}@example.com",
                status=Registration.Status.RESERVED,
            )
        with self.settings(REGISTRATIONS_PAGE_SIZE=3):
            self.client.force_login(self.organizer)
            response = self.client.get(reverse("registrations:registration_list"))
            self.assertEqual(len(response.context["page"]), 3)
            self.assertEqual(response.context["total_count"], 8)  # 3 original + 5 extra
            self.assertTrue(response.context["page"].has_other_pages())

    def test_query_count_stays_flat_regardless_of_row_count(self):
        # select_related should keep this at a small, fixed number of queries
        # no matter how many registrations exist - proves we're not doing
        # an extra query per row (the N+1 bug select_related prevents).
        self.client.force_login(self.organizer)
        with self.assertNumQueries(6):  # session query, count query, registrations query, events/sessions dropdowns
            self.client.get(reverse("registrations:registration_list"))
            
class CsvImportExportTests(TestCase):
    def setUp(self):
        event = Event.objects.create(
            name="CSV Test Event", start_date="2026-01-01", end_date="2026-01-01", venue="Hall"
        )
        self.session = Session.objects.create(
            event=event, title="CSV Session", start_time="2026-01-01T09:00:00Z",
            duration_minutes=60, location="Room 1", capacity=10,
        )

    def make_csv(self, content):
        return SimpleUploadedFile("attendees.csv", content.encode("utf-8"), content_type="text/csv")

    def test_mixed_outcomes_report_correctly(self):
        csv_content = (
            "name,email\n"
            "Alice Adams,alice@example.com\n"
            "Bob Baker,bob@example.com\n"
            ",missing-name@example.com\n"
            "Carol Carter,not-an-email\n"
            "Alice Adams,alice@example.com\n"
        )
        report = import_registrations_from_csv(self.session, self.make_csv(csv_content))

        self.assertEqual(len(report), 5)
        outcomes = [row["outcome"] for row in report]
        self.assertEqual(outcomes, ["created", "created", "rejected", "rejected", "duplicate"])

        # exactly the 2 valid, non-duplicate rows actually got created
        self.assertEqual(Registration.objects.filter(session=self.session).count(), 2)

    def test_valid_rows_survive_even_when_a_later_row_hits_capacity(self):
        # capacity=2 session; 3 valid rows in one file - the 3rd should be
        # rejected for capacity, but the first 2 must still be created,
        # proving the import isn't wrapped in one all-or-nothing transaction.
        small_session = Session.objects.create(
            event=self.session.event, title="Small Session", start_time="2026-01-01T10:00:00Z",
            duration_minutes=30, location="Room 2", capacity=2,
        )
        csv_content = (
            "name,email\n"
            "Alice Adams,alice@example.com\n"
            "Bob Baker,bob@example.com\n"
            "Carol Carter,carol@example.com\n"
        )
        report = import_registrations_from_csv(small_session, self.make_csv(csv_content))

        self.assertEqual(report[0]["outcome"], "created")
        self.assertEqual(report[1]["outcome"], "created")
        self.assertEqual(report[2]["outcome"], "rejected")
        self.assertIn("capacity", report[2]["reason"].lower())

        self.assertEqual(Registration.objects.filter(session=small_session).count(), 2)

    def test_import_handles_utf8_bom(self):
        # Simulates a CSV exported from Excel, which often prepends a BOM.
        csv_content = "\ufeffname,email\nDave Davis,dave@example.com\n"
        report = import_registrations_from_csv(self.session, self.make_csv(csv_content))
        self.assertEqual(report[0]["outcome"], "created")
        self.assertEqual(report[0]["name"], "Dave Davis")

    def test_export_includes_every_registration_with_current_status(self):
        alice = reserve_seat(self.session, "Alice Adams", "alice@example.com")
        transition(alice, Registration.Status.CONFIRMED)
        reserve_seat(self.session, "Bob Baker", "bob@example.com")

        rows = list(build_session_roster_csv_rows(self.session))

        self.assertEqual(len(rows), 3)  # header + 2 registrations
        self.assertEqual(rows[0], ("Attendee Name", "Attendee Email", "Status", "Reserved At"))
        # sorted by attendee_name: Alice before Bob
        self.assertEqual(rows[1][0], "Alice Adams")
        self.assertEqual(rows[1][2], "Confirmed")
        self.assertEqual(rows[2][0], "Bob Baker")
        self.assertEqual(rows[2][2], "Reserved")

    def test_import_requires_organizer_even_for_assigned_staff(self):
        assigned_staff = User.objects.create_user(
            email="assigned3@example.com", password="pass12345", role=User.Role.STAFF
        )
        StaffAssignment.objects.create(staff=assigned_staff, session=self.session)
        self.client.force_login(assigned_staff)

        csv_content = "name,email\nEve Evans,eve@example.com\n"
        response = self.client.post(
            reverse("registrations:registration_import", args=[self.session.id]),
            {"csv_file": self.make_csv(csv_content)},
        )
        self.assertEqual(response.status_code, 403)
        self.assertFalse(Registration.objects.filter(attendee_email="eve@example.com").exists())

    def test_import_succeeds_for_organizer(self):
        organizer = User.objects.create_user(
            email="importorganizer@example.com", password="pass12345", role=User.Role.ORGANIZER
        )
        self.client.force_login(organizer)
        csv_content = "name,email\nFrank Foster,frank@example.com\n"
        response = self.client.post(
            reverse("registrations:registration_import", args=[self.session.id]),
            {"csv_file": self.make_csv(csv_content)},
        )
        self.assertEqual(response.status_code, 200)  # renders the report page directly
        self.assertTrue(Registration.objects.filter(attendee_email="frank@example.com").exists())

    def test_export_view_requires_session_access(self):
        staff_unassigned = User.objects.create_user(
            email="unassigned4@example.com", password="pass12345", role=User.Role.STAFF
        )
        self.client.force_login(staff_unassigned)
        response = self.client.get(reverse("registrations:session_roster_csv", args=[self.session.id]))
        self.assertEqual(response.status_code, 403)
        
    def test_export_succeeds_for_assigned_staff(self):
        assigned_staff = User.objects.create_user(
            email="assigned4@example.com", password="pass12345", role=User.Role.STAFF
        )
        StaffAssignment.objects.create(staff=assigned_staff, session=self.session)
        self.client.force_login(assigned_staff)
        response = self.client.get(reverse("registrations:session_roster_csv", args=[self.session.id]))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "text/csv")
        
class RegistrationEventImmutabilityTests(TestCase):
    def setUp(self):
        self.superuser = User.objects.create_superuser(
            email="superuser@example.com", password="pass12345"
        )
        event = Event.objects.create(
            name="Immutability Test Event", start_date="2026-01-01", end_date="2026-01-01", venue="Hall"
        )
        session = Session.objects.create(
            event=event, title="Session", start_time="2026-01-01T09:00:00Z",
            duration_minutes=60, location="Room 1", capacity=10,
        )
        self.registration = reserve_seat(session, "Alice Adams", "alice@example.com")
        self.event_row = RegistrationEvent.objects.filter(registration=self.registration).first()

    def test_admin_change_permission_is_always_denied(self):
        from registrations.admin import RegistrationEventAdmin
        from django.contrib.admin.sites import AdminSite

        admin_instance = RegistrationEventAdmin(RegistrationEvent, AdminSite())
        self.assertFalse(admin_instance.has_change_permission(None))
        self.assertFalse(admin_instance.has_delete_permission(None))
        self.assertFalse(admin_instance.has_add_permission(None))

    def test_superuser_can_view_but_not_edit_registration_event(self):
        self.client.force_login(self.superuser)
        url = f"/admin/registrations/registrationevent/{self.event_row.pk}/change/"

        # GET succeeds - Django shows a read-only view since has_view is
        # implicitly true even though has_change_permission is False
        get_response = self.client.get(url)
        self.assertEqual(get_response.status_code, 200)

        # POST (an actual attempted save) is what's really blocked
        original_note = self.event_row.note
        post_response = self.client.post(url, {
            "new_status": "expired",  # attempting to tamper with the status
            "note": "TAMPERED",
        })
        self.assertEqual(post_response.status_code, 403)

        self.event_row.refresh_from_db()
        self.assertEqual(self.event_row.new_status, Registration.Status.RESERVED)  # unchanged
        self.assertEqual(self.event_row.note, original_note)  # unchanged

    def test_superuser_cannot_delete_via_admin(self):
        self.client.force_login(self.superuser)
        url = f"/admin/registrations/registrationevent/{self.event_row.pk}/delete/"
        response = self.client.get(url)
        self.assertEqual(response.status_code, 403)
        self.assertTrue(RegistrationEvent.objects.filter(pk=self.event_row.pk).exists())

    def test_registration_event_count_never_decreases_across_lifecycle(self):
        # A sanity check that the audit trail only ever grows - each legal
        # transition adds exactly one row, nothing ever removes one.
        transition(self.registration, Registration.Status.CONFIRMED)
        count_after_confirm = RegistrationEvent.objects.filter(registration=self.registration).count()
        self.assertEqual(count_after_confirm, 2)  # creation + confirm

        transition(self.registration, Registration.Status.CHECKED_IN)
        count_after_checkin = RegistrationEvent.objects.filter(registration=self.registration).count()
        self.assertEqual(count_after_checkin, 3)  # + check-in
        
class RegistrationTimelineTests(TestCase):
    def setUp(self):
        self.organizer = User.objects.create_user(
            email="timeline_organizer@example.com", password="pass12345", role=User.Role.ORGANIZER
        )
        event = Event.objects.create(
            name="Timeline Test Event", start_date="2026-01-01", end_date="2026-01-01", venue="Hall"
        )
        self.session = Session.objects.create(
            event=event, title="Session", start_time="2026-01-01T09:00:00Z",
            duration_minutes=60, location="Room 1", capacity=10,
        )

    def test_timeline_shows_creation_and_transitions_in_order(self):
        registration = reserve_seat(self.session, "Alice Adams", "alice@example.com", created_by=self.organizer)
        transition(registration, Registration.Status.CONFIRMED, changed_by=self.organizer, note="Confirmed by phone.")
        transition(registration, Registration.Status.CHECKED_IN, changed_by=self.organizer)

        self.client.force_login(self.organizer)
        response = self.client.get(reverse("registrations:registration_timeline", args=[registration.id]))

        self.assertEqual(response.status_code, 200)
        events = list(response.context["events"])
        self.assertEqual(len(events), 3)

        # events must be in chronological order: creation, confirm, check-in
        self.assertIsNone(events[0].old_status)
        self.assertEqual(events[0].new_status, Registration.Status.RESERVED)

        self.assertEqual(events[1].old_status, Registration.Status.RESERVED)
        self.assertEqual(events[1].new_status, Registration.Status.CONFIRMED)
        self.assertEqual(events[1].note, "Confirmed by phone.")

        self.assertEqual(events[2].old_status, Registration.Status.CONFIRMED)
        self.assertEqual(events[2].new_status, Registration.Status.CHECKED_IN)

    def test_timeline_shows_system_for_automated_changes(self):
        registration = reserve_seat(self.session, "Bob Baker", "bob@example.com")
        # Backdate and expire it, same technique as the expiry tests -
        # produces a changed_by=None event, exactly what the expiry
        # command generates.
        Registration.objects.filter(pk=registration.pk).update(
            reserved_at=timezone.now() - timedelta(minutes=45)
        )
        expire_stale_reservations(self.session)

        self.client.force_login(self.organizer)
        response = self.client.get(reverse("registrations:registration_timeline", args=[registration.id]))
        self.assertContains(response, "System")

    def test_timeline_requires_session_access(self):
        unassigned_staff = User.objects.create_user(
            email="timeline_staff@example.com", password="pass12345", role=User.Role.STAFF
        )
        registration = reserve_seat(self.session, "Carol Carter", "carol@example.com")

        self.client.force_login(unassigned_staff)
        response = self.client.get(reverse("registrations:registration_timeline", args=[registration.id]))
        self.assertEqual(response.status_code, 403)