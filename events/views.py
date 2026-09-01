from django.contrib.auth.decorators import login_required
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib import messages

from .forms import EventForm
from .models import Event
from .permissions import require_organizer

# Create your views here.

@login_required
def event_list(request):
    show_archived = request.GET.get("show_archived") == "1"
    events = Event.objects.all()
    if not show_archived:
        events = events.filter(is_archived=False)
    return render(request, "events/event_list.html", {
        "events": events,
        "show_archived": show_archived,
    })
    
@login_required
def event_detail(request, event_id):
    event = get_object_or_404(Event, pk=event_id)
    return render(request, "events/event_detail.html", {"event": event})

@login_required
def event_create(request):
    require_organizer(request.user)
    if request.method == "POST":
        form = EventForm(request.POST)
        if form.is_valid():
            event = form.save()
            messages.success(request, f"Event '{event.name}' created.")
            return redirect("events:event_detail", event_id=event.pk)
    else:
        form = EventForm()
    return render(request, "events/event_form.html", {"form": form, "is_create": True})

@login_required
def event_update(request, event_id):
    require_organizer(request.user)
    event = get_object_or_404(Event, pk=event_id)
    if request.method == "POST":
        form = EventForm(request.POST, instance=event)
        if form.is_valid():
            form.save()
            messages.success(request, f"Event '{event.name}' updated.")
            return redirect("events:event_detail", event_id=event.pk)
    else:
        form = EventForm(instance=event)
    return render(request, "events/event_form.html", {"form": form, "is_create": False, "event": event})

@login_required
def event_archive(request, event_id):
    require_organizer(request.user)
    event = get_object_or_404(Event, pk=event_id)
    if request.method == "POST":
        event.is_archived = True
        event.save()
        messages.success(request, f"Event '{event.name}' archived.")
    return redirect("events:event_list")

@login_required
def event_restore(request, event_id):
    require_organizer(request.user)
    event = get_object_or_404(Event, pk=event_id)
    if request.method == "POST":
        event.is_archived = False
        event.save()
        messages.success(request, f"Event '{event.name} restored.")
    return redirect("events:event_list")