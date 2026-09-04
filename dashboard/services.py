from datetime import timedelta

from django.db.models import Count
from django.db.models.functions import TruncDate
from django.utils import timezone

from events.permissions import visible_sessions_for_user
from events.models import Session
from registrations.models import Registration, RegistrationEvent
from registrations.services import session_is_at_capacity

ALLOWED_CHART_DAY_OPTIONS = [7, 14, 30]
DEFAULT_CHART_DAYS = 14

CHART_SERIES = [
    (Registration.Status.RESERVED, "Reservations", "#fd7e14"),
    (Registration.Status.CONFIRMED, "Confirmations", "#0d6efd"),
    (Registration.Status.CHECKED_IN, "Check-ins", "#198754"),
]


def get_dashboard_stats(user, chart_days=DEFAULT_CHART_DAYS):
    if chart_days not in ALLOWED_CHART_DAY_OPTIONS:
        chart_days = DEFAULT_CHART_DAYS

    sessions = visible_sessions_for_user(user)
    registrations = Registration.objects.filter(session__in=sessions)
    registration_events = RegistrationEvent.objects.filter(registration__session__in=sessions)

    today = timezone.localdate()
    start_of_week = today - timedelta(days=today.weekday())  # Monday

    sessions_today_count = sessions.filter(start_time__date=today).count()

    checked_in_today_count = registration_events.filter(
        new_status=Registration.Status.CHECKED_IN,
        created_at__date=today,
    ).count()

    expired_this_week_count = registration_events.filter(
        new_status=Registration.Status.EXPIRED,
        created_at__date__gte=start_of_week,
    ).count()

    sessions_at_capacity = [s for s in sessions.select_related("event") if session_is_at_capacity(s)]

    status_breakdown = list(
        registrations.values("status").annotate(count=Count("id")).order_by("status")
    )

    session_breakdown = list(
        registrations.values("session__id", "session__title")
        .annotate(count=Count("id"))
        .order_by("-count")
    )

    events_by_status = _events_per_day_by_status(registration_events, chart_days, today)

    return {
        "sessions_today_count": sessions_today_count,
        "checked_in_today_count": checked_in_today_count,
        "expired_this_week_count": expired_this_week_count,
        "sessions_at_capacity": sessions_at_capacity,
        "status_breakdown": status_breakdown,
        "session_breakdown": session_breakdown,
        "events_by_status": events_by_status,
        "chart_days": chart_days,
    }


def _events_per_day_by_status(registration_events, num_days, today):
    start_date = today - timedelta(days=num_days - 1)
    statuses = [status for status, _, _ in CHART_SERIES]

    rows = (
        registration_events.filter(
            new_status__in=statuses,
            created_at__date__gte=start_date,
            created_at__date__lte=today,
        )
        .annotate(day=TruncDate("created_at"))
        .values("day", "new_status")
        .annotate(count=Count("id"))
    )
    
    counts_by_status_and_date = {status: {} for status in statuses}
    for row in rows:
        counts_by_status_and_date[row["new_status"]][row["day"]] = row["count"]
        
    result = {}
    for status in statuses:
        daily_counts = counts_by_status_and_date[status]
        result[status] = [
            (start_date + timedelta(days=i), daily_counts.get(start_date + timedelta(days=i), 0))
            for i in range(num_days)
        ]
    return result