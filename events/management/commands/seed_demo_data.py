from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import timedelta

from accounts.models import User
from events.models import Event, Session, StaffAssignment
from registrations.models import Registration
from registrations.services import reserve_seat, transition

class Command(BaseCommand):
    help = "Populates the database with a small set of realistic demo data."
    
    def handle(self, *args, **options):
        organizer, _ = User.objects.get_or_create(
            email="organizer@example.com",
            defaults={"role": User.Role.ORGANIZER, "is_staff": True, "is_superuser": True}
        )
        organizer.set_password("demo1234")
        organizer.save()
        
        staff_member, _ = User.objects.get_or_create(
            email="staff@example.com", defaults={"role": User.Role.STAFF}
        )
        staff_member.set_password("test1234")
        staff_member.save()
        
        self.stdout.write(f"Organizer: {organizer.email} / demo1234")
        self.stdout.write(f"Staff:     {staff_member.email} / test1234")
        
        now = timezone.now()
        
        event_specs = [
            {
                "name": "Spring Tech Summit",
                "description": "A two-day conference on emerging technology.",
                "start_date": (now + timedelta(days=10)).date(),
                "end_date": (now + timedelta(days=11)).date(),
                "venue": "Downtown Convention Center",
                "session_count": 3,
            },
            {
                "name": "Community Wellness Fair",
                "description": "A single-day event for local health and wellness vendors.",
                "start_date": (now + timedelta(days=20)).date(),
                "end_date": (now + timedelta(days=20)).date(),
                "venue": "City Park Pavilion",
                "session_count": 4,
            },
        ]
        
        for event_spec in event_specs:
            session_count = event_spec.pop("session_count")
            event, created = Event.objects.get_or_create(
                name=event_spec["name"], defaults=event_spec
            )
            if not created:
                self.stdout.write(f"Event '{event.name}' already exists, skipping creation.")
                continue
            
            self.stdout.write(f"Created event: {event.name}")
            
            for i in range(1, session_count + 1):
                session = Session.objects.create(
                    event=event,
                    title=f"{event.name} — Session {i}",
                    start_time=now + timedelta(days=10, hours=i),
                    duration_minutes=45,
                    location=f"Room {i}",
                    capacity=5,
                )
                StaffAssignment.objects.get_or_create(staff=staff_member, session=session)
                self.stdout.write(f"  Created session: {session.title} (capacity {session.capacity})")
                
                for j in range(1, 6):
                    registration = reserve_seat(
                        session,
                        attendee_name=f"Attendee {j} of {session.title}",
                        attendee_email=f"attendee{j}.{event.id}.{session.id}@example.com",
                        created_by=organizer,
                    )
                    if j == 2:
                        transition(registration, Registration.Status.CONFIRMED, changed_by=organizer)
                    elif j == 3:
                        transition(registration, Registration.Status.CONFIRMED, changed_by=organizer)
                        transition(registration, Registration.Status.CHECKED_IN, changed_by=staff_member)
                    elif j == 4:
                        transition(registration, Registration.Status.CANCELLED, changed_by=organizer)
                        
                self.stdout.write(f"    Created 5 registrations across varied statuses")

        self.stdout.write(self.style.SUCCESS("Demo data seeding complete."))