"""
accounts/models.py
------------------
Custom User model extending Django's AbstractUser.

This is the AUTH_USER_MODEL for the entire HSRS project.
Any app that needs to reference the user model should use:

    from django.conf import settings
    settings.AUTH_USER_MODEL           # for ForeignKey / model references
    get_user_model()                   # for runtime model access

NEVER import User directly from this module in other apps — that creates
a hard dependency on the accounts app's internals.
"""

from django.contrib.auth.models import AbstractUser
from django.db import models


class User(AbstractUser):
    """
    Project-wide User model.

    Extends AbstractUser with:
    - role: determines what the user can do and where they are redirected
    - department: user's academic/admin department
    - campus: which campus the user belongs to
    - mobile_number: primary contact number
    """

    class Role(models.TextChoices):
        REQUESTOR = "REQUESTOR", "Requestor"
        FACULTY_INCHARGE = "FACULTY_INCHARGE", "Faculty In-Charge"
        HOD_DIRECTOR = "HOD_DIRECTOR", "HOD / Director"
        GUEST_HOUSE_TEAM = "GUEST_HOUSE_TEAM", "Guest House Team"
        MANAGEMENT = "MANAGEMENT", "Management"
        ADMIN = "ADMIN", "Admin"

    role = models.CharField(
        max_length=20,
        choices=Role.choices,
        default=Role.REQUESTOR,
        db_index=True,
    )
    department = models.CharField(max_length=150, blank=True)
    campus = models.CharField(max_length=150, blank=True)
    mobile_number = models.CharField(max_length=15, blank=True)

    class Meta:
        verbose_name = "User"
        verbose_name_plural = "Users"

    def __str__(self) -> str:
        full_name = self.get_full_name()
        return f"{full_name or self.username} ({self.get_role_display()})"

    # ── Convenience role-check properties ─────────────────────────────────────
    # These are read by accounts/permissions.py and can be used in templates
    # via {{ request.user.is_requestor }} etc.

    @property
    def is_requestor(self) -> bool:
        return self.role == self.Role.REQUESTOR

    @property
    def is_approver(self) -> bool:
        """True for HOD, Director, or Faculty In-Charge."""
        return self.role in (self.Role.HOD_DIRECTOR, self.Role.FACULTY_INCHARGE)

    @property
    def is_guest_house_team(self) -> bool:
        return self.role == self.Role.GUEST_HOUSE_TEAM

    @property
    def is_management(self) -> bool:
        return self.role == self.Role.MANAGEMENT

    @property
    def is_admin_user(self) -> bool:
        return self.role == self.Role.ADMIN

    def get_dashboard_url(self) -> str:
        """
        Return the URL the user should be redirected to after login.
        Used by accounts/views.py DashboardRedirectView.
        """
        role_url_map = {
            self.Role.REQUESTOR: "/booking/my-bookings/",
            self.Role.FACULTY_INCHARGE: "/booking/my-bookings/",
            self.Role.HOD_DIRECTOR: "/booking/approvals/",
            self.Role.GUEST_HOUSE_TEAM: "/booking/allotment/",
            self.Role.MANAGEMENT: "/booking/approvals/management/",
            self.Role.ADMIN: "/admin/",
        }
        return role_url_map.get(self.role, "/booking/my-bookings/")
