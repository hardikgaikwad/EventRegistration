from django.db import transaction
from django.utils import timezone

from events.models import Session
from .models import Registration, RegistrationEvent

class TransitionError(Exception):
    pass

class CapacityFullError(Exception):
    pass

ALLOWED_TRANSITIONS = {
    Registration.Status.RESERVED: {
        Registration.Status.CONFIRMED,
        Registration.Status.CANCELLED,
        Registration.Status.EXPIRED,
    },
    Registration.Status.CONFIRMED: {
        Registration.Status.CHECKED_IN,
        Registration.Status.CANCELLED,
    },
    Registration.Status.CHECKED_IN: set(),
    Registration.Status.EXPIRED: set(),
    Registration.Status.CANCELLED: set(),
}

def transition(registration, new_status, changed_by=None, note=None):
    old_status = registration.status
    
    if new_status not in ALLOWED_TRANSITIONS.get(old_status, set()):
        raise TransitionError(
            f"Cannot move a registration from '{old_status}' to '{new_status}'."
        )
        
    with transaction.atomic():
        registration.status = new_status
        registration.save(update_fields=["status", "updated_at"])
        
        RegistrationEvent.objects.create(
            registration=registration,
            old_status=old_status,
            new_status=new_status,
            changed_by=changed_by,
            note=note,
        )
        
    return registration

def compute_seats_taken(session):
    return session.registrations.filter(
        status__in=[
            Registration.Status.RESERVED,
            Registration.Status.CONFIRMED,
            Registration.Status.CHECKED_IN,
        ]
    ).count()
    
def reserve_seat(session, attendee_name, attendee_email, created_by=None):
    with transaction.atomic():
        locked_session = Session.objects.select_for_update().get(pk=session.pk)
        
        seats_taken = compute_seats_taken(locked_session)
        if seats_taken >=locked_session.capacity:
            raise CapacityFullError(
                f'"{locked_session.title}" is at full capacity ({locked_session.capacity} seats).'
            )
            
        registration = Registration.objects.create(
            session=locked_session,
            attendee_name=attendee_name,
            attendee_email=attendee_email,
            status=Registration.Status.RESERVED,
            created_by=created_by,
        )
        
        RegistrationEvent.objects.create(
            registration=registration,
            old_status=None,
            new_status=Registration.Status.RESERVED,
            changed_by=created_by,
            note="Initial reservation.",
        )
        
        return registration