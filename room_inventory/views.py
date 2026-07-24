from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Count, Q
from django.shortcuts import get_object_or_404, redirect, render
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.models import User
from accounts.permissions import role_required
from room_inventory.forms import AmenityForm, GuestHouseForm, RoomCategoryForm, RoomForm
from room_inventory.models import Amenity, Campus, Event, GuestHouse, Room, RoomCategory
from room_inventory.serializers import CampusSerializer, EventSerializer, GuestHouseSerializer


def ensure_default_amenities():
    """Ensure standard amenities exist in database without emoji icons."""
    defaults = [
        ("Wi-Fi", ""),
        ("AC", ""),
        ("Attached Bathroom", ""),
        ("TV", ""),
    ]
    for name, icon in defaults:
        amenity, created = Amenity.objects.get_or_create(name=name, defaults={"icon": icon, "is_active": True})
        if not created and amenity.icon in ("📶", "❄️", "🚿", "📺"):
            amenity.icon = ""
            amenity.save()



# ── DRF API Views (Contract preserved & updated) ─────────────────────────────

class CampusListView(APIView):
    """GET /api/rooms/campuses/ — list all active campuses."""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        campuses = Campus.objects.filter(is_active=True)
        return Response(CampusSerializer(campuses, many=True).data)


class GuestHouseListView(APIView):
    """
    GET /api/rooms/guest-houses/?campus=<id>
    List guest houses filtered by campus. If campus is omitted, returns all.
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
    Calculates actual room availability excluding rooms marked as UNDER_MAINTENANCE or BLOCKED.
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

        total_defined_rooms = gh.rooms.filter(is_active=True).count()
        if total_defined_rooms > 0:
            available_rooms = gh.rooms.filter(is_active=True, status=Room.Status.VACANT_CLEAN).count()
            under_maintenance_rooms = gh.rooms.filter(is_active=True, status=Room.Status.UNDER_MAINTENANCE).count()
            blocked_rooms = gh.rooms.filter(is_active=True, status=Room.Status.BLOCKED).count()
        else:
            available_rooms = gh.total_rooms
            under_maintenance_rooms = 0
            blocked_rooms = 0

        categories = list(RoomCategory.objects.filter(
            Q(guest_house=gh) | Q(guest_house__isnull=True), is_active=True
        ).values_list("name", flat=True).distinct())

        if not categories:
            categories = ["Single", "Double King", "Double Queen", "Double Twin"]

        return Response(
            {
                "guest_house_id": gh.id,
                "guest_house_name": gh.name,
                "available_rooms": available_rooms,
                "under_maintenance_rooms": under_maintenance_rooms,
                "blocked_rooms": blocked_rooms,
                "configurations": categories,
                "check_in": check_in,
                "check_out": check_out,
            }
        )


class EventListView(APIView):
    """GET /api/rooms/events/?campus=<id>"""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        campus_id = request.query_params.get("campus")
        qs = Event.objects.filter(is_active=True).select_related("campus")
        if campus_id:
            qs = qs.filter(campus_id=campus_id)
        return Response(EventSerializer(qs, many=True).data)


# ── Web Management Views (HTML UI for Module 1) ───────────────────────────────

@login_required
@role_required(User.Role.ADMIN, User.Role.GUEST_HOUSE_TEAM)
def guesthouse_list(request):
    """View all guest houses with quick stats and room drill-down."""
    ensure_default_amenities()
    guest_houses = GuestHouse.objects.all().select_related("campus").annotate(
        room_count=Count("rooms", filter=Q(rooms__is_active=True)),
        available_count=Count("rooms", filter=Q(rooms__is_active=True, rooms__status=Room.Status.VACANT_CLEAN)),
        maintenance_count=Count("rooms", filter=Q(rooms__is_active=True, rooms__status=Room.Status.UNDER_MAINTENANCE)),
        blocked_count=Count("rooms", filter=Q(rooms__is_active=True, rooms__status=Room.Status.BLOCKED)),
        category_count=Count("categories", filter=Q(categories__is_active=True)),
    )

    example_houses = ["KE Hall", "DVK Guest House", "Jonas Hall", "Auditorium Block", "Sports Complex"]
    existing_names = set(gh.name for gh in guest_houses)
    quick_add_examples = [name for name in example_houses if name not in existing_names]

    return render(
        request,
        "room_inventory/guesthouse_list.html",
        {
            "guest_houses": guest_houses,
            "quick_add_examples": quick_add_examples,
        },
    )


@login_required
@role_required(User.Role.ADMIN)
def guesthouse_create(request):
    """Add a new guest house (supports quick-add via GET query param)."""
    quick_name = request.GET.get("quick_add")
    initial_data = {}
    if quick_name:
        initial_data["name"] = quick_name

    if request.method == "POST":
        form = GuestHouseForm(request.POST)
        if form.is_valid():
            gh = form.save()
            messages.success(request, f"Guest house '{gh.name}' created successfully!")
            return redirect("room_inventory:guesthouse-list")
    else:
        form = GuestHouseForm(initial=initial_data)

    return render(request, "room_inventory/guesthouse_form.html", {"form": form, "title": "Add Guest House"})


@login_required
@role_required(User.Role.ADMIN)
def guesthouse_edit(request, pk):
    """Edit an existing guest house."""
    gh = get_object_or_404(GuestHouse, pk=pk)
    if request.method == "POST":
        form = GuestHouseForm(request.POST, instance=gh)
        if form.is_valid():
            form.save()
            messages.success(request, f"Guest house '{gh.name}' updated successfully!")
            return redirect("room_inventory:guesthouse-list")
    else:
        form = GuestHouseForm(instance=gh)

    return render(request, "room_inventory/guesthouse_form.html", {"form": form, "title": f"Edit Guest House — {gh.name}", "guesthouse": gh})


@login_required
@role_required(User.Role.ADMIN)
def guesthouse_delete(request, pk):
    """Delete a guest house."""
    gh = get_object_or_404(GuestHouse, pk=pk)
    if request.method == "POST":
        name = gh.name
        gh.delete()
        messages.success(request, f"Guest house '{name}' deleted.")
        return redirect("room_inventory:guesthouse-list")

    return render(request, "room_inventory/guesthouse_confirm_delete.html", {"guesthouse": gh})


@login_required
@role_required(User.Role.ADMIN, User.Role.GUEST_HOUSE_TEAM)
def guesthouse_rooms(request, pk):

    """View all rooms belonging to a specific guest house."""
    gh = get_object_or_404(GuestHouse, pk=pk)
    rooms = gh.rooms.all().select_related("room_category").prefetch_related("amenities")
    return render(request, "room_inventory/guesthouse_rooms.html", {"guesthouse": gh, "rooms": rooms})


# ── Room Category Views ───────────────────────────────────────────────────────

@login_required
@role_required(User.Role.ADMIN, User.Role.GUEST_HOUSE_TEAM)
def category_list(request):
    """View all room categories, optionally filtered by Guest House."""
    gh_id = request.GET.get("guest_house")
    categories = RoomCategory.objects.all().select_related("guest_house")
    if gh_id:
        categories = categories.filter(guest_house_id=gh_id)

    guest_houses = GuestHouse.objects.filter(is_active=True)
    return render(
        request,
        "room_inventory/category_list.html",
        {
            "categories": categories,
            "guest_houses": guest_houses,
            "selected_gh_id": int(gh_id) if gh_id and gh_id.isdigit() else None,
        },
    )


@login_required
@role_required(User.Role.ADMIN)
def category_create(request):
    """Create a room category and associate it with a guest house."""
    initial_gh = request.GET.get("guest_house")
    initial_data = {}
    if initial_gh:
        initial_data["guest_house"] = initial_gh

    if request.method == "POST":
        form = RoomCategoryForm(request.POST)
        if form.is_valid():
            cat = form.save()
            messages.success(request, f"Room category '{cat.name}' created successfully!")
            return redirect("room_inventory:category-list")
    else:
        form = RoomCategoryForm(initial=initial_data)

    return render(request, "room_inventory/category_form.html", {"form": form, "title": "Create Room Category"})


@login_required
@role_required(User.Role.ADMIN)
def category_edit(request, pk):
    """Edit room category."""
    cat = get_object_or_404(RoomCategory, pk=pk)
    if request.method == "POST":
        form = RoomCategoryForm(request.POST, instance=cat)
        if form.is_valid():
            form.save()
            messages.success(request, f"Room category '{cat.name}' updated successfully!")
            return redirect("room_inventory:category-list")
    else:
        form = RoomCategoryForm(instance=cat)

    return render(request, "room_inventory/category_form.html", {"form": form, "title": f"Edit Room Category — {cat.name}", "category": cat})


@login_required
@role_required(User.Role.ADMIN)
def category_delete(request, pk):
    """Delete room category."""
    cat = get_object_or_404(RoomCategory, pk=pk)
    if request.method == "POST":
        name = cat.name
        cat.delete()
        messages.success(request, f"Room category '{name}' deleted.")
        return redirect("room_inventory:category-list")

    return render(request, "room_inventory/category_confirm_delete.html", {"category": cat})


# ── Room Views ────────────────────────────────────────────────────────────────

@login_required
@role_required(User.Role.ADMIN, User.Role.GUEST_HOUSE_TEAM)
def room_list(request):
    """List all rooms with filtering by Guest House, Category, Status, Amenity."""
    ensure_default_amenities()
    rooms = Room.objects.all().select_related("guest_house", "room_category").prefetch_related("amenities")

    gh_id = request.GET.get("guest_house")
    cat_id = request.GET.get("category")
    status = request.GET.get("status")
    amenity_id = request.GET.get("amenity")
    search = request.GET.get("search")

    if gh_id:
        rooms = rooms.filter(guest_house_id=gh_id)
    if cat_id:
        rooms = rooms.filter(room_category_id=cat_id)
    if status:
        rooms = rooms.filter(status=status)
    if amenity_id:
        rooms = rooms.filter(amenities__id=amenity_id)
    if search:
        rooms = rooms.filter(Q(room_number__icontains=search) | Q(guest_house__name__icontains=search))

    guest_houses = GuestHouse.objects.filter(is_active=True)
    categories = RoomCategory.objects.filter(is_active=True)
    amenities = Amenity.objects.filter(is_active=True)

    return render(
        request,
        "room_inventory/room_list.html",
        {
            "rooms": rooms,
            "guest_houses": guest_houses,
            "categories": categories,
            "amenities": amenities,
            "statuses": Room.Status.choices,
            "selected_gh": int(gh_id) if gh_id and gh_id.isdigit() else None,
            "selected_cat": int(cat_id) if cat_id and cat_id.isdigit() else None,
            "selected_status": status,
            "selected_amenity": int(amenity_id) if amenity_id and amenity_id.isdigit() else None,
            "search_query": search or "",
        },
    )


@login_required
@role_required(User.Role.ADMIN)
def room_create(request):
    """Create a new room."""
    ensure_default_amenities()
    initial_gh = request.GET.get("guest_house")
    initial_data = {}
    if initial_gh:
        initial_data["guest_house"] = initial_gh

    if request.method == "POST":
        form = RoomForm(request.POST)
        if form.is_valid():
            room = form.save()
            room.guest_house.update_total_rooms_count()
            messages.success(request, f"Room {room.room_number} ({room.guest_house.name}) created successfully!")
            return redirect("room_inventory:room-list")
    else:
        form = RoomForm(initial=initial_data)

    return render(request, "room_inventory/room_form.html", {"form": form, "title": "Create Room"})


@login_required
@role_required(User.Role.ADMIN)
def room_edit(request, pk):
    """Edit an existing room."""
    ensure_default_amenities()
    room = get_object_or_404(Room, pk=pk)
    if request.method == "POST":
        form = RoomForm(request.POST, instance=room)
        if form.is_valid():
            room = form.save()
            room.guest_house.update_total_rooms_count()
            messages.success(request, f"Room {room.room_number} updated successfully!")
            return redirect("room_inventory:room-list")
    else:
        form = RoomForm(instance=room)

    return render(request, "room_inventory/room_form.html", {"form": form, "title": f"Edit Room {room.room_number}", "room": room})


@login_required
@role_required(User.Role.ADMIN)
def room_delete(request, pk):
    """Delete a room."""
    room = get_object_or_404(Room, pk=pk)
    gh = room.guest_house
    if request.method == "POST":
        number = room.room_number
        room.delete()
        gh.update_total_rooms_count()
        messages.success(request, f"Room {number} deleted.")
        return redirect("room_inventory:room-list")

    return render(request, "room_inventory/room_confirm_delete.html", {"room": room})


# ── Amenity Views ─────────────────────────────────────────────────────────────

@login_required
@role_required(User.Role.ADMIN)
def amenity_list_create(request):
    """View and create amenities dynamically."""
    ensure_default_amenities()
    amenities = Amenity.objects.all()
    if request.method == "POST":
        form = AmenityForm(request.POST)
        if form.is_valid():
            amenity = form.save()
            messages.success(request, f"Amenity '{amenity.name}' added successfully!")
            return redirect("room_inventory:amenity-list")
    else:
        form = AmenityForm()

    return render(request, "room_inventory/amenity_list.html", {"amenities": amenities, "form": form})

