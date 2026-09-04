import random
from datetime import timedelta

from django.core.management.base import BaseCommand
from django.utils import timezone

from accounts.models import User
from events.models import Event, Session, StaffAssignment
from registrations.models import Registration, RegistrationEvent, DismissedAlert
from registrations.services import reserve_seat, transition

FIRST_NAMES = [
    "James", "Mary", "Robert", "Patricia", "John", "Jennifer", "Michael", "Linda",
    "David", "Elizabeth", "William", "Barbara", "Richard", "Susan", "Joseph", "Jessica",
    "Thomas", "Sarah", "Charles", "Karen", "Priya", "Arjun", "Wei", "Fatima",
    "Carlos", "Sofia", "Ahmed", "Yuki", " Olivia", "Noah",
]
LAST_NAMES = [
    "Smith", "Johnson", "Williams", "Brown", "Jones", "Garcia", "Miller", "Davis",
    "Rodriguez", "Martinez", "Hernandez", "Lopez", "Gonzalez", "Wilson", "Anderson",
    "Thomas", "Taylor", "Moore", "Jackson", "Martin", "Lee", "Perez", "Thompson",
    "White", "Harris", "Sanchez", "Clark", "Ramirez", "Lewis", "Robinson",
]

DEMO_EVENT_NAMES = [
    "Spring Tech Summit",
    "Community Wellness Fair",
    "Founders Meetup 2025",  # archived
]


def random_full_name():
    return f"{random.choice(FIRST_NAMES)} {random.choice(LAST_NAMES)}"


def email_from_name(name, unique_id):
    slug = name.lower().replace(" ", ".")
    return f"{slug}.{unique_id}@example.com"


