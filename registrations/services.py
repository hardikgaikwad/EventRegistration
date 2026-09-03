from datetime import timedelta

import csv

from django.conf import settings
from django.db import transaction
from django.utils import timezone
from django.core.exceptions import ValidationError
from django.core.validators import EmailValidator

from events.models import Session
from .models import Registration, RegistrationEvent, DismissedAlert

class TransitionError(Exception):
    pass

class CapacityFullError(Exception):
    pass

class DuplicateRegistrationError(Exception):
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

def session_is_at_capacity(session):
    return compute_seats_taken(session) >= session.capacity

def session_alert_is_active(session):
    return session_is_at_capacity(session) and not session.dismissed_alerts.exists()

def clear_dismissed_alert_if_below_capacity(session):
    if compute_seats_taken(session) < session.capacity:
        DismissedAlert.objects.filter(session=session).delete()

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
        
        clear_dismissed_alert_if_below_capacity(registration.session)
        
    return registration

def compute_seats_taken(session):
    return session.registrations.filter(
        status__in=[
            Registration.Status.RESERVED,
            Registration.Status.CONFIRMED,
            Registration.Status.CHECKED_IN,
        ]
    ).count()
    
def expire_stale_reservations(session):
    cutoff = timezone.now() - timedelta(minutes=settings.RESERVATION_HOLD_MINUTES)
    
    stale_registrations = session.registrations.filter(
        status=Registration.Status.RESERVED,
        reserved_at__lt=cutoff,
    )
    
    expired_count = 0
    for registration in stale_registrations:
        transition(registration, Registration.Status.EXPIRED, changed_by=None, note="Auto-expired: hold window elapsed.")
        expired_count += 1
    
    return expired_count
    
def reserve_seat(session, attendee_name, attendee_email, created_by=None):
    with transaction.atomic():
        locked_session = Session.objects.select_for_update().get(pk=session.pk)
        
        expire_stale_reservations(locked_session)
        
        already_registered = locked_session.registrations.filter(
            attendee_email__iexact=attendee_email
        ).exclude(
            status__in=[Registration.Status.CANCELLED, Registration.Status.EXPIRED]
        ).exists()
        if already_registered:
            raise DuplicateRegistrationError(
                f"'{attendee_email}' is already registered for this session."
            )
        
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
    
def import_registrations_from_csv(session, csv_file, created_by=None):
    decoded_text = csv_file.read().decode("utf-8-sig")
    reader = csv.DictReader(decoded_text.splitlines())
    email_validator = EmailValidator()
    
    report = []
    
    for row_number, row in enumerate(reader, start=2):
        name = (row.get("name") or "").strip()
        email = (row.get("email") or "").strip()
        
        if not name or not email:
            report.append({
                "row_number": row_number, "name": name, "email": email,
                "outcome": "rejected", "reason": "Missing name or email.",
            })
            continue
        
        try:
            email_validator(email)
        except ValidationError:
            report.append({
                "row_number": row_number, "name": name, "email": email,
                "outcome": "rejected", "reason": "Invalid email format.",
            })
            continue
        
        try:
            reserve_seat(session, attendee_name=name, attendee_email=email, created_by=created_by)
            report.append({
                "row_number": row_number, "name": name, "email": email,
                "outcome": "created", "reason": None,
            })
        except DuplicateRegistrationError:
            report.append({
                "row_number": row_number, "name": name, "email": email,
                "outcome": "duplicate", "reason": "Already registered for this session.",
            })
        except CapacityFullError as e:
            report.append({
                "row_number": row_number, "name": name, "email": email,
                "outcome": "rejected", "reason": str(e),
            })
    
    return report

def build_session_roster_csv_rows(session):
    yield ("Attendee Name", "Attendee Email", "Status", "Reserved At")
    for registration in session.registrations.all().order_by("attendee_name"):
        yield (
            registration.attendee_name,
            registration.attendee_email,
            registration.get_status_display(),
            registration.reserved_at.isoformat(),
        )