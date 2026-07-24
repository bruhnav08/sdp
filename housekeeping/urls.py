from django.urls import path
from housekeeping import views

app_name = "housekeeping"

urlpatterns = [
    # ── Web UI ────────────────────────────────────────────────────────────────
    path("dashboard/", views.dashboard_view, name="dashboard"),
    path("rooms/<int:pk>/change-status/", views.change_room_status_view, name="change-status"),
    path("rooms/<int:pk>/history/", views.room_history_view, name="room-history"),

    # ── REST API ──────────────────────────────────────────────────────────────
    path("room-status/", views.RoomStatusView.as_view(), name="room-status"),
]
