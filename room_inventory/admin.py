from django.contrib import admin

from room_inventory.models import Amenity, Campus, Event, GuestHouse, Room, RoomCategory


@admin.register(Campus)
class CampusAdmin(admin.ModelAdmin):
    list_display = ("name", "location", "is_active")
    list_filter = ("is_active",)
    search_fields = ("name", "location")


@admin.register(GuestHouse)
class GuestHouseAdmin(admin.ModelAdmin):
    list_display = ("name", "campus", "total_rooms", "is_active")
    list_filter = ("is_active", "campus")
    search_fields = ("name",)


@admin.register(RoomCategory)
class RoomCategoryAdmin(admin.ModelAdmin):
    list_display = ("name", "guest_house", "default_capacity", "is_active")
    list_filter = ("is_active", "guest_house")
    search_fields = ("name",)


@admin.register(Amenity)
class AmenityAdmin(admin.ModelAdmin):
    list_display = ("name", "icon", "is_active")
    list_filter = ("is_active",)
    search_fields = ("name",)


@admin.register(Room)
class RoomAdmin(admin.ModelAdmin):
    list_display = ("room_number", "guest_house", "floor", "capacity", "room_category", "status", "is_active")
    list_filter = ("status", "is_active", "guest_house", "room_category")
    search_fields = ("room_number", "guest_house__name")
    filter_horizontal = ("amenities",)


@admin.register(Event)
class EventAdmin(admin.ModelAdmin):
    list_display = ("name", "event_date", "campus", "is_active")
    list_filter = ("is_active", "campus")
    search_fields = ("name",)
    date_hierarchy = "event_date"

