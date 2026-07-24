from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.models import User
from accounts.permissions import IsGuestHouseTeamOrAdmin, role_required
from housekeeping.models import RoomStatusHistory
from housekeeping.services import change_room_status, get_available_actions
from room_inventory.models import GuestHouse, Room, RoomCategory


# ── DRF REST API (Updated with real DB integration) ───────────────────────────

class RoomStatusView(APIView):
    """
    GET /api/housekeeping/room-status/?room=<id>
    Returns real room operational status and timestamp.
    """

    permission_classes = [IsAuthenticated, IsGuestHouseTeamOrAdmin]

    def get(self, request):
        room_id = request.query_params.get("room")
        if not room_id:
            return Response({"error": "room parameter is required."}, status=400)

        try:
            room = Room.objects.get(pk=room_id)
        except Room.DoesNotExist:
            return Response({"error": "Room not found."}, status=404)

        last_history = room.status_history.first()
        last_updated_ts = last_history.timestamp.isoformat() if last_history else room.updated_at.isoformat()

        return Response(
            {
                "room_id": room.id,
                "room_number": room.room_number,
                "guest_house": room.guest_house.name,
                "status": room.status,
                "status_display": room.get_status_display(),
                "last_updated": last_updated_ts,
            }
        )


# ── Web UI Views ──────────────────────────────────────────────────────────────

@login_required
@role_required(User.Role.GUEST_HOUSE_TEAM, User.Role.ADMIN)
def dashboard_view(request):
    """
    Enterprise Housekeeping & Room Status Dashboard.
    Provides stat cards, filter controls, live inventory table, and action triggers.
    """
    rooms = Room.objects.filter(is_active=True).select_related("guest_house", "room_category").prefetch_related("amenities", "status_history")

    gh_id = request.GET.get("guest_house")
    cat_id = request.GET.get("category")
    status = request.GET.get("status")
    search = request.GET.get("search")

    if gh_id:
        rooms = rooms.filter(guest_house_id=gh_id)
    if cat_id:
        rooms = rooms.filter(room_category_id=cat_id)
    if status:
        rooms = rooms.filter(status=status)
    if search:
        rooms = rooms.filter(Q(room_number__icontains=search) | Q(guest_house__name__icontains=search))

    # Compute overall stats across all active rooms (or filtered)
    all_rooms = Room.objects.filter(is_active=True)
    if gh_id:
        all_rooms = all_rooms.filter(guest_house_id=gh_id)

    total_rooms = all_rooms.count()
    vacant_clean_count = all_rooms.filter(status=Room.Status.VACANT_CLEAN).count()
    vacant_dirty_count = all_rooms.filter(status=Room.Status.VACANT_DIRTY).count()
    cleaning_progress_count = all_rooms.filter(status=Room.Status.CLEANING_IN_PROGRESS).count()
    occupied_count = all_rooms.filter(status=Room.Status.OCCUPIED).count()
    maintenance_count = all_rooms.filter(status=Room.Status.UNDER_MAINTENANCE).count()

    # Annotate actions for each room
    room_list = []
    for r in rooms:
        r.available_actions = get_available_actions(r)
        r.last_history = r.status_history.first()
        room_list.append(r)

    guest_houses = GuestHouse.objects.filter(is_active=True)
    categories = RoomCategory.objects.filter(is_active=True)

    context = {
        "rooms": room_list,
        "total_rooms": total_rooms,
        "vacant_clean_count": vacant_clean_count,
        "vacant_dirty_count": vacant_dirty_count,
        "cleaning_progress_count": cleaning_progress_count,
        "occupied_count": occupied_count,
        "maintenance_count": maintenance_count,
        "guest_houses": guest_houses,
        "categories": categories,
        "statuses": Room.Status.choices,
        "selected_gh": int(gh_id) if gh_id and gh_id.isdigit() else None,
        "selected_cat": int(cat_id) if cat_id and cat_id.isdigit() else None,
        "selected_status": status,
        "search_query": search or "",
    }

    return render(request, "housekeeping/dashboard.html", context)


@login_required
@role_required(User.Role.GUEST_HOUSE_TEAM, User.Role.ADMIN)
def change_room_status_view(request, pk):
    """
    Handles status transition POST request (supports HTMX partial response).
    """
    room = get_object_or_404(Room, pk=pk)
    if request.method == "POST":
        new_status = request.POST.get("new_status")
        remarks = request.POST.get("remarks", "")

        try:
            change_room_status(room, new_status, request.user, remarks=remarks)
            messages.success(request, f"Room {room.room_number} status changed to '{dict(Room.Status.choices).get(new_status, new_status)}'.")
        except ValidationError as e:
            messages.error(request, str(e.message if hasattr(e, 'message') else e))

        # Check if HTMX request
        if request.headers.get("HX-Request"):
            room.refresh_from_db()
            room.available_actions = get_available_actions(room)
            room.last_history = room.status_history.first()
            return render(request, "housekeeping/_room_row.html", {"room": room})

        return redirect("housekeeping:dashboard")

    return redirect("housekeeping:dashboard")


@login_required
@role_required(User.Role.GUEST_HOUSE_TEAM, User.Role.ADMIN)
def room_history_view(request, pk):
    """
    Room-specific audit log history view.
    """
    room = get_object_or_404(Room, pk=pk)
    history_entries = room.status_history.all().select_related("changed_by")

    context = {
        "room": room,
        "history_entries": history_entries,
    }

    if request.headers.get("HX-Request"):
        return render(request, "housekeeping/_room_history_modal.html", context)

    return render(request, "housekeeping/room_history.html", context)

