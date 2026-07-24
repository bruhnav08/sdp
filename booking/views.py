"""
booking/views.py
-----------------
Views for the booking module. Two layers:

1. DRF API (BookingRequestViewSet)
   Endpoints:
       GET    /api/bookings/               → list bookings (role filtered)
       POST   /api/bookings/               → create DRAFT booking
       GET    /api/bookings/<id>/          → retrieve booking detail
       PATCH  /api/bookings/<id>/          → update DRAFT booking
       DELETE /api/bookings/<id>/          → delete DRAFT booking
       POST   /api/bookings/<id>/submit/   → DRAFT → PENDING_HOD_APPROVAL
       POST   /api/bookings/<id>/hod_approve/ → approve by HOD
       POST   /api/bookings/<id>/hod_reject/  → reject by HOD
       POST   /api/bookings/<id>/hod_query/   → raise query by HOD
       POST   /api/bookings/<id>/allot_room/  → allot room by GH Team
       POST   /api/bookings/<id>/propose_alternative/ → propose alt room
       POST   /api/bookings/<id>/accept_alternative/  → accept alt room
       POST   /api/bookings/<id>/reject_alternative/  → reject alt room
       POST   /api/bookings/<id>/mgmt_approve/ → final approval by Management
       POST   /api/bookings/<id>/mgmt_reject/  → rejection by Management
       POST   /api/bookings/<id>/mgmt_hold/    → place on hold
       POST   /api/bookings/<id>/mgmt_query/   → raise query by Management
       POST   /api/bookings/<id>/respond_query/→ submit query response
       POST   /api/bookings/<id>/cancel/       → cancel booking

2. HTMX/Template views (web UI)
   URLs:
       GET/POST /booking/new/              → booking application form
       GET      /booking/my-bookings/      → list of requestor's bookings
       GET      /booking/<id>/             → booking detail & approval timeline
       GET      /booking/approvals/        → HOD Pending Approvals queue
       GET      /booking/allotment/        → Guest House Team Allotment queue
       GET      /booking/approvals/management/ → Management Approvals queue
"""

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import PermissionDenied, ValidationError
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.views import View
from django.views.generic import DetailView, ListView
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from accounts.models import User
from accounts.permissions import IsApprover, IsGuestHouseTeam, IsManagement, role_required
from booking.models import BookingRequest
from booking.serializers import BookingRequestListSerializer, BookingRequestSerializer
from booking.tasks import send_booking_confirmation_email
from common.api_response import error_response, success_response
from room_inventory.models import GuestHouse, Room


# ── DRF API ViewSet ───────────────────────────────────────────────────────────

