from django.db import models

# Create your models here.

class Event(models.Model):
    name = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    start_date = models.DateField()
    end_date = models.DateField()
    venue = models.CharField(max_length=200)
    is_archived = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ["-start_date"]
        
    def __str__(self):
        return self.name
    
class Session(models.Model):
    event = models.ForeignKey(Event, on_delete=models.CASCADE, related_name="sessions")
    title = models.CharField(max_length=200)
    start_time = models.DateTimeField()
    duration_minutes = models.PositiveIntegerField()
    location = models.CharField(max_length=200)
    capacity = models.PositiveIntegerField()
    
    class Meta:
        ordering = ["start_time"]
        
    def __str__(self):
        return f"{self.title} ({self.event.name})"