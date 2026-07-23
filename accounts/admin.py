"""
accounts/admin.py
------------------
Register the custom User model in Django Admin with a sensible display.
"""

from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin

from accounts.models import User


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    """Extended UserAdmin that surfaces HSRS-specific fields."""

    # Columns shown in the list view
    list_display = (
        "username",
        "email",
        "first_name",
        "last_name",
        "role",
        "department",
        "campus",
        "is_active",
        "is_staff",
        "date_joined",
    )
    list_filter = ("role", "is_active", "is_staff", "campus", "department")
    search_fields = ("username", "email", "first_name", "last_name", "mobile_number")
    ordering = ("-date_joined",)

    # Extra fields displayed on the User detail/edit page
    fieldsets = BaseUserAdmin.fieldsets + (  # type: ignore[operator]
        (
            "HSRS Profile",
            {
                "fields": ("role", "department", "campus", "mobile_number"),
            },
        ),
    )

    # Fields shown when creating a new user from Admin
    add_fieldsets = BaseUserAdmin.add_fieldsets + (  # type: ignore[operator]
        (
            "HSRS Profile",
            {
                "classes": ("wide",),
                "fields": ("role", "department", "campus", "mobile_number"),
            },
        ),
    )