class BookingRequestViewSet(viewsets.ModelViewSet):
    """
    Full CRUD + workflow approval actions for BookingRequest.
    """

    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        base_qs = (
            BookingRequest.objects.select_related(
                "requestor", "allotted_room", "allotted_guest_house", "proposed_room", "proposed_guest_house"
            )
            .prefetch_related("guests", "alternate_contacts", "approval_history")
        )
        if user.role == User.Role.REQUESTOR:
            return base_qs.filter(requestor=user)
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
        booking = self.get_object()
        try:
            booking.submit(request.user)
            send_booking_confirmation_email.delay(booking.pk)
        except (ValueError, PermissionError) as exc:
            return error_response(message=str(exc))

        serializer = BookingRequestSerializer(booking, context={"request": request})
        return success_response(
            data=serializer.data,
            message=f"Booking {booking.booking_id} submitted successfully for HOD approval.",
        )

    @action(detail=True, methods=["post"], url_path="hod_approve")
    def hod_approve(self, request, pk=None):
        booking = self.get_object()
        comments = request.data.get("comments", "")
        try:
            booking.approve_by_hod(request.user, comments=comments)
        except (ValueError, PermissionError) as exc:
            return error_response(message=str(exc))
        serializer = BookingRequestSerializer(booking, context={"request": request})
        return success_response(data=serializer.data, message="Approved by HOD successfully.")

    @action(detail=True, methods=["post"], url_path="hod_reject")
    def hod_reject(self, request, pk=None):
        booking = self.get_object()
        reason = request.data.get("reason", "")
        try:
            booking.reject(request.user, reason=reason)
        except (ValueError, PermissionError) as exc:
            return error_response(message=str(exc))
        serializer = BookingRequestSerializer(booking, context={"request": request})
        return success_response(data=serializer.data, message="Booking request rejected by HOD.")

    @action(detail=True, methods=["post"], url_path="hod_query")
    def hod_query(self, request, pk=None):
        booking = self.get_object()
        query_text = request.data.get("query_text", "")
        try:
            booking.query_by_hod(request.user, query_text=query_text)
        except (ValueError, PermissionError) as exc:
            return error_response(message=str(exc))
        serializer = BookingRequestSerializer(booking, context={"request": request})
        return success_response(data=serializer.data, message="Query raised to requestor.")

    @action(detail=True, methods=["post"], url_path="allot_room")
    def allot_room(self, request, pk=None):
        booking = self.get_object()
        room_id = request.data.get("room_id")
        comments = request.data.get("comments", "")
        if not room_id:
            return error_response(message="room_id is required.")
        room = get_object_or_404(Room, pk=room_id)
        try:
            booking.allot_room(request.user, room=room, comments=comments)
        except (ValueError, PermissionError) as exc:
            return error_response(message=str(exc))
        serializer = BookingRequestSerializer(booking, context={"request": request})
        return success_response(data=serializer.data, message=f"Room {room.room_number} allotted successfully.")

    @action(detail=True, methods=["post"], url_path="propose_alternative")
    def propose_alternative(self, request, pk=None):
        booking = self.get_object()
        room_id = request.data.get("room_id")
        note = request.data.get("note", "")
        if not room_id:
            return error_response(message="room_id is required for alternative proposal.")
        room = get_object_or_404(Room, pk=room_id)
        try:
            booking.propose_alternative(request.user, room=room, note=note)
        except (ValueError, PermissionError) as exc:
            return error_response(message=str(exc))
        serializer = BookingRequestSerializer(booking, context={"request": request})
        return success_response(data=serializer.data, message="Alternative room proposed to requestor.")

    @action(detail=True, methods=["post"], url_path="accept_alternative")
    def accept_alternative(self, request, pk=None):
        booking = self.get_object()
        try:
            booking.accept_alternative(request.user)
        except (ValueError, PermissionError) as exc:
            return error_response(message=str(exc))
        serializer = BookingRequestSerializer(booking, context={"request": request})
        return success_response(data=serializer.data, message="Proposed alternative room accepted.")

    @action(detail=True, methods=["post"], url_path="reject_alternative")
    def reject_alternative(self, request, pk=None):
        booking = self.get_object()
        reason = request.data.get("reason", "")
        try:
            booking.reject_alternative(request.user, reason=reason)
        except (ValueError, PermissionError) as exc:
            return error_response(message=str(exc))
        serializer = BookingRequestSerializer(booking, context={"request": request})
        return success_response(data=serializer.data, message="Proposed alternative room declined.")

    @action(detail=True, methods=["post"], url_path="mgmt_approve")
    def mgmt_approve(self, request, pk=None):
        booking = self.get_object()
        comments = request.data.get("comments", "")
        try:
            booking.approve_by_management(request.user, comments=comments)
        except (ValueError, PermissionError) as exc:
            return error_response(message=str(exc))
        serializer = BookingRequestSerializer(booking, context={"request": request})
        return success_response(data=serializer.data, message="Final approval by Management completed. Booking confirmed.")

    @action(detail=True, methods=["post"], url_path="mgmt_reject")
    def mgmt_reject(self, request, pk=None):
        booking = self.get_object()
        reason = request.data.get("reason", "")
        try:
            booking.reject(request.user, reason=reason)
        except (ValueError, PermissionError) as exc:
            return error_response(message=str(exc))
        serializer = BookingRequestSerializer(booking, context={"request": request})
        return success_response(data=serializer.data, message="Booking request rejected by Management.")

    @action(detail=True, methods=["post"], url_path="mgmt_hold")
    def mgmt_hold(self, request, pk=None):
        booking = self.get_object()
        reason = request.data.get("reason", "")
        try:
            booking.hold_by_management(request.user, reason=reason)
        except (ValueError, PermissionError) as exc:
            return error_response(message=str(exc))
        serializer = BookingRequestSerializer(booking, context={"request": request})
        return success_response(data=serializer.data, message="Booking request placed on hold.")

    @action(detail=True, methods=["post"], url_path="mgmt_query")
    def mgmt_query(self, request, pk=None):
        booking = self.get_object()
        query_text = request.data.get("query_text", "")
        try:
            booking.query_by_management(request.user, query_text=query_text)
        except (ValueError, PermissionError) as exc:
            return error_response(message=str(exc))
        serializer = BookingRequestSerializer(booking, context={"request": request})
        return success_response(data=serializer.data, message="Query raised to requestor by Management.")

    @action(detail=True, methods=["post"], url_path="respond_query")
    def respond_query(self, request, pk=None):
        booking = self.get_object()
        response_text = request.data.get("response_text", "")
        try:
            booking.respond_to_query(request.user, response_text=response_text)
        except (ValueError, PermissionError) as exc:
            return error_response(message=str(exc))
        serializer = BookingRequestSerializer(booking, context={"request": request})
        return success_response(data=serializer.data, message="Query response submitted successfully.")

    @action(detail=True, methods=["post"], url_path="cancel")
    def cancel(self, request, pk=None):
        booking = self.get_object()
        try:
            booking.cancel(request.user)
        except (ValueError, PermissionError) as exc:
            return error_response(message=str(exc))
        return success_response(message=f"Booking {booking.booking_id or 'request'} has been cancelled.")


