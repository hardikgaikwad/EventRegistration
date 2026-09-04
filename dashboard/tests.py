from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from datetime import timedelta

from accounts.models import User
from events.models import Event, Session, StaffAssignment
from registrations.models import Registration
from registrations.services import reserve_seat, transition, expire_stale_reservations
from .services import get_dashboard_stats


class DashboardStatsTests(TestCase):
    def setUp(self):
        self.organizer = User.objects.create_user(
            email="dash_organizer@example.com", password="pass12345", role=User.Role.ORGANIZER
        )
        self.staff = User.objects.create_user(
            email="dash_staff@example.com", password="pass12345", role=User.Role.STAFF
        )
        self.event = Event.objects.create(
            name="Dashboard Test Event", start_date="2026-01-01", end_date="2026-01-01", venue="Hall"
        )
        self.session_a = Session.objects.create(
            event=self.event, title="Session A", start_time=timezone.now(),
            duration_minutes=60, location="Room A", capacity=5,
        )
        self.session_b = Session.objects.create(
            event=self.event, title="Session B", start_time=timezone.now() + timedelta(days=1),
            duration_minutes=60, location="Room B", capacity=5,
        )
        StaffAssignment.objects.create(staff=self.staff, session=self.session_a)

    def test_chart_fills_zero_days_with_no_gaps(self):
        stats = get_dashboard_stats(self.organizer, chart_days=7)
        for status, daily_counts in stats["events_by_status"].items():
            self.assertEqual(len(daily_counts), 7)
            for day, count in daily_counts:
                self.assertEqual(count, 0)

    def test_chart_days_option_is_respected(self):
        stats_7 = get_dashboard_stats(self.organizer, chart_days=7)
        stats_30 = get_dashboard_stats(self.organizer, chart_days=30)
        for status in stats_7["events_by_status"]:
            self.assertEqual(len(stats_7["events_by_status"][status]), 7)
            self.assertEqual(len(stats_30["events_by_status"][status]), 30)

    def test_invalid_chart_days_falls_back_to_default(self):
        stats = get_dashboard_stats(self.organizer, chart_days=9999)
        for status in stats["events_by_status"]:
            self.assertEqual(len(stats["events_by_status"][status]), 14)
            
    def test_events_by_status_counts_each_series_independently(self):
        alice = reserve_seat(self.session_a, "Alice", "alice@example.com")  # reserved
        bob = reserve_seat(self.session_a, "Bob", "bob@example.com")
        transition(bob, Registration.Status.CONFIRMED)  # confirmed
        carol = reserve_seat(self.session_a, "Carol", "carol@example.com")
        transition(carol, Registration.Status.CONFIRMED)
        transition(carol, Registration.Status.CHECKED_IN)  # checked in

        stats = get_dashboard_stats(self.organizer, chart_days=7)
        today_index = 6  # last entry in a 7-day range is today

        reserved_today = stats["events_by_status"][Registration.Status.RESERVED][today_index][1]
        confirmed_today = stats["events_by_status"][Registration.Status.CONFIRMED][today_index][1]
        checked_in_today = stats["events_by_status"][Registration.Status.CHECKED_IN][today_index][1]

        self.assertEqual(reserved_today, 3)   # alice, bob, carol all started as reserved
        self.assertEqual(confirmed_today, 2)  # bob, carol
        self.assertEqual(checked_in_today, 1) # carol only