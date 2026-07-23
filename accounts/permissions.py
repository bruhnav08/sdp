"""
accounts/permissions.py
------------------------
Reusable DRF permission classes for every module in the HSRS project.

Teammates building room_inventory and housekeeping can import from here:

    from accounts.permissions import IsGuestHouseTeam, IsApprover

All classes follow a consistent pattern:
    - Check request.user.is_authenticated first
    - Check request.user.role against the allowed roles
    - Return a clear .message on denial

Object-level permission methods are also provided for views that need
to check ownership (e.g. a requestor can only edit THEIR OWN booking).
"""

from rest_framework.permissions import BasePermission

from accounts.models import User


class IsRequestor(BasePermission):
    """
    Allows access only to users with REQUESTOR role.
    Use on booking creation/edit endpoints.
    """

    message = "You must be a Requestor to perform this action."

    def has_permission(self, request, view):
        return bool(
            request.user
            and request.user.is_authenticated
            and request.user.role == User.Role.REQUESTOR
        )


class IsApprover(BasePermission):
    """
    Allows access to HOD / Director or Faculty In-Charge.
    Use on approval workflow endpoints.
    """

    message = "You must be an approver (HOD, Director, or Faculty In-Charge) to perform this action."

    def has_permission(self, request, view):
        return bool(
            request.user
            and request.user.is_authenticated
            and request.user.role in (User.Role.HOD_DIRECTOR, User.Role.FACULTY_INCHARGE)
        )


class IsGuestHouseTeam(BasePermission):
    """
    Allows access only to Guest House Team members.
    Use on allotment / room status endpoints.
    """

    message = "You must be a member of the Guest House Team to perform this action."

    def has_permission(self, request, view):
        return bool(
            request.user
            and request.user.is_authenticated
            and request.user.role == User.Role.GUEST_HOUSE_TEAM
        )


class IsManagement(BasePermission):
    """
    Allows access only to Management users.
    Use on final approval / reporting endpoints.
    """

    message = "You must be a Management user to perform this action."

    def has_permission(self, request, view):
        return bool(
            request.user
            and request.user.is_authenticated
            and request.user.role == User.Role.MANAGEMENT
        )


class IsAdminUser(BasePermission):
    """
    Allows access only to ADMIN role users (separate from Django's is_staff).
    """

    message = "You must be an Admin to perform this action."

    def has_permission(self, request, view):
        return bool(
            request.user
            and request.user.is_authenticated
            and request.user.role == User.Role.ADMIN
        )


class IsRequestorOrStaff(BasePermission):
    """
    Read access for authenticated users; write access only for REQUESTOR
    or staff/admin roles.  Useful for mixed-audience list views.
    """

    message = "Write access requires Requestor role."

    def has_permission(self, request, view):
        if not (request.user and request.user.is_authenticated):
            return False
        if request.method in ("GET", "HEAD", "OPTIONS"):
            return True
        return request.user.role in (
            User.Role.REQUESTOR,
            User.Role.ADMIN,
        ) or request.user.is_staff


class IsOwnerOrStaff(BasePermission):
    """
    Object-level permission: allow access only if the requesting user owns
    the object (obj.requestor == request.user) or is staff / admin.

    Must be used with get_object() in DRF views; set
    self.check_object_permissions(self.request, obj) explicitly.
    """

    message = "You do not have permission to access this object."

    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated)

    def has_object_permission(self, request, view, obj):
        # Staff and admins can see everything
        if request.user.is_staff or request.user.role == User.Role.ADMIN:
            return True
        # Object must have a `requestor` attribute
        owner = getattr(obj, "requestor", None)
        return owner == request.user
