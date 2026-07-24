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
    campus = models.ForeignKey(
        Campus, on_delete=models.SET_NULL, null=True, blank=True, related_name="guest_houses"
    )
    total_rooms = models.PositiveIntegerField(default=0)
    contact_number = models.CharField(max_length=15, blank=True)
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        verbose_name = "Guest House"
        verbose_name_plural = "Guest Houses"
        ordering = ["name"]

    def __str__(self) -> str:
        if self.campus:
            return f"{self.name} ({self.campus.name})"
        return self.name

    def update_total_rooms_count(self):
        """Recalculate total rooms based on actual Room instances."""
        self.total_rooms = self.rooms.filter(is_active=True).count()
        self.save(update_fields=["total_rooms", "updated_at"])


class RoomCategory(TimeStampedModel):
    """
    Room category (e.g., Single, Double King, Double Queen, Double Twin).
    Can be associated with a specific GuestHouse.
    """

    name = models.CharField(max_length=100)
    guest_house = models.ForeignKey(
        GuestHouse, on_delete=models.CASCADE, null=True, blank=True, related_name="categories"
    )
    description = models.TextField(blank=True)
    default_capacity = models.PositiveIntegerField(default=1)
    is_active = models.BooleanField(default=True)

    class Meta:
        verbose_name = "Room Category"
        verbose_name_plural = "Room Categories"
        ordering = ["name"]

    def __str__(self) -> str:
        if self.guest_house:
            return f"{self.name} - {self.guest_house.name}"
        return self.name


class Amenity(TimeStampedModel):
    """
    Room amenities (Wi-Fi, AC, Attached Bathroom, TV, etc.).
    Extensible design allowing additional amenities to be added.
    """

    name = models.CharField(max_length=100, unique=True)
    icon = models.CharField(max_length=50, blank=True, help_text="Optional icon identifier or emoji")
    is_active = models.BooleanField(default=True)

    class Meta:
        verbose_name = "Amenity"
        verbose_name_plural = "Amenities"
        ordering = ["name"]

    def __str__(self) -> str:
        return self.name


class Room(TimeStampedModel):
    """
    Individual guest room inside a GuestHouse.
    """

    class Status(models.TextChoices):
        VACANT_CLEAN = "VACANT_CLEAN", "Vacant Clean"
        VACANT_DIRTY = "VACANT_DIRTY", "Vacant Dirty"
        CLEANING_IN_PROGRESS = "CLEANING_IN_PROGRESS", "Cleaning In Progress"
        OCCUPIED = "OCCUPIED", "Occupied"
        UNDER_MAINTENANCE = "UNDER_MAINTENANCE", "Under Maintenance"
        BLOCKED = "BLOCKED", "Blocked"

    room_number = models.CharField(max_length=50)
    floor = models.CharField(max_length=20, default="1")
    capacity = models.PositiveIntegerField(default=1)
    guest_house = models.ForeignKey(
        GuestHouse, on_delete=models.CASCADE, related_name="rooms"
    )
    room_category = models.ForeignKey(
        RoomCategory, on_delete=models.SET_NULL, null=True, blank=True, related_name="rooms"
    )
    amenities = models.ManyToManyField(Amenity, blank=True, related_name="rooms")
    status = models.CharField(
        max_length=30,
        choices=Status.choices,
        default=Status.VACANT_CLEAN,
        db_index=True,
    )
    is_active = models.BooleanField(default=True)

    class Meta:
        verbose_name = "Room"
        verbose_name_plural = "Rooms"
        ordering = ["guest_house", "room_number"]
        unique_together = [["guest_house", "room_number"]]

    def __str__(self) -> str:
        return f"Room {self.room_number} ({self.guest_house.name})"

    @property
    def is_available_for_booking(self) -> bool:
        """
        Only rooms marked as Vacant Clean are available for new bookings.
        Under Maintenance, Vacant Dirty, Cleaning In Progress, Occupied, and Blocked are NOT available.
        """
        return self.is_active and self.status in (self.Status.VACANT_CLEAN, "AVAILABLE")


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

