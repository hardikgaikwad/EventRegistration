from django.core.management.base import BaseCommand

from events.models import Session
from registrations.services import expire_stale_reservations

class Command(BaseCommand):
    help = "Expire stale 'reserved' registrations across every session, freeing their seats."
    
    def handle(self, *args, **options):
        total_expired = 0
        sessions_affected = 0
        
        for session in Session.objects.all():
            count = expire_stale_reservations(session)
            if count:
                sessions_affected += 1
                total_expired += count
                self.stdout.write(f"    {session.title} (event: {session.event.name}): expired {count}")
                
        self.stdout.write(self.style.SUCCESS(
            f"Done. {total_expired} registration(s) expired across {sessions_affected} session(s)."
        ))