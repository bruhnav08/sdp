"""
room_inventory/urls.py
-----------------------
Stub URL patterns for the room_inventory integration contract.
Included in config/urls.py under /api/rooms/.

app_name = "room_inventory"
"""

from django.urls import path

from room_inventory import views

app_name = "room_inventory"

urlpatterns = [
    path("campuses/", views.CampusListView.as_view(), name="campus-list"),
    path("guest-houses/", views.GuestHouseListView.as_view(), name="guest-house-list"),
    path("availability/", views.RoomAvailabilityView.as_view(), name="room-availability"),
    path("events/", views.EventListView.as_view(), name="event-list"),
]