# ── HTMX Partial Views ────────────────────────────────────────────────────────

@login_required
def htmx_guest_houses(request):
    campus_id = request.GET.get("campus")
    guest_houses = []
    if campus_id:
        guest_houses = GuestHouse.objects.filter(campus_id=campus_id, is_active=True)
    return render(request, "booking/partials/guest_house_options.html", {"guest_houses": guest_houses})


@login_required
def htmx_event_date(request):
    from room_inventory.models import Event
    event_id = request.GET.get("event")
    event = None
    if event_id:
        try:
            event = Event.objects.get(pk=event_id, is_active=True)
        except Event.DoesNotExist:
            pass
    return render(request, "booking/partials/event_date.html", {"event": event})


@login_required
def htmx_events_for_campus(request):
    from room_inventory.models import Event
    campus_id = request.GET.get("campus")
    events = []
    if campus_id:
        events = Event.objects.filter(campus_id=campus_id, is_active=True)
    return render(request, "booking/partials/event_options.html", {"events": events})


# ── Template Views (Web UI) ───────────────────────────────────────────────────

class BookingFormView(LoginRequiredMixin, View):
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
        from booking.models import AlternateContact, Guest
        from room_inventory.models import Campus, GuestHouse

        data = request.POST
        errors = {}

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

        # Guest date validation: check-out must be after check-in
        guest_names = data.getlist("guest_name")
        guest_check_ins = data.getlist("guest_check_in")
        guest_check_outs = data.getlist("guest_check_out")
        for i, g_name in enumerate(guest_names):
            g_name = g_name.strip()
            if not g_name:
                continue
            ci = guest_check_ins[i] if i < len(guest_check_ins) else None
            co = guest_check_outs[i] if i < len(guest_check_outs) else None
            if ci and co and co <= ci:
                errors["guest_dates"] = "Check-out date must be after check-in date."
                break

        if errors:
            ctx = self._get_context()
            ctx.update({"user": request.user, "errors": errors, "form_data": data})
            return render(request, self.template_name, ctx, status=422)

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

        action_type = data.get("action", "draft")
        if action_type == "submit":
            try:
                booking.submit(request.user)
                send_booking_confirmation_email.delay(booking.pk)
                messages.success(request, f"Booking {booking.booking_id} submitted successfully!")
            except Exception as e:
                messages.warning(request, f"Booking saved as draft. Submit failed: {e}")
        else:
            messages.success(request, "Booking saved as draft. You can submit it from My Bookings.")

        return redirect("booking:my-bookings")


