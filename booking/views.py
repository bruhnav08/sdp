"""
booking/views.py
-----------------
Views for the booking module.  Two layers:

1. DRF API (BookingRequestViewSet)
   Endpoints:
       GET    /api/bookings/               → list requestor's bookings
       POST   /api/bookings/               → create DRAFT booking
       GET    /api/bookings/<id>/          → retrieve booking detail
       PATCH  /api/bookings/<id>/          → update DRAFT booking
       DELETE /api/bookings/<id>/          → delete DRAFT booking
       POST   /api/bookings/<id>/submit/   → DRAFT → PENDING_HOD_APPROVAL
       POST   /api/bookings/<id>/cancel/   → DRAFT/PENDING_HOD → CANCELLED

2. HTMX/Template views (web UI)
   URLs:
       GET/POST /booking/new/              → multi-section application form
       GET      /booking/my-bookings/      → list of requestor's bookings
       GET      /booking/<id>/             → booking detail
       GET      /booking/htmx/guest-houses/ → partial: guest house options
       GET      /booking/htmx/event-date/  → partial: event date auto-fill
       GET      /booking/approvals/        → stub page for HOD/Management
       GET      /booking/allotment/        → stub page for Guest House Team
"""

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.decorators import method_decorator
from django.views import View
from django.views.generic import DetailView, ListView
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from accounts.permissions import IsOwnerOrStaff
from booking.models import BookingRequest
from booking.serializers import BookingRequestListSerializer, BookingRequestSerializer
from booking.tasks import send_booking_confirmation_email
from common.api_response import error_response, success_response


# ── DRF API ViewSet ───────────────────────────────────────────────────────────

class BookingRequestViewSet(viewsets.ModelViewSet):
    """
    Full CRUD + submit/cancel actions for BookingRequest.

    Access rules:
    - Requestors see only their own bookings (enforced in get_queryset)
    - HOD/Director/Management/GuestHouseTeam/Admin see all bookings
    - Object-level: requestor can edit/cancel only their own DRAFT bookings
    """

    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        base_qs = (
            BookingRequest.objects.select_related("requestor")
            .prefetch_related("guests", "alternate_contacts")
        )
        # Requestors see only their own bookings
        if user.role == "REQUESTOR":
            return base_qs.filter(requestor=user)
        # All other roles see everything (approval/allotment views)
        return base_qs

    def get_serializer_class(self):
        if self.action == "list":
            return BookingRequestListSerializer
        return BookingRequestSerializer

    def get_serializer_context(self):
        ctx = super().get_serializer_context()
        ctx["request"] = self.request
        return ctx

    def destroy(self, request, *args, **kwargs):
        booking = self.get_object()
        if booking.status != BookingRequest.Status.DRAFT:
            return error_response(
                message="Only DRAFT bookings can be deleted.",
                status_code=status.HTTP_400_BAD_REQUEST,
            )
        return super().destroy(request, *args, **kwargs)

    @action(detail=True, methods=["post"], url_path="submit")
    def submit(self, request, pk=None):
        """
        POST /api/bookings/<id>/submit/
        Transitions the booking from DRAFT → PENDING_HOD_APPROVAL.
        Fires a confirmation email task.
        """
        booking = self.get_object()
        try:
            booking.submit(request.user)
        except (ValueError, PermissionError) as exc:
            return error_response(message=str(exc))

        # Fire confirmation email (synchronous in dev, async in prod)
        send_booking_confirmation_email.delay(booking.pk)

        serializer = BookingRequestSerializer(booking, context={"request": request})
        return success_response(
            data=serializer.data,
            message=f"Booking {booking.booking_id} submitted successfully.",
            status_code=status.HTTP_200_OK,
        )

    @action(detail=True, methods=["post"], url_path="cancel")
    def cancel(self, request, pk=None):
        """
        POST /api/bookings/<id>/cancel/
        Cancels a DRAFT or PENDING_HOD_APPROVAL booking.
        """
        booking = self.get_object()
        try:
            booking.cancel(request.user)
        except (ValueError, PermissionError) as exc:
            return error_response(message=str(exc))

        return success_response(message=f"Booking {booking.booking_id} has been cancelled.")


# ── HTMX Partial Views ────────────────────────────────────────────────────────

@login_required
def htmx_guest_houses(request):
    """
    GET /booking/htmx/guest-houses/?campus=<id>
    Returns an HTML <option> list for the guest house dropdown.
    Called by HTMX when the campus selection changes.
    """
    from room_inventory.models import GuestHouse

    campus_id = request.GET.get("campus")
    guest_houses = []
    if campus_id:
        guest_houses = GuestHouse.objects.filter(campus_id=campus_id, is_active=True)
    return render(
        request,
        "booking/partials/guest_house_options.html",
        {"guest_houses": guest_houses},
    )


@login_required
def htmx_event_date(request):
    """
    GET /booking/htmx/event-date/?event=<id>
    Returns a tiny partial with the event date so the form auto-fills it.
    """
    from room_inventory.models import Event

    event_id = request.GET.get("event")
    event = None
    if event_id:
        try:
            event = Event.objects.get(pk=event_id, is_active=True)
        except Event.DoesNotExist:
            pass
    return render(
        request,
        "booking/partials/event_date.html",
        {"event": event},
    )


