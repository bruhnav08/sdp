from django.contrib import admin

from room_inventory.models import Campus, Event, GuestHouse


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


@admin.register(Event)
class EventAdmin(admin.ModelAdmin):
    list_display = ("name", "event_date", "campus", "is_active")
    list_filter = ("is_active", "campus")
    search_fields = ("name",)
    date_hierarchy = "event_date"
