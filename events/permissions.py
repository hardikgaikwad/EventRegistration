from django.core.exceptions import PermissionDenied

def user_is_organizer(user):
    return user.is_authenticated and user.role == user.Role.ORGANIZER

def require_organizer(user):
    if not user_is_organizer(user):
        raise PermissionDenied("Only organizers can perform this action.")