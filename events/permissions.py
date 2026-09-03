from django.core.exceptions import PermissionDenied

def user_is_organizer(user):
    return user.is_authenticated and user.role == user.Role.ORGANIZER

def require_organizer(user):
    if not user_is_organizer(user):
        raise PermissionDenied("Only organizers can perform this action.")
    
def user_can_manage_session(user, session):
    if not user.is_authenticated:
        return False
    if user_is_organizer(user):
        return True
    return session.staff_assignments.filter(staff=user).exists()

def require_session_access(user, session):
    if not user_can_manage_session(user, session):
        raise PermissionDenied("You are not assigned to this session.")
    
def visible_sessions_for_user(user):
    from .models import Session
    
    if not user.is_authenticated:
        return Session.objects.none()
    if user_is_organizer(user):
        return Session.objects.all()
    return Session.objects.filter(staff_assignments__staff=user)