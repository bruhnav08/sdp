"""
accounts/urls.py
-----------------
URL patterns for the accounts app.
Included in config/urls.py under the prefix /accounts/.

app_name = "accounts" ensures all names are scoped, e.g.:
    {% url "accounts:login" %}
    reverse("accounts:dashboard")
"""

from django.urls import path

from accounts import views

app_name = "accounts"

urlpatterns = [
    # ── Web (session-based) ───────────────────────────────────────────────────
    path("login/", views.LoginView.as_view(), name="login"),
    path("logout/", views.LogoutView.as_view(), name="logout"),
    path("dashboard/", views.DashboardRedirectView.as_view(), name="dashboard"),

    # ── API (JWT-based) ───────────────────────────────────────────────────────
    path("api/profile/", views.UserProfileAPIView.as_view(), name="api-profile"),
]
