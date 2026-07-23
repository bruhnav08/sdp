"""
accounts/serializers.py
------------------------
DRF serializers for the accounts app.
"""

from django.contrib.auth import get_user_model
from rest_framework import serializers

User = get_user_model()


class UserProfileSerializer(serializers.ModelSerializer):
    """
    Read / update the logged-in user's own profile.
    Password changes are excluded here — use Django's built-in change-password
    view or add a dedicated endpoint.
    """

    full_name = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = [
            "id",
            "username",
            "email",
            "first_name",
            "last_name",
            "full_name",
            "role",
            "department",
            "campus",
            "mobile_number",
            "date_joined",
        ]
        read_only_fields = ["id", "username", "role", "date_joined"]

    def get_full_name(self, obj) -> str:
        return obj.get_full_name() or obj.username


class UserMinimalSerializer(serializers.ModelSerializer):
    """
    Lightweight serializer used when another module embeds user info
    (e.g. BookingRequest.requestor) without exposing sensitive fields.
    """

    full_name = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = ["id", "full_name", "email", "department", "campus", "mobile_number"]

    def get_full_name(self, obj) -> str:
        return obj.get_full_name() or obj.username
