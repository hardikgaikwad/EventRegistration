from django.contrib import admin
from .models import Event, Session

# Register your models here.

@admin.register(Event)
class EventAdmin(admin.ModelAdmin):
    list_display = ["name", "start_date", "end_date", "venue", "is_archived"]
    list_filter = ["is_archived"]
    search_fields = ["name", "venue"]
    
@admin.register(Session)
class SessionAdmin(admin.ModelAdmin):
    list_display = ["title", "event", "start_time", "duration_minutes", "location", "capacity"]
    list_filter = ["event"]