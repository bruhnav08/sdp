from django.contrib import admin
from housekeeping.models import RoomStatusHistory


@admin.register(RoomStatusHistory)
class RoomStatusHistoryAdmin(admin.ModelAdmin):
    list_display = ("room", "previous_status", "new_status", "changed_by", "timestamp")
    list_filter = ("new_status", "previous_status", "timestamp")
    search_fields = ("room__room_number", "room__guest_house__name", "changed_by__username")
    readonly_fields = ("timestamp",)
