"""
housekeeping/views.py
----------------------
STUB API view implementing the integration contract for room status.

Contract (do not change response shape without updating README.md and
informing the booking module owner):

    GET /api/housekeeping/room-status/?room=<id>
        → {
            "room_id": 1,
            "status": "CLEAN",          # CLEAN | DIRTY | OUT_OF_SERVICE
            "last_updated": "2025-07-22T10:30:00Z",
            "_stub": true
          }

The real implementation (by the housekeeping module owner) should:
    - Track actual room cleaning cycles in the database
    - Return real timestamps and status based on room ID
"""

from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView


class RoomStatusView(APIView):
    """
    GET /api/housekeeping/room-status/?room=<id>

    STUB: Returns a hardcoded CLEAN status for any room ID.
    The allotment step in the booking workflow will call this
    before assigning a room to a guest.
    """

    permission_classes = [IsAuthenticated]

    STUB_STATUSES = {
        # Pre-seeded statuses for demo purposes
        # Format: room_id → status
        "1": "CLEAN",
        "2": "CLEAN",
        "3": "DIRTY",
        "4": "OUT_OF_SERVICE",
    }

    def get(self, request):
        room_id = request.query_params.get("room")

        if not room_id:
            return Response({"error": "room parameter is required."}, status=400)

        status_value = self.STUB_STATUSES.get(str(room_id), "CLEAN")

        return Response(
            {
                "room_id": room_id,
                "status": status_value,  # CLEAN | DIRTY | OUT_OF_SERVICE
                "last_updated": "2025-07-22T10:30:00Z",  # stub timestamp
                "_stub": True,
            }
        )
