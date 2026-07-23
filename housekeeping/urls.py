"""
housekeeping/urls.py
---------------------
Stub URL patterns for the housekeeping integration contract.
Included in config/urls.py under /api/housekeeping/.

app_name = "housekeeping"
"""

from django.urls import path

from housekeeping import views

app_name = "housekeeping"

urlpatterns = [
    path("room-status/", views.RoomStatusView.as_view(), name="room-status"),
]
