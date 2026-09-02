from django.contrib import admin
from .models import Registration, RegistrationEvent

# Register your models here.

@admin.register(Registration)
class RegistrationAdmin(admin.ModelAdmin):
    list_display = ["attendee_name", "attendee_email", "session", "status", "reserved_at"]
    list_filter = ["status", "session__event"]
    search_fields = ["attendee_name", "attendee_email"]
    
@admin.register(RegistrationEvent)
class RegistrationEventAdmin(admin.ModelAdmin):
    list_display = ["registration", "old_status", "new_status", "changed_by", "created_at"]