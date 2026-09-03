def active_alert_count(request):
    if not request.user.is_authenticated:
        return {"active_alert_count": 0}

    from events.permissions import visible_sessions_for_user
    from registrations.services import session_alert_is_active

    sessions = visible_sessions_for_user(request.user).select_related("event")
    count = sum(1 for session in sessions if session_alert_is_active(session))
    return {"active_alert_count": count}