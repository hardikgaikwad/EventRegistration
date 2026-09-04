from django.contrib import admin
from .models import Registration, RegistrationEvent, DismissedAlert

# Register your models here.

@admin.register(Registration)
class RegistrationAdmin(admin.ModelAdmin):
    list_display = ["attendee_name", "attendee_email", "session", "status", "reserved_at"]
    list_filter = ["status", "session__event"]
    search_fields = ["attendee_name", "attendee_email"]
    readonly_fields = ["status", "session", "reserved_at", "created_by", "updated_at"]
    
@admin.register(RegistrationEvent)
class RegistrationEventAdmin(admin.ModelAdmin):
    list_display = ["registration", "old_status", "new_status", "changed_by", "created_at"]
    list_filter = ["new_status"]
    readonly_fields = ["registration", "old_status", "new_status", "changed_by", "note", "created_at"]
    
    def has_add_permission(self, request):
        return False
    
    def has_change_permission(self, request, obj=None):
        return False
    
    def has_delete_permission(self, request, obj=None):
        return False
    
@admin.register(DismissedAlert)
class DismissedAlertAdmin(admin.ModelAdmin):
    list_display = ["session", "dismissed_by", "dismissed_at"]