@login_required
def htmx_events_for_campus(request):
    """
    GET /booking/htmx/events/?campus=<id>
    Returns <option> list of events for the selected campus.
    """
    from room_inventory.models import Event

    campus_id = request.GET.get("campus")
    events = []
    if campus_id:
        events = Event.objects.filter(campus_id=campus_id, is_active=True)
    return render(
        request,
        "booking/partials/event_options.html",
        {"events": events},
    )


# ── Template Views (web UI) ───────────────────────────────────────────────────

class BookingFormView(LoginRequiredMixin, View):
    """
    GET  /booking/new/   → render blank application form
    POST /booking/new/   → save DRAFT booking, redirect to my-bookings

    The form uses HTMX for chained dropdowns (campus→guest houses, campus→events)
    and Alpine.js for conditional field visibility and repeating sections.
    """

    template_name = "booking/form.html"

    def _get_context(self):
        from room_inventory.models import Campus, Event

        return {
            "campuses": Campus.objects.filter(is_active=True),
            "events": Event.objects.filter(is_active=True),
            "arrangement_choices": BookingRequest.ArrangementChoice.choices,
            "payment_choices": BookingRequest.PaymentChoice.choices,
            "event_type_choices": [
                "Academic", "Administrative", "Cultural", "Sports",
                "Research", "Alumni", "Board Meeting", "Other"
            ],
            "room_config_choices": ["Single", "Double", "Twin", "Suite", "Dormitory"],
        }

    def get(self, request):
        ctx = self._get_context()
        ctx["user"] = request.user
        return render(request, self.template_name, ctx)

    def post(self, request):
        from room_inventory.models import Campus, GuestHouse

        data = request.POST
        errors = {}

        # ── Mandatory fields ────────────────────────────────────────────
        purpose = data.get("purpose_of_booking", "").strip()
        if not purpose:
            errors["purpose_of_booking"] = "Purpose of booking is required."

        mobile = data.get("mobile_number", "").strip()
        if not mobile:
            errors["mobile_number"] = "Mobile number is required."

        is_faculty_incharge = data.get("is_faculty_incharge") == "on"
        incharge_name = data.get("incharge_name", "").strip()
        incharge_email = data.get("incharge_email", "").strip()

        if not is_faculty_incharge:
            if not incharge_name:
                errors["incharge_name"] = "Faculty in-charge name is required."
            if not incharge_email:
                errors["incharge_email"] = "Faculty in-charge email is required."

        if errors:
            ctx = self._get_context()
            ctx.update({"user": request.user, "errors": errors, "form_data": data})
            return render(request, self.template_name, ctx, status=422)

        # ── Build the BookingRequest ────────────────────────────────────
        campus_id = data.get("campus_id") or None
        campus_name = ""
        if campus_id:
            try:
                campus_obj = Campus.objects.get(pk=campus_id)
                campus_name = campus_obj.name
            except Campus.DoesNotExist:
                campus_id = None

        gh_id = data.get("preferred_guest_house_id") or None
        gh_name = ""
        if gh_id:
            try:
                gh_obj = GuestHouse.objects.get(pk=gh_id)
                gh_name = gh_obj.name
            except GuestHouse.DoesNotExist:
                gh_id = None

        booking = BookingRequest.objects.create(
            requestor=request.user,
            mobile_number=mobile,
            is_faculty_incharge=is_faculty_incharge,
            incharge_name=incharge_name if not is_faculty_incharge else "",
            incharge_email=incharge_email if not is_faculty_incharge else "",
            incharge_mobile=data.get("incharge_mobile", "").strip() if not is_faculty_incharge else "",
            campus_id=campus_id,
            campus_name=campus_name,
            purpose_of_booking=purpose,
            event_id=data.get("event_id") or None,
            event_name=data.get("event_name", "").strip(),
            event_date=data.get("event_date") or None,
            event_type=data.get("event_type", "").strip(),
            num_guests_male=int(data.get("num_guests_male") or 0),
            num_guests_female=int(data.get("num_guests_female") or 0),
            num_rooms_required=int(data.get("num_rooms_required") or 1),
            is_foreign_guest=data.get("is_foreign_guest") == "on",
            preferred_guest_house_id=gh_id,
            preferred_guest_house_name=gh_name,
            room_configuration=data.get("room_configuration", "").strip(),
            special_requests=data.get("special_requests", "").strip(),
            food_arrangement=data.get("food_arrangement", "NOT_REQUIRED"),
            travel_arrangement=data.get("travel_arrangement", "NOT_REQUIRED"),
            local_transport_arrangement=data.get("local_transport_arrangement", "NOT_REQUIRED"),
            payment_arrangement=data.get("payment_arrangement", "GUEST"),
            room_sharing_grouping=data.get("room_sharing_grouping", "").strip(),
        )

        # ── Alternate contacts ─────────────────────────────────────────
        from booking.models import AlternateContact, Guest

        contact_names = data.getlist("contact_name")
        contact_mobiles = data.getlist("contact_mobile")
        contact_emails = data.getlist("contact_email")
        for i, name in enumerate(contact_names[:4]):
            name = name.strip()
            if name:
                AlternateContact.objects.create(
                    booking=booking,
                    name=name,
                    mobile=contact_mobiles[i] if i < len(contact_mobiles) else "",
                    email=contact_emails[i] if i < len(contact_emails) else "",
                )

        # ── Guests ────────────────────────────────────────────────────
        guest_names = data.getlist("guest_name")
        for i, g_name in enumerate(guest_names):
            g_name = g_name.strip()
            if not g_name:
                continue
            check_in = data.getlist("guest_check_in")[i] if i < len(data.getlist("guest_check_in")) else None
            check_out = data.getlist("guest_check_out")[i] if i < len(data.getlist("guest_check_out")) else None
            if check_in and check_out:
                Guest.objects.create(
                    booking=booking,
                    name=g_name,
                    mobile=data.getlist("guest_mobile")[i] if i < len(data.getlist("guest_mobile")) else "",
                    gender=data.getlist("guest_gender")[i] if i < len(data.getlist("guest_gender")) else "M",
                    email=data.getlist("guest_email")[i] if i < len(data.getlist("guest_email")) else "",
                    guest_type=data.getlist("guest_type")[i] if i < len(data.getlist("guest_type")) else "DOMESTIC",
                    check_in=check_in,
                    check_out=check_out,
                    disability_needs=data.getlist("guest_disability")[i] if i < len(data.getlist("guest_disability")) else "",
                )

        # ── Submit if the user clicked "Submit" (not "Save Draft") ─────
        action_type = data.get("action", "draft")
        if action_type == "submit":
            try:
                booking.submit(request.user)
                send_booking_confirmation_email.delay(booking.pk)
                messages.success(
                    request,
                    f"Booking {booking.booking_id} submitted successfully! "
                    f"A confirmation email has been sent.",
                )
            except Exception as e:
                messages.warning(request, f"Booking saved as draft. Submit failed: {e}")
        else:
            messages.success(request, "Booking saved as draft. You can submit it from My Bookings.")

        return redirect("booking:my-bookings")


