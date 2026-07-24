"""
booking/models.py
-----------------
Core models for the Guest Room Booking module.

Models
------
BookingRequest  — main booking entity with strict status-transition guards
Guest           — guests associated with a BookingRequest
AlternateContact — backup contact persons for a booking
ApprovalHistory — audit trail log for every approval action and status transition
NotificationLog — in-app workflow event notification log

Status Lifecycle
----------------
DRAFT
  └─ submit() → PENDING_HOD_APPROVAL
       ├─ query_by_hod() ──► QUERY_RAISED ──(respond_to_query)──┐
       │                                                         │
       └─ approve_by_hod() ──► PENDING_ALLOTMENT ◄───────────────┘
            ├─ propose_alternative() ──► ALTERNATIVE_PROPOSED ──► accept_alternative() ──┐
            │                                                                            │
            └─ allot_room() ──────────► PENDING_MANAGEMENT_APPROVAL ◄───────────────────┘
                 ├─ hold_by_management()   ──► ON_HOLD
                 ├─ query_by_mgmt()        ──► QUERY_RAISED
                 └─ approve_by_management()──► CONFIRMED

Rejection can occur at HOD, Allotment, or Management stage.
Cancellation can be initiated by the Requestor.
"""

import random
import string

from django.conf import settings
from django.db import models
from django.utils import timezone

from common.models import TimeStampedModel


