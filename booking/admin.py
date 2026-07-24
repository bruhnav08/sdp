"""
booking/admin.py
-----------------
Django Admin registrations for the booking app.
"""

from django.contrib import admin
from django.utils.html import format_html

from booking.models import AlternateContact, ApprovalHistory, BookingRequest, Guest, NotificationLog


class GuestInline(admin.TabularInline):
    model = Guest
    extra = 0
    fields = ("name", "gender", "guest_type", "email", "mobile", "check_in", "check_out")
    readonly_fields = ("created_at",)


class AlternateContactInline(admin.TabularInline):
    model = AlternateContact
    extra = 0
    fields = ("name", "mobile", "email")
    max_num = 4


class ApprovalHistoryInline(admin.TabularInline):
    model = ApprovalHistory
    extra = 0
    readonly_fields = ("user_name", "role", "action", "comments", "previous_status", "new_status", "created_at")
    can_delete = False


@admin.register(BookingRequest)
class BookingRequestAdmin(admin.ModelAdmin):
    list_display = (
        "booking_id",
        "requestor",
        "campus_name",
        "status_badge",
        "num_rooms_required",
        "total_guests",
        "is_foreign_guest",
        "created_at",
    )
    list_filter = ("status", "is_foreign_guest", "campus_name", "food_arrangement")
    search_fields = ("booking_id", "requestor__username", "requestor__email", "campus_name")
    readonly_fields = (
        "booking_id",
        "status",
        "requestor",
        "rejection_stage",
        "rejected_by",
        "hod_approved_by",
        "allotted_by",
        "management_approved_by",
        "created_at",
        "updated_at",
    )
    ordering = ("-created_at",)
    inlines = [GuestInline, AlternateContactInline, ApprovalHistoryInline]

    fieldsets = (
        ("Identity", {"fields": ("booking_id", "status", "requestor")}),
        (
            "Requestor Details",
            {"fields": ("mobile_number", "is_faculty_incharge", "incharge_name", "incharge_email", "incharge_mobile")},
        ),
        (
            "Event & Campus",
            {"fields": ("campus_id", "campus_name", "purpose_of_booking", "event_id", "event_name", "event_date", "event_type")},
        ),
        (
            "Guest Summary",
            {"fields": ("num_guests_male", "num_guests_female", "num_rooms_required", "is_foreign_guest")},
        ),
        (
            "Guest House & Allotment",
            {
                "fields": (
                    "preferred_guest_house_id",
                    "preferred_guest_house_name",
                    "room_configuration",
                    "allotted_room",
                    "allotted_guest_house",
                    "proposed_room",
                    "proposed_guest_house",
                    "proposed_note",
                    "special_requests",
                )
            },
        ),
        (
            "Queries & Holds",
            {"fields": ("query_text", "query_stage", "query_response", "hold_reason"), "classes": ("collapse",)},
        ),
        (
            "Arrangements",
            {
                "fields": (
                    "food_arrangement",
                    "travel_arrangement",
                    "local_transport_arrangement",
                    "payment_arrangement",
                    "room_sharing_grouping",
                )
            },
        ),
        (
            "Rejection & Approvers",
            {
                "fields": (
                    "rejection_reason",
                    "rejected_by",
                    "rejection_stage",
                    "hod_approved_by",
                    "allotted_by",
                    "management_approved_by",
                ),
                "classes": ("collapse",),
            },
        ),
        ("Timestamps", {"fields": ("created_at", "updated_at"), "classes": ("collapse",)}),
    )

    def status_badge(self, obj):
        colours = {
            "DRAFT": "#94a3b8",
            "PENDING_HOD_APPROVAL": "#f59e0b",
            "PENDING_ALLOTMENT": "#3b82f6",
            "ALTERNATIVE_PROPOSED": "#0284c7",
            "PENDING_MANAGEMENT_APPROVAL": "#8b5cf6",
            "ON_HOLD": "#d97706",
            "QUERY_RAISED": "#ea580c",
            "CONFIRMED": "#10b981",
            "REJECTED": "#ef4444",
            "CANCELLED": "#64748b",
        }
        colour = colours.get(obj.status, "#94a3b8")
        return format_html(
            '<span style="background:{};color:#fff;padding:2px 8px;border-radius:4px;font-size:12px">{}</span>',
            colour,
            obj.get_status_display(),
        )

    status_badge.short_description = "Status"
    status_badge.admin_order_field = "status"

    def total_guests(self, obj):
        return obj.total_guests

    total_guests.short_description = "Guests"


@admin.register(Guest)
class GuestAdmin(admin.ModelAdmin):
    list_display = ("name", "booking", "gender", "guest_type", "check_in", "check_out")
    list_filter = ("gender", "guest_type")
    search_fields = ("name", "email", "booking__booking_id")


@admin.register(AlternateContact)
class AlternateContactAdmin(admin.ModelAdmin):
    list_display = ("name", "mobile", "email", "booking")
    search_fields = ("name", "booking__booking_id")


@admin.register(ApprovalHistory)
class ApprovalHistoryAdmin(admin.ModelAdmin):
    list_display = ("booking", "action", "user_name", "role", "previous_status", "new_status", "created_at")
    list_filter = ("action", "role", "previous_status", "new_status")
    search_fields = ("booking__booking_id", "user_name", "comments")


@admin.register(NotificationLog)
class NotificationLogAdmin(admin.ModelAdmin):
    list_display = ("user", "title", "booking", "is_read", "created_at")
    list_filter = ("is_read", "created_at")
    search_fields = ("user__username", "title", "message")
