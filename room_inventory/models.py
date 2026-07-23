"""
room_inventory/models.py
-------------------------
STUB — minimal models that give the booking module something concrete to call
against during development.

This app will be replaced / expanded by a teammate.  Do NOT add business
logic here.  The real implementation must conform to the integration contract
documented in README.md § Integration Contracts.

Interface contract (what the booking module expects):
    Campus.objects.all()  → QuerySet of Campus
    GuestHouse.objects.filter(campus=<campus>)  → QuerySet of GuestHouse
    Event.objects.filter(campus=<campus>)  → QuerySet of Event
"""

from django.db import models

from common.models import TimeStampedModel


class Campus(TimeStampedModel):
    """A physical campus of the university."""

    name = models.CharField(max_length=150)
    location = models.CharField(max_length=200, blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        verbose_name = "Campus"
        verbose_name_plural = "Campuses"
        ordering = ["name"]

    def __str__(self) -> str:
        return self.name


class GuestHouse(TimeStampedModel):
    """A guest house facility on a campus."""

    name = models.CharField(max_length=200)
    campus = models.ForeignKey(Campus, on_delete=models.CASCADE, related_name="guest_houses")
    total_rooms = models.PositiveIntegerField(default=0)
    contact_number = models.CharField(max_length=15, blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        verbose_name = "Guest House"
        verbose_name_plural = "Guest Houses"
        ordering = ["campus", "name"]

    def __str__(self) -> str:
        return f"{self.name} ({self.campus.name})"


class Event(TimeStampedModel):
    """
    An institutional event that may drive a guest room booking.
    The booking form lets requestors select an event and auto-fills the date.
    """

    name = models.CharField(max_length=250)
    event_date = models.DateField()
    campus = models.ForeignKey(
        Campus, on_delete=models.SET_NULL, null=True, blank=True, related_name="events"
    )
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        verbose_name = "Event"
        verbose_name_plural = "Events"
        ordering = ["event_date"]

    def __str__(self) -> str:
        return f"{self.name} ({self.event_date})"
