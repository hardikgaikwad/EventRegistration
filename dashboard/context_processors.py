from django.db import models

def active_alert_count(request):
    if not request.user.is_authenticated:
        return {"active_alert_count": 0}

    from django.db.models import Q, Count, F
    from events.permissions import visible_sessions_for_user
    from registrations.models import Registration, DismissedAlert

    sessions = visible_sessions_for_user(request.user)
    active_statuses = [
        Registration.Status.RESERVED,
        Registration.Status.CONFIRMED,
        Registration.Status.CHECKED_IN,
    ]
    
    count = (
        sessions
        .annotate(
            seats_taken=Count(
                "registrations",
                filter=Q(registrations__status__in=active_statuses),
            )
        )
        .filter(seats_taken__gte=models.F("capacity"))
        .exclude(pk__in=DismissedAlert.objects.values("session_id"))
        .count()
    )
    
    return {"active_alert_count": count}