class MyBookingsView(LoginRequiredMixin, ListView):
    """
    GET /booking/my-bookings/
    Shows all bookings belonging to the logged-in requestor.
    For other roles, shows all bookings (HOD/Management dashboard entry point).
    """

    template_name = "booking/my_bookings.html"
    context_object_name = "bookings"
    paginate_by = 20

    def get_queryset(self):
        user = self.request.user
        qs = BookingRequest.objects.select_related("requestor").prefetch_related("guests")
        if user.role == "REQUESTOR":
            qs = qs.filter(requestor=user)
        status_filter = self.request.GET.get("status")
        if status_filter:
            qs = qs.filter(status=status_filter)
        return qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["status_choices"] = BookingRequest.Status.choices
        ctx["current_status"] = self.request.GET.get("status", "")
        return ctx


class BookingDetailView(LoginRequiredMixin, DetailView):
    """
    GET /booking/<id>/
    Detail view for a single booking. Requestors can only see their own.
    """

    template_name = "booking/booking_detail.html"
    context_object_name = "booking"

    def get_queryset(self):
        user = self.request.user
        qs = BookingRequest.objects.select_related("requestor", "rejected_by").prefetch_related(
            "guests", "alternate_contacts"
        )
        if user.role == "REQUESTOR":
            return qs.filter(requestor=user)
        return qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        booking = ctx["booking"]
        ctx["can_cancel"] = booking.is_cancellable and booking.requestor == self.request.user
        ctx["can_edit"] = booking.is_editable and booking.requestor == self.request.user
        return ctx


@login_required
def booking_cancel_view(request, pk):
    """
    POST /booking/<pk>/cancel/   (web UI cancel action)
    """
    booking = get_object_or_404(BookingRequest, pk=pk)
    if request.method == "POST":
        try:
            booking.cancel(request.user)
            messages.success(request, f"Booking {booking.booking_id or '(draft)'} has been cancelled.")
        except (ValueError, PermissionError) as e:
            messages.error(request, str(e))
    return redirect("booking:my-bookings")


# ── Stub placeholder views for other roles (not yet built) ───────────────────

@login_required
def approvals_view(request):
    """Stub: HOD/Director approval queue — to be built in a future sprint."""
    return render(request, "booking/stub_page.html", {
        "page_title": "Pending Approvals",
        "message": "The approvals dashboard is under construction. "
                   "This module is owned by the approval workflow sprint.",
    })


@login_required
def management_approvals_view(request):
    """Stub: Management final approval queue."""
    return render(request, "booking/stub_page.html", {
        "page_title": "Management Approvals",
        "message": "The management approvals view is under construction.",
    })


@login_required
def allotment_view(request):
    """Stub: Guest House Team allotment view."""
    return render(request, "booking/stub_page.html", {
        "page_title": "Room Allotment",
        "message": "The allotment view is under construction. "
                   "This module is owned by the Guest House Team sprint.",
    })
