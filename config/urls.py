"""
config/urls.py
--------------
Root URL configuration.  Each app owns its own urls.py included here
under a clear namespace prefix so route names never collide across modules.

Pattern:
    /accounts/      → accounts app (login, dashboard, profile)
    /booking/       → booking app (HTML views)
    /api/bookings/  → booking DRF endpoints
    /api/rooms/     → room_inventory stub DRF endpoints
    /api/housekeeping/ → housekeeping stub DRF endpoints
    /api/token/     → JWT token obtain/refresh
    /admin/         → Django Admin
    /api-auth/      → DRF browsable API login/logout
"""

from django.contrib import admin
from django.urls import include, path
from django.views.generic import RedirectView
from rest_framework.routers import DefaultRouter
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView

from booking.views import BookingRequestViewSet

# ── DRF API Router ────────────────────────────────────────────────────────────
# Registers /api/bookings/ as the canonical REST endpoint for the booking module.
# Mobile/React clients should use these URLs.
api_router = DefaultRouter()
api_router.register(r"bookings", BookingRequestViewSet, basename="booking")

urlpatterns = [
    # ── Root → redirect to login ──────────────────────────────────────────────
    path("", RedirectView.as_view(url="/accounts/login/", permanent=False)),

    # ── Django Admin ──────────────────────────────────────────────────────────
    path("admin/", admin.site.urls),

    # ── Accounts (web UI: login, logout, dashboard) ───────────────────────────
    path("accounts/", include("accounts.urls", namespace="accounts")),

    # ── Booking web UI (HTMX templates) ──────────────────────────────────────
    path("booking/", include("booking.urls", namespace="booking")),

    # ── Booking REST API ──────────────────────────────────────────────────────
    path("api/", include(api_router.urls)),

    # ── Room Inventory Web UI & API ───────────────────────────────────────────
    path("inventory/", include("room_inventory.urls", namespace="inventory")),
    path("api/rooms/", include("room_inventory.urls", namespace="room_inventory")),

    # ── Housekeeping Web UI & API ─────────────────────────────────────────────
    path("housekeeping/", include("housekeeping.urls", namespace="housekeeping_ui")),
    path("api/housekeeping/", include("housekeeping.urls", namespace="housekeeping")),

    # ── JWT token endpoints ───────────────────────────────────────────────────
    path("api/token/", TokenObtainPairView.as_view(), name="token_obtain_pair"),
    path("api/token/refresh/", TokenRefreshView.as_view(), name="token_refresh"),

    # ── DRF browsable API auth ────────────────────────────────────────────────
    path("api-auth/", include("rest_framework.urls")),
]