class Command(BaseCommand):
    help = "Populates the database with realistic demo data spread across the last 30 days."

    def handle(self, *args, **options):
        random.seed(42)  # deterministic demo data - reruns produce the same "random" spread

        organizer, _ = User.objects.get_or_create(
            email="organizer@example.com",
            defaults={"role": User.Role.ORGANIZER, "is_staff": True, "is_superuser": True},
        )
        organizer.set_password("demopass123")
        organizer.save()

        staff_member, _ = User.objects.get_or_create(
            email="staff@example.com", defaults={"role": User.Role.STAFF}
        )
        staff_member.set_password("demopass123")
        staff_member.save()

        self.stdout.write(f"Organizer: {organizer.email} / demopass123")
        self.stdout.write(f"Staff:     {staff_member.email} / demopass123")

        # Rerunnable: wipe any previously-seeded demo events (cascades to
        # their sessions/registrations/audit rows) before recreating.
        deleted_count, _ = Event.objects.filter(name__in=DEMO_EVENT_NAMES).delete()
        if deleted_count:
            self.stdout.write(f"Cleared {deleted_count} row(s) from a previous seed run.")

        now = timezone.now()

        spring_summit = Event.objects.create(
            name="Spring Tech Summit",
            description="A two-day conference on emerging technology.",
            start_date=(now + timedelta(days=10)).date(),
            end_date=(now + timedelta(days=11)).date(),
            venue="Downtown Convention Center",
        )
        wellness_fair = Event.objects.create(
            name="Community Wellness Fair",
            description="A single-day event for local health and wellness vendors.",
            start_date=now.date(),
            end_date=now.date(),
            venue="City Park Pavilion",
        )
        founders_meetup = Event.objects.create(
            name="Founders Meetup 2025",
            description="A past networking event for early-stage founders.",
            start_date=(now - timedelta(days=60)).date(),
            end_date=(now - timedelta(days=60)).date(),
            venue="The Loft Coworking Space",
            is_archived=True,
        )
        self.stdout.write("Created 3 events (1 archived).")

        # (event, [(title, start_time, capacity), ...])
        session_specs = [
            (spring_summit, [
                ("Keynote: The Next Decade", now + timedelta(days=10, hours=9), 8),
                ("Workshop: Hands-on AI", now + timedelta(days=10, hours=13), 4),
                ("Panel: Startup Funding", now + timedelta(days=11, hours=10), 6),
            ]),
            (wellness_fair, [
                ("Morning Yoga", now.replace(hour=8, minute=0, second=0, microsecond=0), 3),
                ("Nutrition Talk", now.replace(hour=11, minute=0, second=0, microsecond=0), 6),
                ("Vendor Showcase", now.replace(hour=14, minute=0, second=0, microsecond=0), 10),
                ("Evening Meditation", now.replace(hour=17, minute=0, second=0, microsecond=0), 3),
            ]),
            (founders_meetup, [
                ("Pitch Practice", now - timedelta(days=60, hours=-10), 5),
                ("Networking Hour", now - timedelta(days=60, hours=-13), 20),
            ]),
        ]

        # Status weights: mostly confirmed/checked-in (realistic for past
        # activity), with a meaningful minority reserved/cancelled/expired.
        status_weights = [
            (Registration.Status.RESERVED, 0.20),
            (Registration.Status.CONFIRMED, 0.25),
            (Registration.Status.CHECKED_IN, 0.30),
            (Registration.Status.CANCELLED, 0.10),
            (Registration.Status.EXPIRED, 0.15),
        ]

        for event, sessions in session_specs:
            for title, start_time, capacity in sessions:
                session = Session.objects.create(
                    event=event, title=title, start_time=start_time,
                    duration_minutes=45, location=f"Room {random.randint(1, 5)}", capacity=capacity,
                )
                StaffAssignment.objects.get_or_create(staff=staff_member, session=session)

                attendee_count = min(capacity, random.randint(2, capacity))
                names_used = random.sample(
                    [random_full_name() for _ in range(attendee_count * 3)], attendee_count
                )

                for i, name in enumerate(names_used):
                    email = email_from_name(name, f"{session.id}{i}")
                    # First attendee always lands "today", so sessions_today
                    # and checked_in_today have something to show without
                    # relying purely on randomness. Rest spread over 30 days.
                    days_ago = 0 if i == 0 else random.randint(0, 29)
                    target_status = random.choices(
                        [s for s, _ in status_weights], weights=[w for _, w in status_weights]
                    )[0]
                    self._create_and_backdate_registration(
                        session, name, email, target_status, days_ago, organizer
                    )

                self.stdout.write(f"  {title}: {attendee_count} registrations")

        # Deliberately fill two sessions to exact capacity for alert testing.
        alert_session_dismissed = Session.objects.create(
            event=wellness_fair, title="Pottery Workshop (Full, Dismissed)",
            start_time=now + timedelta(hours=2), duration_minutes=60, location="Room 6", capacity=2,
        )
        alert_session_active = Session.objects.create(
            event=wellness_fair, title="Live Cooking Demo (Full)",
            start_time=now + timedelta(hours=4), duration_minutes=60, location="Room 7", capacity=2,
        )
        for session in [alert_session_dismissed, alert_session_active]:
            StaffAssignment.objects.get_or_create(staff=staff_member, session=session)
            for i in range(2):
                name = random_full_name()
                reserve_seat(session, name, email_from_name(name, f"alert{session.id}{i}"), created_by=organizer)

        DismissedAlert.objects.create(session=alert_session_dismissed, dismissed_by=organizer)
        self.stdout.write("Created 2 at-capacity sessions (1 alert dismissed, 1 active).")

        self.stdout.write(self.style.SUCCESS("Demo data seeding complete."))

    def _create_and_backdate_registration(self, session, name, email, target_status, days_ago, created_by):
        registration = reserve_seat(session, attendee_name=name, attendee_email=email, created_by=created_by)

        if target_status in (Registration.Status.CONFIRMED, Registration.Status.CHECKED_IN):
            transition(registration, Registration.Status.CONFIRMED, changed_by=created_by)
        if target_status == Registration.Status.CHECKED_IN:
            transition(registration, Registration.Status.CHECKED_IN, changed_by=created_by)
        if target_status == Registration.Status.CANCELLED:
            transition(registration, Registration.Status.CANCELLED, changed_by=created_by, note="Attendee cancelled.")
        if target_status == Registration.Status.EXPIRED:
            transition(registration, Registration.Status.EXPIRED, changed_by=None, note="Auto-expired: hold window elapsed.")

        # Backdate: spread this registration's real events across the
        # target day, spaced a realistic 5-180 minutes apart, in order.
        base_time = timezone.now() - timedelta(days=days_ago, hours=random.randint(0, 20))
        current_time = base_time
        first_event = True
        for event in registration.events.order_by("created_at"):
            RegistrationEvent.objects.filter(pk=event.pk).update(created_at=current_time)
            if first_event:
                Registration.objects.filter(pk=registration.pk).update(reserved_at=current_time)
                first_event = False
            current_time += timedelta(minutes=random.randint(5, 180))