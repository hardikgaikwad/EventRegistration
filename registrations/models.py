from django.db import models
from django.conf import settings

from events.models import Session

# Create your models here.

class Registration(models.Model):
    class Status(models.TextChoices):
        RESERVED = "reserved", "Reserved"
        CONFIRMED = "confirmed", "Confirmed"
        CHECKED_IN = "checked_in", "Checked_in"
        EXPIRED = "expired", "Expired"
        CANCELLED = "cancelled", "Cancelled"
        
    session = models.ForeignKey(Session, on_delete=models.CASCADE, related_name="registrations")
    attendee_name = models.CharField(max_length=200)
    attendee_email = models.EmailField()
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.RESERVED)
    reserved_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="created_registrations",    
    )
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ["-reserved_at"]
        
    def __str__(self):
        return f"{self.attendee_name} <{self.attendee_email}> — {self.session.title} ({self.status})"
    
class RegistrationEvent(models.Model):
    registration = models.ForeignKey(Registration, on_delete=models.CASCADE, related_name="events")
    old_status = models.CharField(max_length=20, choices=Registration.Status.choices, null=True, blank=True)
    new_status = models.CharField(max_length=20, choices=Registration.Status.choices)
    changed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="registration_changes",
    )
    note = models.TextField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ["created_at"]
        
    def __str__(self):
        return f"{self.registration_id}: {self.old_status} -> {self.new_status}"