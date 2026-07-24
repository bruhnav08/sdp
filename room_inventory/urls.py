from django.urls import path
from room_inventory import views

app_name = "room_inventory"

urlpatterns = [
    # ── API Endpoints ─────────────────────────────────────────────────────────
    path("campuses/", views.CampusListView.as_view(), name="campus-list"),
    path("guest-houses/", views.GuestHouseListView.as_view(), name="guest-house-list"),
    path("availability/", views.RoomAvailabilityView.as_view(), name="room-availability"),
    path("events/", views.EventListView.as_view(), name="event-list"),

    # ── Guest House Management ────────────────────────────────────────────────
    path("guest-houses/manage/", views.guesthouse_list, name="guesthouse-list"),
    path("guest-houses/add/", views.guesthouse_create, name="guesthouse-create"),
    path("guest-houses/<int:pk>/edit/", views.guesthouse_edit, name="guesthouse-edit"),
    path("guest-houses/<int:pk>/delete/", views.guesthouse_delete, name="guesthouse-delete"),
    path("guest-houses/<int:pk>/rooms/", views.guesthouse_rooms, name="guesthouse-rooms"),

    # ── Room Category Management ──────────────────────────────────────────────
    path("categories/", views.category_list, name="category-list"),
    path("categories/add/", views.category_create, name="category-create"),
    path("categories/<int:pk>/edit/", views.category_edit, name="category-edit"),
    path("categories/<int:pk>/delete/", views.category_delete, name="category-delete"),

    # ── Room Management ───────────────────────────────────────────────────────
    path("rooms/", views.room_list, name="room-list"),
    path("rooms/add/", views.room_create, name="room-create"),
    path("rooms/<int:pk>/edit/", views.room_edit, name="room-edit"),
    path("rooms/<int:pk>/delete/", views.room_delete, name="room-delete"),

    # ── Amenity Management ────────────────────────────────────────────────────
    path("amenities/", views.amenity_list_create, name="amenity-list"),
]
