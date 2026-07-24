"""
booking/urls.py
----------------
URL patterns for the booking module's HTML/HTMX views.
Included in config/urls.py under the /booking/ prefix.
"""

from django.urls import path

from booking import views

app_name = "booking"

urlpatterns = [
    # ── Template & Workflow views ─────────────────────────────────────────────
    path("new/", views.BookingFormView.as_view(), name="new-booking"),
    path("my-bookings/", views.MyBookingsView.as_view(), name="my-bookings"),
    path("<int:pk>/", views.BookingDetailView.as_view(), name="booking-detail"),
    path("<int:pk>/cancel/", views.booking_cancel_view, name="booking-cancel"),

    # ── Role Approval Queues ──────────────────────────────────────────────────
    path("approvals/", views.approvals_view, name="approvals"),
    path("allotment/", views.allotment_view, name="allotment"),
    path("approvals/management/", views.management_approvals_view, name="management-approvals"),

    # ── Workflow Action Handlers ──────────────────────────────────────────────
    path("<int:pk>/hod-action/", views.hod_action_view, name="hod-action"),
    path("<int:pk>/allotment-action/", views.allotment_action_view, name="allotment-action"),
    path("<int:pk>/management-action/", views.management_action_view, name="management-action"),
    path("<int:pk>/respond-query/", views.respond_query_view, name="respond-query"),
    path("<int:pk>/alternative-response/", views.alternative_response_view, name="alternative-response"),

    # ── HTMX partials ─────────────────────────────────────────────────────────
    path("htmx/guest-houses/", views.htmx_guest_houses, name="htmx-guest-houses"),
    path("htmx/events/", views.htmx_events_for_campus, name="htmx-events"),
    path("htmx/event-date/", views.htmx_event_date, name="htmx-event-date"),
]