class MyBookingsView(LoginRequiredMixin, ListView):
    template_name = "booking/my_bookings.html"
    context_object_name = "bookings"
    paginate_by = 20

    def get_queryset(self):
        user = self.request.user
        qs = BookingRequest.objects.select_related("requestor", "allotted_room", "allotted_guest_house").prefetch_related("guests")
        if user.role == User.Role.REQUESTOR:
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
    template_name = "booking/booking_detail.html"
    context_object_name = "booking"

    def get_queryset(self):
        user = self.request.user
        qs = BookingRequest.objects.select_related(
            "requestor", "rejected_by", "allotted_room", "allotted_guest_house", "proposed_room", "proposed_guest_house"
        ).prefetch_related("guests", "alternate_contacts", "approval_history")
        if user.role == User.Role.REQUESTOR:
            return qs.filter(requestor=user)
        return qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        booking = ctx["booking"]
        user = self.request.user

        ctx["can_cancel"] = booking.is_cancellable and (booking.requestor == user or user.is_superuser or user.role == "ADMIN")
        ctx["can_edit"] = booking.is_editable and (booking.requestor == user or user.is_superuser or user.role == "ADMIN")

        ctx["can_hod_act"] = (user.is_approver or user.is_admin_user) and booking.status == BookingRequest.Status.PENDING_HOD_APPROVAL
        ctx["can_allot_act"] = (user.is_guest_house_team or user.is_admin_user) and booking.status == BookingRequest.Status.PENDING_ALLOTMENT
        ctx["can_mgmt_act"] = (user.is_management or user.is_admin_user) and booking.status in (
            BookingRequest.Status.PENDING_MANAGEMENT_APPROVAL,
            BookingRequest.Status.ON_HOLD,
        )
        ctx["can_respond_query"] = (booking.requestor == user or user.is_admin_user) and booking.status == BookingRequest.Status.QUERY_RAISED
        ctx["can_respond_alternative"] = (booking.requestor == user or user.is_admin_user) and booking.status == BookingRequest.Status.ALTERNATIVE_PROPOSED

        if ctx["can_allot_act"]:
            check_in = booking.check_in_date
            check_out = booking.check_out_date
            all_rooms = Room.objects.filter(is_active=True, status=Room.Status.VACANT_CLEAN).select_related("guest_house", "room_category")
            
            available_for_period = []
            if check_in and check_out:
                for r in all_rooms:
                    if r.is_available_for_period(check_in, check_out, exclude_booking_pk=booking.pk):
                        available_for_period.append(r)
            else:
                available_for_period = list(all_rooms)
            ctx["available_rooms"] = available_for_period

        ctx["approval_history"] = booking.approval_history.all()
        return ctx


@login_required
def booking_cancel_view(request, pk):
    booking = get_object_or_404(BookingRequest, pk=pk)
    if request.method == "POST":
        try:
            booking.cancel(request.user)
            messages.success(request, f"Booking {booking.booking_id or '(draft)'} has been cancelled.")
        except (ValueError, PermissionError) as e:
            messages.error(request, str(e))
    return redirect("booking:my-bookings")


# ── Role Approvals Dashboards ──────────────────────────────────────────────────

@login_required
@role_required(User.Role.HOD_DIRECTOR, User.Role.FACULTY_INCHARGE, User.Role.ADMIN)
def approvals_view(request):
    """
    HOD / Director Pending Approvals Queue.
    """
    pending_bookings = BookingRequest.objects.filter(
        status=BookingRequest.Status.PENDING_HOD_APPROVAL
    ).select_related("requestor").prefetch_related("guests")

    return render(
        request,
        "booking/hod_approvals.html",
        {"pending_bookings": pending_bookings},
    )


@login_required
@role_required(User.Role.GUEST_HOUSE_TEAM, User.Role.ADMIN)
def allotment_view(request):
    """
    Guest House Team Room Allotment Queue.
    """
    pending_allotments = BookingRequest.objects.filter(
        status=BookingRequest.Status.PENDING_ALLOTMENT
    ).select_related("requestor").prefetch_related("guests")

    available_rooms = Room.objects.filter(is_active=True, status=Room.Status.VACANT_CLEAN).select_related("guest_house", "room_category")

    return render(
        request,
        "booking/allotment_queue.html",
        {
            "pending_allotments": pending_allotments,
            "available_rooms": available_rooms,
        },
    )


@login_required
@role_required(User.Role.MANAGEMENT, User.Role.ADMIN)
def management_approvals_view(request):
    """
    Management Final Approvals Queue.
    """
    pending_mgmt = BookingRequest.objects.filter(
        status__in=[
            BookingRequest.Status.PENDING_MANAGEMENT_APPROVAL,
            BookingRequest.Status.ON_HOLD,
        ]
    ).select_related("requestor", "allotted_room", "allotted_guest_house").prefetch_related("guests")

    return render(
        request,
        "booking/management_approvals.html",
        {"pending_mgmt": pending_mgmt},
    )


# ── HTML Form Action POST Handlers ───────────────────────────────────────────

