from django.shortcuts import render, get_object_or_404, redirect
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Q
from django.conf import settings

from events.models import Session, Event, StaffAssignment
from events.permissions import require_session_access, user_is_organizer
from .forms import RegistrationForm
from .models import Registration
from .services import (
    CapacityFullError,
    TransitionError,
    reserve_seat,
    transition,
)

# Create your views here.

@login_required
def registration_create(request, session_id):
    session = get_object_or_404(Session, pk=session_id)
    require_session_access(request.user, session)
    
    if request.method == "POST":
        form = RegistrationForm(request.POST)
        if form.is_valid():
            try:
                reserve_seat(
                    session,
                    attendee_name=form.cleaned_data["attendee_name"],
                    attendee_email=form.cleaned_data["attendee_email"],
                    created_by=request.user,
                )
                messages.success(request, "Registration reserved.")
                return redirect("events:session_detail", event_id=session.event_id, session_id=session.id)
            except CapacityFullError as e:
                messages.error(request, str(e))
                
    else:
        form = RegistrationForm()
        
    return render(request, "registrations/registration_form.html", {"form": form, "session": session})

@login_required
def registration_confirm(request, registration_id):
    registration = get_object_or_404(Registration, pk=registration_id)
    require_session_access(request.user, registration.session)
    if request.method == "POST":
        try:
            transition(registration, Registration.Status.CONFIRMED, changed_by=request.user)
            messages.success(request, f"{registration.attendee_name} confirmed.")
        except TransitionError as e:
            messages.error(request, str(e))
    return redirect(
        "events:session_detail",
        event_id=registration.session.event_id,
        session_id=registration.session_id,
    )
    
@login_required
def registration_check_in(request, registration_id):
    registration = get_object_or_404(Registration, pk=registration_id)
    require_session_access(request.user, registration.session)
    if request.method == "POST":
        try:
            transition(registration, Registration.Status.CHECKED_IN, changed_by=request.user)
            messages.success(request, f"{registration.attendee_name} checked_in.")
        except TransitionError as e:
            messages.error(request, str(e))
    return redirect(
        "events:session_detail",
        event_id=registration.session.event_id,
        session_id=registration.session_id,
    )
    
@login_required
def registration_cancel(request, registration_id):
    registration = get_object_or_404(Registration, pk=registration_id)
    require_session_access(request.user, registration.session)
    if request.method == "POST":
        try:
            transition(registration, Registration.Status.CANCELLED, changed_by=request.user)
            messages.success(request, f"{registration.attendee_name}'s registration cancelled.")
        except TransitionError as e:
            messages.error(request, str(e))
    return redirect(
        "events:session_detail",
        event_id=registration.session.event_id,
        session_id=registration.session_id,
    )
    
@login_required
def registration_list(request):
    if user_is_organizer(request.user):
        registrations = Registration.objects.select_related("session", "session__event")
    else:
        assigned_session_ids = StaffAssignment.objects.filter(
            staff=request.user
        ).values_list("session_id", flat=True)
        registrations = Registration.objects.filter(
            session_id__in=assigned_session_ids
        ).select_related("session", "session__event")
        
    search_query = request.GET.get("q", "").strip()
    if search_query:
        registrations = registrations.filter(
            Q(attendee_name__icontains=search_query) | Q(attendee_email__icontains=search_query)
        )
        
    if user_is_organizer(request.user):
        visible_events = Event.objects.all()
        visible_sessions = Session.objects.all()
    else:
        visible_events = Event.objects.filter(sessions__id__in=assigned_session_ids).distinct()
        visible_sessions = Session.objects.filter(id__in=assigned_session_ids)
        
    selected_event_id = request.GET.get("event", "")
    if selected_event_id:
        registrations = registrations.filter(session__event_id=selected_event_id)
    
    selected_status = request.GET.get("status", "")
    if selected_status:
        registrations = registrations.filter(status=selected_status)
        
    selected_session_id = request.GET.get("session", "")
    if selected_session_id:
        registrations = registrations.filter(session_id=selected_session_id)
        
    registrations = registrations.order_by("-reserved_at")
    
    paginator = Paginator(registrations, settings.REGISTRATIONS_PAGE_SIZE)
    page_number = request.GET.get("page", 1)
    page = paginator.get_page(page_number)
    
    return render(request, "registrations/registration_list.html", {
        "page": page,
        "total_count": paginator.count,
        "visible_events": visible_events,
        "visible_sessions": visible_sessions,
        "search_query": search_query,
        "selected_event_id": selected_event_id,
        "selected_status": selected_status,
        "selected_session_id": selected_session_id,
        "status_choices": Registration.Status.choices,
    })