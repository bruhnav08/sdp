"""
room_inventory/serializers.py
------------------------------
STUB serializers for the room_inventory app.
"""

from rest_framework import serializers

from room_inventory.models import Campus, Event, GuestHouse


class CampusSerializer(serializers.ModelSerializer):
    class Meta:
        model = Campus
        fields = ["id", "name", "location"]


class GuestHouseSerializer(serializers.ModelSerializer):
    campus_name = serializers.CharField(source="campus.name", read_only=True)

    class Meta:
        model = GuestHouse
        fields = ["id", "name", "campus", "campus_name", "total_rooms", "contact_number"]


class EventSerializer(serializers.ModelSerializer):
    campus_name = serializers.CharField(source="campus.name", read_only=True)

    class Meta:
        model = Event
        fields = ["id", "name", "event_date", "campus", "campus_name", "description"]
