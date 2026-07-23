"""
booking/urls.py
----------------
URL patterns for the booking module's HTML/HTMX views.
Included in config/urls.py under the /booking/ prefix.

The DRF REST API for bookings is registered separately in config/urls.py
under /api/bookings/ via a DefaultRouter — do not add a second router here.

app_name = "booking" ensures all names are scoped:
    {% url "booking:my-bookings" %}
    {% url "booking:new-booking" %}
"""

from django.urls import path

from booking import views

app_name = "booking"

urlpatterns = [
    # ── Template (HTMX) views ─────────────────────────────────────────────────
    path("new/", views.BookingFormView.as_view(), name="new-booking"),
    path("my-bookings/", views.MyBookingsView.as_view(), name="my-bookings"),
    path("<int:pk>/", views.BookingDetailView.as_view(), name="booking-detail"),
    path("<int:pk>/cancel/", views.booking_cancel_view, name="booking-cancel"),

    # ── Stub views for other roles (not yet built) ────────────────────────────
    path("approvals/", views.approvals_view, name="approvals"),
    path("approvals/management/", views.management_approvals_view, name="management-approvals"),
    path("allotment/", views.allotment_view, name="allotment"),

    # ── HTMX partials ─────────────────────────────────────────────────────────
    path("htmx/guest-houses/", views.htmx_guest_houses, name="htmx-guest-houses"),
    path("htmx/events/", views.htmx_events_for_campus, name="htmx-events"),
    path("htmx/event-date/", views.htmx_event_date, name="htmx-event-date"),
]