class BookingRequest(TimeStampedModel):
    """
    A request to book guest accommodation.

    The full business lifecycle is encapsulated in transition methods.
    Direct modification of `.status` is prohibited.
    """

    class Status(models.TextChoices):
        DRAFT = "DRAFT", "Draft"
        PENDING_HOD_APPROVAL = "PENDING_HOD_APPROVAL", "Pending HOD Approval"
        PENDING_ALLOTMENT = "PENDING_ALLOTMENT", "Pending Room Allotment"
        ALTERNATIVE_PROPOSED = "ALTERNATIVE_PROPOSED", "Alternative Room Proposed"
        PENDING_MANAGEMENT_APPROVAL = "PENDING_MANAGEMENT_APPROVAL", "Pending Management Approval"
        ON_HOLD = "ON_HOLD", "On Hold"
        QUERY_RAISED = "QUERY_RAISED", "Query / Clarification Required"
        CONFIRMED = "CONFIRMED", "Confirmed"
        REJECTED = "REJECTED", "Rejected"
        CANCELLED = "CANCELLED", "Cancelled"

    _REJECTABLE_STATUSES = frozenset([
        Status.PENDING_HOD_APPROVAL,
        Status.PENDING_ALLOTMENT,
        Status.ALTERNATIVE_PROPOSED,
        Status.PENDING_MANAGEMENT_APPROVAL,
        Status.ON_HOLD,
        Status.QUERY_RAISED,
    ])

    # ── Identity ──────────────────────────────────────────────────────────────
    booking_id = models.CharField(
        max_length=20,
        unique=True,
        blank=True,
        db_index=True,
        help_text="Auto-generated on submit. Format: BK-YYYYMM-XXXX",
    )
    status = models.CharField(
        max_length=35,
        choices=Status.choices,
        default=Status.DRAFT,
        db_index=True,
    )

    # ── Requestor ─────────────────────────────────────────────────────────────
    requestor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="booking_requests",
        help_text="The user who created this booking request.",
    )
    mobile_number = models.CharField(
        max_length=15,
        help_text="Contact number for this booking (may differ from profile).",
    )

    # ── Faculty In-Charge ─────────────────────────────────────────────────────
    is_faculty_incharge = models.BooleanField(
        default=False,
        help_text="True if the requestor is themselves the Faculty In-Charge.",
    )
    incharge_name = models.CharField(max_length=150, blank=True)
    incharge_email = models.EmailField(blank=True)
    incharge_mobile = models.CharField(max_length=15, blank=True)

    # ── Campus & Event ────────────────────────────────────────────────────────
    campus_id = models.PositiveIntegerField(null=True, blank=True)
    campus_name = models.CharField(max_length=150, blank=True)

    purpose_of_booking = models.TextField(
        help_text="Mandatory. Reason this accommodation is being requested.",
    )

    event_id = models.PositiveIntegerField(null=True, blank=True)
    event_name = models.CharField(max_length=250, blank=True)
    event_date = models.DateField(null=True, blank=True)
    event_type = models.CharField(max_length=100, blank=True)

    # ── Guest counts ──────────────────────────────────────────────────────────
    num_guests_male = models.PositiveIntegerField(default=0)
    num_guests_female = models.PositiveIntegerField(default=0)
    num_rooms_required = models.PositiveIntegerField(default=1)

    # ── Foreign guest ─────────────────────────────────────────────────────────
    is_foreign_guest = models.BooleanField(
        default=False,
        help_text="Triggers Form C requirement when True.",
    )

    # ── Preferred Guest House & Room Config ───────────────────────────────────
    preferred_guest_house_id = models.PositiveIntegerField(null=True, blank=True)
    preferred_guest_house_name = models.CharField(max_length=250, blank=True)
    room_configuration = models.CharField(
        max_length=100,
        blank=True,
        help_text="E.g. Single, Double, Suite.",
    )

    special_requests = models.TextField(blank=True)

    # ── Room Allotment Fields ─────────────────────────────────────────────────
    allotted_room = models.ForeignKey(
        "room_inventory.Room",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="allotted_bookings",
    )
    allotted_guest_house = models.ForeignKey(
        "room_inventory.GuestHouse",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="allotted_guesthouse_bookings",
    )

    # Alternative Room Proposal Fields
    proposed_room = models.ForeignKey(
        "room_inventory.Room",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="proposed_bookings",
    )
    proposed_guest_house = models.ForeignKey(
        "room_inventory.GuestHouse",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="proposed_guesthouse_bookings",
    )
    proposed_note = models.TextField(blank=True)

    # Query & Clarification Fields
    query_text = models.TextField(blank=True)
    query_stage = models.CharField(max_length=35, blank=True)
    query_response = models.TextField(blank=True)

    # Management Hold Reason
    hold_reason = models.TextField(blank=True)

    # Approver User Tracking
    hod_approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="hod_approved_bookings",
    )
    allotted_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="allotted_bookings",
    )
    management_approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="management_approved_bookings",
    )

    # ── Arrangements ─────────────────────────────────────────────────────────
    class ArrangementChoice(models.TextChoices):
        UNIVERSITY = "UNIVERSITY", "University"
        DEPARTMENT = "DEPARTMENT", "Department"
        SELF = "SELF", "Self"
        NOT_REQUIRED = "NOT_REQUIRED", "Not Required"

    food_arrangement = models.CharField(
        max_length=20,
        choices=ArrangementChoice.choices,
        default=ArrangementChoice.NOT_REQUIRED,
    )
    travel_arrangement = models.CharField(
        max_length=20,
        choices=ArrangementChoice.choices,
        default=ArrangementChoice.NOT_REQUIRED,
    )
    local_transport_arrangement = models.CharField(
        max_length=20,
        choices=ArrangementChoice.choices,
        default=ArrangementChoice.NOT_REQUIRED,
    )

    class PaymentChoice(models.TextChoices):
        GUEST = "GUEST", "Guest Pays"
        DEPARTMENT = "DEPARTMENT", "Department"
        UNIVERSITY = "UNIVERSITY", "University"

    payment_arrangement = models.CharField(
        max_length=20,
        choices=PaymentChoice.choices,
        default=PaymentChoice.GUEST,
    )
    room_sharing_grouping = models.TextField(blank=True)

    # ── Rejection Audit ───────────────────────────────────────────────────────
    rejection_reason = models.TextField(blank=True)
    rejected_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="rejected_bookings",
    )
    rejection_stage = models.CharField(max_length=35, blank=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Booking Request"
        verbose_name_plural = "Booking Requests"
        indexes = [
            models.Index(fields=["requestor", "status"]),
            models.Index(fields=["status", "created_at"]),
        ]

    def __str__(self) -> str:
        label = self.booking_id or f"DRAFT-{self.pk}"
        return f"{label} — {self.requestor} [{self.get_status_display()}]"

    # ── ID Generator & Guards ─────────────────────────────────────────────────

    @staticmethod
    def _generate_booking_id() -> str:
        now = timezone.now()
        for _ in range(10):
            suffix = "".join(random.choices(string.digits, k=4))
            candidate = f"BK-{now.strftime('%Y%m')}-{suffix}"
            if not BookingRequest.objects.filter(booking_id=candidate).exists():
                return candidate
        raise RuntimeError("Could not generate a unique booking ID after 10 attempts.")

    def _assert_status(self, expected, action: str) -> None:
        if isinstance(expected, (list, tuple, set, frozenset)):
            if self.status not in expected:
                raise ValueError(
                    f"Cannot perform '{action}' on booking {self.booking_id or self.pk} in status '{self.status}'. "
                    f"Allowed statuses: {sorted(expected)}"
                )
        elif self.status != expected:
            raise ValueError(
                f"Cannot perform '{action}' on booking {self.booking_id or self.pk} in status '{self.status}'. "
                f"Expected status: '{expected}'"
            )

    def _log_history(self, user, action: str, comments: str, prev_status: str, new_status: str):
        role_label = getattr(user, "get_role_display", lambda: getattr(user, "role", "User"))()
        user_name = user.get_full_name() or user.username if user else "System"
        ApprovalHistory.objects.create(
            booking=self,
            user=user if user and user.is_authenticated else None,
            user_name=user_name,
            role=role_label,
            action=action,
            comments=comments,
            previous_status=prev_status,
            new_status=new_status,
        )

    # ── Workflow Transition Methods ───────────────────────────────────────────

    def submit(self, user) -> None:
        """DRAFT → PENDING_HOD_APPROVAL"""
        self._assert_status(self.Status.DRAFT, "submit")
        if self.requestor_id != user.pk:
            raise PermissionError("Only the requestor can submit this booking.")
        
        prev_status = self.status
        self.booking_id = self._generate_booking_id()
        self.status = self.Status.PENDING_HOD_APPROVAL
        self.save(update_fields=["booking_id", "status", "updated_at"])

        self._log_history(user, "SUBMIT", "Booking submitted for HOD approval.", prev_status, self.status)

    def approve_by_hod(self, user, comments: str = "") -> None:
        """PENDING_HOD_APPROVAL → PENDING_ALLOTMENT"""
        self._assert_status(self.Status.PENDING_HOD_APPROVAL, "approve_by_hod")
        
        prev_status = self.status
        self.status = self.Status.PENDING_ALLOTMENT
        self.hod_approved_by = user
        self.save(update_fields=["status", "hod_approved_by", "updated_at"])

        self._log_history(user, "HOD_APPROVE", comments or "Approved by HOD/Director.", prev_status, self.status)

    def query_by_hod(self, user, query_text: str) -> None:
        """PENDING_HOD_APPROVAL → QUERY_RAISED"""
        self._assert_status(self.Status.PENDING_HOD_APPROVAL, "query_by_hod")
        if not query_text.strip():
            raise ValueError("Query text is required.")

        prev_status = self.status
        self.status = self.Status.QUERY_RAISED
        self.query_stage = prev_status
        self.query_text = query_text.strip()
        self.query_response = ""
        self.save(update_fields=["status", "query_stage", "query_text", "query_response", "updated_at"])

        self._log_history(user, "HOD_QUERY", f"Query raised: {query_text}", prev_status, self.status)
        NotificationLog.objects.create(
            user=self.requestor,
            booking=self,
            title=f"Query Raised for Booking {self.booking_id}",
            message=f"HOD raised a query: {query_text}",
        )

    def allot_room(self, user, room, comments: str = "") -> None:
        """PENDING_ALLOTMENT → PENDING_MANAGEMENT_APPROVAL"""
        self._assert_status(self.Status.PENDING_ALLOTMENT, "allot_room")
        if not room:
            raise ValueError("Allotted room must be provided.")

        prev_status = self.status
        self.allotted_room = room
        self.allotted_guest_house = room.guest_house
        self.allotted_by = user
        self.status = self.Status.PENDING_MANAGEMENT_APPROVAL
        self.save(update_fields=["allotted_room", "allotted_guest_house", "allotted_by", "status", "updated_at"])

        c_msg = f"Room {room.room_number} ({room.guest_house.name}) allotted."
        if comments:
            c_msg += f" Comments: {comments}"

        self._log_history(user, "ALLOT_ROOM", c_msg, prev_status, self.status)
        NotificationLog.objects.create(
            user=self.requestor,
            booking=self,
            title=f"Room Allotted for Booking {self.booking_id}",
            message=f"Room {room.room_number} ({room.guest_house.name}) allotted.",
        )

    def propose_alternative(self, user, room, note: str = "") -> None:
        """PENDING_ALLOTMENT → ALTERNATIVE_PROPOSED"""
        self._assert_status(self.Status.PENDING_ALLOTMENT, "propose_alternative")
        if not room:
            raise ValueError("Proposed room must be provided.")

        prev_status = self.status
        self.proposed_room = room
        self.proposed_guest_house = room.guest_house
        self.proposed_note = note.strip()
        self.status = self.Status.ALTERNATIVE_PROPOSED
        self.save(update_fields=["proposed_room", "proposed_guest_house", "proposed_note", "status", "updated_at"])

        c_msg = f"Proposed alternative Room {room.room_number} ({room.guest_house.name})."
        if note:
            c_msg += f" Note: {note}"

        self._log_history(user, "PROPOSE_ALTERNATIVE", c_msg, prev_status, self.status)
        NotificationLog.objects.create(
            user=self.requestor,
            booking=self,
            title=f"Alternative Room Proposed for Booking {self.booking_id}",
            message=f"Guest House Team proposed alternative Room {room.room_number} ({room.guest_house.name}).",
        )

    def accept_alternative(self, user) -> None:
        """ALTERNATIVE_PROPOSED → PENDING_MANAGEMENT_APPROVAL"""
        self._assert_status(self.Status.ALTERNATIVE_PROPOSED, "accept_alternative")
        if self.requestor_id != user.pk and not (user.is_superuser or user.is_staff or user.role == "ADMIN"):
            raise PermissionError("Only the requestor can accept the proposed alternative.")

        prev_status = self.status
        self.allotted_room = self.proposed_room
        self.allotted_guest_house = self.proposed_guest_house
        self.status = self.Status.PENDING_MANAGEMENT_APPROVAL
        self.save(update_fields=["allotted_room", "allotted_guest_house", "status", "updated_at"])

        self._log_history(user, "ACCEPT_ALTERNATIVE", "Requestor accepted the proposed alternative room.", prev_status, self.status)

    def reject_alternative(self, user, reason: str = "") -> None:
        """ALTERNATIVE_PROPOSED → CANCELLED"""
        self._assert_status(self.Status.ALTERNATIVE_PROPOSED, "reject_alternative")
        if self.requestor_id != user.pk and not (user.is_superuser or user.is_staff or user.role == "ADMIN"):
            raise PermissionError("Only the requestor can decline the proposed alternative.")

        prev_status = self.status
        self.status = self.Status.CANCELLED
        self.save(update_fields=["status", "updated_at"])

        c_msg = "Requestor declined the proposed alternative room."
        if reason:
            c_msg += f" Reason: {reason}"

        self._log_history(user, "REJECT_ALTERNATIVE", c_msg, prev_status, self.status)

    def approve_by_management(self, user, comments: str = "") -> None:
        """PENDING_MANAGEMENT_APPROVAL or ON_HOLD → CONFIRMED"""
        self._assert_status([self.Status.PENDING_MANAGEMENT_APPROVAL, self.Status.ON_HOLD], "approve_by_management")
        
        prev_status = self.status
        self.management_approved_by = user
        self.status = self.Status.CONFIRMED
        self.save(update_fields=["status", "management_approved_by", "updated_at"])

        self._log_history(user, "MGMT_APPROVE", comments or "Final approval by Management. Booking confirmed.", prev_status, self.status)
        NotificationLog.objects.create(
            user=self.requestor,
            booking=self,
            title=f"Booking Confirmed: {self.booking_id}",
            message=f"Your booking {self.booking_id} has been confirmed!",
        )

    def hold_by_management(self, user, reason: str) -> None:
        """PENDING_MANAGEMENT_APPROVAL → ON_HOLD"""
        self._assert_status(self.Status.PENDING_MANAGEMENT_APPROVAL, "hold_by_management")
        if not reason.strip():
            raise ValueError("Reason for placing on hold is required.")

        prev_status = self.status
        self.hold_reason = reason.strip()
        self.status = self.Status.ON_HOLD
        self.save(update_fields=["status", "hold_reason", "updated_at"])

        self._log_history(user, "MGMT_HOLD", f"Placed on hold: {reason}", prev_status, self.status)
        NotificationLog.objects.create(
            user=self.requestor,
            booking=self,
            title=f"Booking Placed On Hold: {self.booking_id}",
            message=f"Management placed booking {self.booking_id} on hold. Reason: {reason}",
        )

    def query_by_management(self, user, query_text: str) -> None:
        """PENDING_MANAGEMENT_APPROVAL → QUERY_RAISED"""
        self._assert_status(self.Status.PENDING_MANAGEMENT_APPROVAL, "query_by_management")
        if not query_text.strip():
            raise ValueError("Query text is required.")

        prev_status = self.status
        self.query_stage = prev_status
        self.query_text = query_text.strip()
        self.query_response = ""
        self.status = self.Status.QUERY_RAISED
        self.save(update_fields=["status", "query_stage", "query_text", "query_response", "updated_at"])

        self._log_history(user, "MGMT_QUERY", f"Management query: {query_text}", prev_status, self.status)
        NotificationLog.objects.create(
            user=self.requestor,
            booking=self,
            title=f"Query Raised for Booking {self.booking_id}",
            message=f"Management raised a query: {query_text}",
        )

    def respond_to_query(self, user, response_text: str) -> None:
        """QUERY_RAISED → query_stage (PENDING_HOD_APPROVAL or PENDING_MANAGEMENT_APPROVAL)"""
        self._assert_status(self.Status.QUERY_RAISED, "respond_to_query")
        if self.requestor_id != user.pk and not (user.is_superuser or user.is_staff or user.role == "ADMIN"):
            raise PermissionError("Only the requestor can respond to queries.")
        if not response_text.strip():
            raise ValueError("Response text is required.")

        prev_status = self.status
        self.query_response = response_text.strip()
        target_status = self.query_stage if self.query_stage else self.Status.PENDING_HOD_APPROVAL
        self.status = target_status
        self.save(update_fields=["status", "query_response", "updated_at"])

        self._log_history(user, "RESPOND_QUERY", f"Requestor response: {response_text}", prev_status, self.status)

    def reject(self, user, reason: str = "") -> None:
        """Any active approval state → REJECTED"""
        if self.status not in self._REJECTABLE_STATUSES:
            raise ValueError(
                f"Cannot reject a booking in status '{self.status}'. "
                f"Rejectable statuses: {sorted(self._REJECTABLE_STATUSES)}"
            )
        
        prev_status = self.status
        self.rejection_stage = prev_status
        self.status = self.Status.REJECTED
        self.rejection_reason = reason.strip()
        self.rejected_by = user
        self.save(update_fields=[
            "status", "rejection_reason", "rejected_by",
            "rejection_stage", "updated_at",
        ])

        c_msg = f"Rejected at stage '{prev_status}'."
        if reason:
            c_msg += f" Reason: {reason}"

        self._log_history(user, "REJECT", c_msg, prev_status, self.status)
        NotificationLog.objects.create(
            user=self.requestor,
            booking=self,
            title=f"Booking Rejected: {self.booking_id}",
            message=f"Your booking {self.booking_id} was rejected. Reason: {reason or 'No reason provided.'}",
        )

    def cancel(self, user) -> None:
        """DRAFT / PENDING_HOD_APPROVAL / PENDING_ALLOTMENT / ALTERNATIVE_PROPOSED / QUERY_RAISED → CANCELLED"""
        cancellable = {
            self.Status.DRAFT,
            self.Status.PENDING_HOD_APPROVAL,
            self.Status.PENDING_ALLOTMENT,
            self.Status.ALTERNATIVE_PROPOSED,
            self.Status.QUERY_RAISED,
        }
        if self.status not in cancellable:
            raise ValueError(
                f"Cannot cancel a booking in status '{self.status}'. "
                f"Cancellable statuses: {sorted(cancellable)}"
            )
        if self.requestor_id != user.pk and not (user.is_superuser or user.is_staff or user.role == "ADMIN"):
            raise PermissionError("Only the requestor can cancel this booking.")

        prev_status = self.status
        self.status = self.Status.CANCELLED
        self.save(update_fields=["status", "updated_at"])

        self._log_history(user, "CANCEL", "Booking cancelled by requestor.", prev_status, self.status)

    # ── Properties ────────────────────────────────────────────────────────────

    @property
    def total_guests(self) -> int:
        return self.num_guests_male + self.num_guests_female

    @property
    def is_cancellable(self) -> bool:
        return self.status in {
            self.Status.DRAFT,
            self.Status.PENDING_HOD_APPROVAL,
            self.Status.PENDING_ALLOTMENT,
            self.Status.ALTERNATIVE_PROPOSED,
            self.Status.QUERY_RAISED,
        }

    @property
    def is_editable(self) -> bool:
        return self.status == self.Status.DRAFT

    @property
    def requires_form_c(self) -> bool:
        return self.is_foreign_guest


class Guest(TimeStampedModel):
    """An individual guest associated with a BookingRequest."""

    class Gender(models.TextChoices):
        MALE = "M", "Male"
        FEMALE = "F", "Female"
        OTHER = "O", "Other / Prefer not to say"

    class GuestType(models.TextChoices):
        DOMESTIC = "DOMESTIC", "Domestic"
        FOREIGN = "FOREIGN", "Foreign"

    booking = models.ForeignKey(
        BookingRequest,
        on_delete=models.CASCADE,
        related_name="guests",
    )
    name = models.CharField(max_length=150)
    mobile = models.CharField(max_length=15, blank=True)
    gender = models.CharField(max_length=1, choices=Gender.choices)
    email = models.EmailField(blank=True)
    guest_type = models.CharField(
        max_length=10,
        choices=GuestType.choices,
        default=GuestType.DOMESTIC,
    )
    check_in = models.DateField()
    check_out = models.DateField()
    disability_needs = models.TextField(
        blank=True,
        help_text="Accessibility or disability accommodation requirements.",
    )

    class Meta:
        ordering = ["name"]
        verbose_name = "Guest"
        verbose_name_plural = "Guests"

    def __str__(self) -> str:
        return f"{self.name} ({self.get_guest_type_display()}) → {self.booking}"

    def clean(self):
        from django.core.exceptions import ValidationError
        if self.check_in and self.check_out and self.check_out <= self.check_in:
            raise ValidationError({"check_out": "Check-out date must be after check-in date."})


class AlternateContact(TimeStampedModel):
    """Backup contact person for a booking."""

    booking = models.ForeignKey(
        BookingRequest,
        on_delete=models.CASCADE,
        related_name="alternate_contacts",
    )
    name = models.CharField(max_length=150)
    mobile = models.CharField(max_length=15)
    email = models.EmailField(blank=True)

    class Meta:
        ordering = ["id"]
        verbose_name = "Alternate Contact"
        verbose_name_plural = "Alternate Contacts"

    def __str__(self) -> str:
        return f"{self.name} ({self.mobile})"


class ApprovalHistory(TimeStampedModel):
    """Audit trail record for every workflow action and status transition."""

    booking = models.ForeignKey(
        BookingRequest,
        on_delete=models.CASCADE,
        related_name="approval_history",
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
    )
    user_name = models.CharField(max_length=150, blank=True)
    role = models.CharField(max_length=50)
    action = models.CharField(max_length=50)
    comments = models.TextField(blank=True)
    previous_status = models.CharField(max_length=50)
    new_status = models.CharField(max_length=50)

    class Meta:
        ordering = ["created_at"]
        verbose_name = "Approval History"
        verbose_name_plural = "Approval Histories"

    def __str__(self) -> str:
        return f"{self.booking} | {self.action} by {self.user_name} ({self.role}) at {self.created_at}"


class NotificationLog(TimeStampedModel):
    """In-app workflow event notification log."""

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="notifications",
    )
    booking = models.ForeignKey(
        BookingRequest,
        on_delete=models.CASCADE,
        related_name="notifications",
        null=True,
        blank=True,
    )
    title = models.CharField(max_length=200)
    message = models.TextField()
    is_read = models.BooleanField(default=False)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Notification Log"
        verbose_name_plural = "Notification Logs"

    def __str__(self) -> str:
        return f"Notification to {self.user.username}: {self.title}"