@login_required
@role_required(User.Role.HOD_DIRECTOR, User.Role.FACULTY_INCHARGE, User.Role.ADMIN)
def hod_action_view(request, pk):
    booking = get_object_or_404(BookingRequest, pk=pk)
    if request.method == "POST":
        action_type = request.POST.get("action_type")
        comments = request.POST.get("comments", "").strip()
        try:
            if action_type == "approve":
                booking.approve_by_hod(request.user, comments=comments)
                messages.success(request, f"Booking {booking.booking_id} approved and sent for room allotment.")
            elif action_type == "reject":
                booking.reject(request.user, reason=comments)
                messages.success(request, f"Booking {booking.booking_id} rejected.")
            elif action_type == "query":
                booking.query_by_hod(request.user, query_text=comments)
                messages.success(request, f"Query sent to requestor for booking {booking.booking_id}.")
            else:
                messages.error(request, "Invalid action.")
        except (ValueError, PermissionError) as e:
            messages.error(request, str(e))
    return redirect("booking:booking-detail", pk=booking.pk)


@login_required
@role_required(User.Role.GUEST_HOUSE_TEAM, User.Role.ADMIN)
def allotment_action_view(request, pk):
    booking = get_object_or_404(BookingRequest, pk=pk)
    if request.method == "POST":
        action_type = request.POST.get("action_type")
        room_id = request.POST.get("room_id")
        comments = request.POST.get("comments", "").strip()

        try:
            if action_type == "allot":
                if not room_id:
                    messages.error(request, "Please select a room to allot.")
                    return redirect("booking:booking-detail", pk=booking.pk)
                room = get_object_or_404(Room, pk=room_id)
                booking.allot_room(request.user, room=room, comments=comments)
                messages.success(request, f"Room {room.room_number} allotted for booking {booking.booking_id}. Sent for Management approval.")
            elif action_type == "propose":
                if not room_id:
                    messages.error(request, "Please select a proposed alternative room.")
                    return redirect("booking:booking-detail", pk=booking.pk)
                room = get_object_or_404(Room, pk=room_id)
                booking.propose_alternative(request.user, room=room, note=comments)
                messages.success(request, f"Proposed alternative Room {room.room_number} to requestor.")
            elif action_type == "reject":
                booking.reject(request.user, reason=comments)
                messages.success(request, f"Booking {booking.booking_id} rejected.")
            else:
                messages.error(request, "Invalid action.")
        except (ValueError, PermissionError) as e:
            messages.error(request, str(e))
    return redirect("booking:booking-detail", pk=booking.pk)


@login_required
@role_required(User.Role.MANAGEMENT, User.Role.ADMIN)
def management_action_view(request, pk):
    booking = get_object_or_404(BookingRequest, pk=pk)
    if request.method == "POST":
        action_type = request.POST.get("action_type")
        comments = request.POST.get("comments", "").strip()
        try:
            if action_type == "approve":
                booking.approve_by_management(request.user, comments=comments)
                send_booking_confirmation_email.delay(booking.pk)
                messages.success(request, f"Booking {booking.booking_id} confirmed!")
            elif action_type == "hold":
                booking.hold_by_management(request.user, reason=comments)
                messages.warning(request, f"Booking {booking.booking_id} placed on hold.")
            elif action_type == "reject":
                booking.reject(request.user, reason=comments)
                messages.success(request, f"Booking {booking.booking_id} rejected.")
            elif action_type == "query":
                booking.query_by_management(request.user, query_text=comments)
                messages.success(request, f"Query sent to requestor for booking {booking.booking_id}.")
            else:
                messages.error(request, "Invalid action.")
        except (ValueError, PermissionError) as e:
            messages.error(request, str(e))
    return redirect("booking:booking-detail", pk=booking.pk)


@login_required
def respond_query_view(request, pk):
    booking = get_object_or_404(BookingRequest, pk=pk)
    if request.method == "POST":
        response_text = request.POST.get("response_text", "").strip()
        try:
            booking.respond_to_query(request.user, response_text=response_text)
            messages.success(request, f"Query response submitted for booking {booking.booking_id}.")
        except (ValueError, PermissionError) as e:
            messages.error(request, str(e))
    return redirect("booking:booking-detail", pk=booking.pk)


@login_required
def alternative_response_view(request, pk):
    booking = get_object_or_404(BookingRequest, pk=pk)
    if request.method == "POST":
        response_action = request.POST.get("response_action")
        reason = request.POST.get("reason", "").strip()
        try:
            if response_action == "accept":
                booking.accept_alternative(request.user)
                messages.success(request, f"Alternative room accepted. Sent for Management approval.")
            elif response_action == "decline":
                booking.reject_alternative(request.user, reason=reason)
                messages.success(request, f"Alternative room declined. Booking cancelled.")
            else:
                messages.error(request, "Invalid response action.")
        except (ValueError, PermissionError) as e:
            messages.error(request, str(e))
    return redirect("booking:booking-detail", pk=booking.pk)
