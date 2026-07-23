"""
room_inventory/views.py
------------------------
STUB API views implementing the integration contract for the booking module.

Contract (do not change response shape without updating README.md and
informing the booking module owner):

    GET /api/rooms/campuses/
        → [{"id": 1, "name": "Main Campus", "location": "North Zone"}, ...]

    GET /api/rooms/guest-houses/?campus=<id>
        → [{"id": 1, "name": "Faculty Guest House", "campus": 1,
            "campus_name": "Main Campus", "total_rooms": 20, ...}, ...]

    GET /api/rooms/availability/?guest_house=<id>&check_in=YYYY-MM-DD&check_out=YYYY-MM-DD
        → {"guest_house_id": 1, "available_rooms": 8,
           "configurations": ["Single", "Double", "Suite"]}

    GET /api/rooms/events/?campus=<id>
        → [{"id": 1, "name": "...", "event_date": "2025-03-15", ...}, ...]
"""

from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from room_inventory.models import Campus, Event, GuestHouse
from room_inventory.serializers import CampusSerializer, EventSerializer, GuestHouseSerializer


class CampusListView(APIView):
    """GET /api/rooms/campuses/ — list all active campuses."""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        campuses = Campus.objects.filter(is_active=True)
        return Response(CampusSerializer(campuses, many=True).data)


class GuestHouseListView(APIView):
    """
    GET /api/rooms/guest-houses/?campus=<id>
    List guest houses filtered by campus.  If campus is omitted, returns all.
    """

    permission_classes = [IsAuthenticated]

    def get(self, request):
        campus_id = request.query_params.get("campus")
        qs = GuestHouse.objects.filter(is_active=True).select_related("campus")
        if campus_id:
            qs = qs.filter(campus_id=campus_id)
        return Response(GuestHouseSerializer(qs, many=True).data)


class RoomAvailabilityView(APIView):
    """
    GET /api/rooms/availability/?guest_house=<id>&check_in=YYYY-MM-DD&check_out=YYYY-MM-DD

    STUB: Always returns the guest house's total_rooms as available.
    The real implementation (by the room_inventory module owner) should
    subtract confirmed bookings for the given date range.
    """

    permission_classes = [IsAuthenticated]

    def get(self, request):
        guest_house_id = request.query_params.get("guest_house")
        check_in = request.query_params.get("check_in")
        check_out = request.query_params.get("check_out")

        if not guest_house_id:
            return Response({"error": "guest_house parameter is required."}, status=400)

        try:
            gh = GuestHouse.objects.get(pk=guest_house_id, is_active=True)
        except GuestHouse.DoesNotExist:
            return Response({"error": "Guest house not found."}, status=404)

        # STUB: return total capacity, ignore date range for now
        return Response(
            {
                "guest_house_id": gh.id,
                "guest_house_name": gh.name,
                "available_rooms": gh.total_rooms,  # TODO: subtract existing bookings
                "configurations": ["Single", "Double", "Twin", "Suite"],
                "check_in": check_in,
                "check_out": check_out,
                "_stub": True,  # flag so callers know this is not real availability
            }
        )


class EventListView(APIView):
    """
    GET /api/rooms/events/?campus=<id>
    List active events, optionally filtered by campus.
    """

    permission_classes = [IsAuthenticated]

    def get(self, request):
        campus_id = request.query_params.get("campus")
        qs = Event.objects.filter(is_active=True).select_related("campus")
        if campus_id:
            qs = qs.filter(campus_id=campus_id)
        return Response(EventSerializer(qs, many=True).data)
