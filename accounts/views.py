"""
accounts/views.py
------------------
Web (session-based) and API (JWT) views for authentication.

Web flow:  LoginView → DashboardRedirectView → role-specific URL
API flow:  POST /api/token/ (simplejwt) → Bearer token in Authorization header
"""

from django.contrib import messages
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import redirect, render
from django.utils.decorators import method_decorator
from django.views import View
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.serializers import UserProfileSerializer


# ── Web Views (session auth) ──────────────────────────────────────────────────

class LoginView(View):
    """
    Renders and processes the HTML login form.
    On success, redirects to DashboardRedirectView which routes by role.
    """

    template_name = "accounts/login.html"

    def get(self, request):
        if request.user.is_authenticated:
            return redirect("accounts:dashboard")
        return render(request, self.template_name)

    def post(self, request):
        username = request.POST.get("username", "").strip()
        password = request.POST.get("password", "")

        if not username or not password:
            messages.error(request, "Please enter both username and password.")
            return render(request, self.template_name, {"username": username})

        user = authenticate(request, username=username, password=password)

        if user is None:
            messages.error(request, "Invalid username or password.")
            return render(request, self.template_name, {"username": username})

        if not user.is_active:
            messages.error(request, "Your account has been deactivated. Contact the admin.")
            return render(request, self.template_name, {"username": username})

        login(request, user)
        # 'next' param support (standard Django redirect-after-login)
        next_url = request.GET.get("next") or request.POST.get("next")
        return redirect(next_url) if next_url else redirect("accounts:dashboard")


class LogoutView(View):
    """Logs the user out and redirects to login."""

    def post(self, request):
        logout(request)
        messages.success(request, "You have been logged out successfully.")
        return redirect("accounts:login")

    # Also support GET for simplicity (clicking a link)
    def get(self, request):
        logout(request)
        return redirect("accounts:login")


class DashboardRedirectView(LoginRequiredMixin, View):
    """
    Redirects the logged-in user to the appropriate module dashboard
    based on their role.  Does not render a template of its own.
    """

    def get(self, request):
        url = request.user.get_dashboard_url()
        return redirect(url)


# ── API Views (JWT auth) ──────────────────────────────────────────────────────

class UserProfileAPIView(APIView):
    """
    GET  /accounts/api/profile/  → return the logged-in user's profile
    PATCH /accounts/api/profile/ → update allowed fields
    """

    permission_classes = [IsAuthenticated]

    def get(self, request):
        serializer = UserProfileSerializer(request.user)
        return Response(serializer.data)

    def patch(self, request):
        serializer = UserProfileSerializer(
            request.user, data=request.data, partial=True
        )
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
