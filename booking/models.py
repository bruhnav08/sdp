"""
booking/models.py
-----------------
Core models for the Guest Room Booking module.

Models
------
BookingRequest  — the main booking entity with status-transition guards
Guest           — a guest associated with a BookingRequest (one-to-many)
AlternateContact — backup contact persons for a booking (up to 4)

Status lifecycle
----------------
DRAFT
  └─ submit()           → PENDING_HOD_APPROVAL
       └─ approve_by_hod()  → PENDING_ALLOTMENT
            └─ approve_allotment() → PENDING_MANAGEMENT_APPROVAL
                 └─ approve_by_management() → CONFIRMED
  Any approval state can go to REJECTED via reject()
  DRAFT or PENDING_HOD_APPROVAL can go to CANCELLED via cancel()

Integration note (loose coupling)
----------------------------------
campus_id, preferred_guest_house_id, and event_id are plain IntegerFields
(not ForeignKeys) so this app's migrations have zero dependency on the
room_inventory app.  Display names are denormalised into *_name CharField
companions.  Upgrade to ForeignKey after room_inventory integration.
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

    The full business lifecycle is encapsulated in the transition methods
    (submit, approve_by_hod, etc.).  Always call those methods — never
    set `.status` directly on a BookingRequest instance.
    """

    # ── Status choices ────────────────────────────────────────────────────────
    class Status(models.TextChoices):
        DRAFT = "DRAFT", "Draft"
        PENDING_HOD_APPROVAL = "PENDING_HOD_APPROVAL", "Pending HOD Approval"
        PENDING_ALLOTMENT = "PENDING_ALLOTMENT", "Pending Allotment"
        PENDING_MANAGEMENT_APPROVAL = "PENDING_MANAGEMENT_APPROVAL", "Pending Management Approval"
        CONFIRMED = "CONFIRMED", "Confirmed"
        REJECTED = "REJECTED", "Rejected"
        CANCELLED = "CANCELLED", "Cancelled"

    # States from which rejection is legal
    _REJECTABLE_STATUSES = frozenset([
        Status.PENDING_HOD_APPROVAL,
        Status.PENDING_ALLOTMENT,
        Status.PENDING_MANAGEMENT_APPROVAL,
    ])

    # ── Identity ──────────────────────────────────────────────────────────────
    booking_id = models.CharField(
        max_length=20,
        unique=True,
        blank=True,
        db_index=True,
        help_text="Auto-generated on submit.  Format: BK-YYYYMM-XXXX",
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

    # ── Campus & Event (loose-coupled — plain IDs, not ForeignKeys) ───────────
    # Upgrade to ForeignKey after room_inventory integration (one-line change
    # + new migration; no business-logic changes required).
    campus_id = models.PositiveIntegerField(
        null=True,
        blank=True,
        help_text="References room_inventory.Campus.pk (no FK constraint for now).",
    )
    campus_name = models.CharField(
        max_length=150,
        blank=True,
        help_text="Denormalised campus name for display without a JOIN.",
    )

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

    # ── Guest House (loose-coupled) ───────────────────────────────────────────
    preferred_guest_house_id = models.PositiveIntegerField(null=True, blank=True)
    preferred_guest_house_name = models.CharField(max_length=250, blank=True)
    room_configuration = models.CharField(
        max_length=100,
        blank=True,
        help_text="E.g. Single, Double, Suite.",
    )

    special_requests = models.TextField(blank=True)

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
    room_sharing_grouping = models.TextField(
        blank=True,
        help_text="Notes on how guests should be grouped for room sharing.",
    )

    # ── Rejection audit ───────────────────────────────────────────────────────
    rejection_reason = models.TextField(blank=True)
    rejected_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="rejected_bookings",
    )
    rejection_stage = models.CharField(
        max_length=35,
        blank=True,
        help_text="Status value at the time of rejection, for audit trail.",
    )

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

    # ── Helpers ───────────────────────────────────────────────────────────────

    @staticmethod
    def _generate_booking_id() -> str:
        """
        Generate a unique booking ID in the format BK-YYYYMM-XXXX.
        Retries on collision (astronomically rare but handled).
        """
        now = timezone.now()
        for _ in range(10):
            suffix = "".join(random.choices(string.digits, k=4))
            candidate = f"BK-{now.strftime('%Y%m')}-{suffix}"
            if not BookingRequest.objects.filter(booking_id=candidate).exists():
                return candidate
        raise RuntimeError("Could not generate a unique booking ID after 10 attempts.")

    def _assert_status(self, expected: str, action: str) -> None:
        if self.status != expected:
            raise ValueError(
                f"Cannot perform '{action}' on a booking in status "
                f"'{self.status}'. Expected: '{expected}'."
            )

    # ── Status transition guards ──────────────────────────────────────────────
    # ALL status changes must go through one of these methods.
    # Direct field assignment (booking.status = '...') is prohibited.

    def submit(self, user) -> None:
        """
        DRAFT → PENDING_HOD_APPROVAL
        Generates a unique booking_id. Only the requestor may submit.
        Call this from the booking submit view / API action.
        """
        self._assert_status(self.Status.DRAFT, "submit")
        if self.requestor_id != user.pk:
            raise PermissionError("Only the requestor can submit this booking.")
        self.booking_id = self._generate_booking_id()
        self.status = self.Status.PENDING_HOD_APPROVAL
        self.save(update_fields=["booking_id", "status", "updated_at"])

    def approve_by_hod(self, user) -> None:
        """
        PENDING_HOD_APPROVAL → PENDING_ALLOTMENT
        Called by an HOD/Director approver.
        """
        self._assert_status(self.Status.PENDING_HOD_APPROVAL, "approve_by_hod")
        self.status = self.Status.PENDING_ALLOTMENT
        self.save(update_fields=["status", "updated_at"])

    def approve_allotment(self, user) -> None:
        """
        PENDING_ALLOTMENT → PENDING_MANAGEMENT_APPROVAL
        Called by Guest House Team after assigning rooms.
        """
        self._assert_status(self.Status.PENDING_ALLOTMENT, "approve_allotment")
        self.status = self.Status.PENDING_MANAGEMENT_APPROVAL
        self.save(update_fields=["status", "updated_at"])

    def approve_by_management(self, user) -> None:
        """
        PENDING_MANAGEMENT_APPROVAL → CONFIRMED
        Final approval by Management.
        """
        self._assert_status(self.Status.PENDING_MANAGEMENT_APPROVAL, "approve_by_management")
        self.status = self.Status.CONFIRMED
        self.save(update_fields=["status", "updated_at"])

    def reject(self, user, reason: str = "") -> None:
        """
        Any approval state → REJECTED
        Records who rejected, the reason, and the stage at which it was rejected.
        """
        if self.status not in self._REJECTABLE_STATUSES:
            raise ValueError(
                f"Cannot reject a booking in status '{self.status}'. "
                f"Rejectable statuses: {sorted(self._REJECTABLE_STATUSES)}"
            )
        self.rejection_stage = self.status
        self.status = self.Status.REJECTED
        self.rejection_reason = reason
        self.rejected_by = user
        self.save(update_fields=[
            "status", "rejection_reason", "rejected_by",
            "rejection_stage", "updated_at",
        ])

    def cancel(self, user) -> None:
        """
        DRAFT or PENDING_HOD_APPROVAL → CANCELLED
        Only the requestor may cancel their own booking.
        """
        cancellable = {self.Status.DRAFT, self.Status.PENDING_HOD_APPROVAL}
        if self.status not in cancellable:
            raise ValueError(
                f"Cannot cancel a booking in status '{self.status}'. "
                f"Bookings can only be cancelled when DRAFT or PENDING_HOD_APPROVAL."
            )
        if self.requestor_id != user.pk:
            raise PermissionError("Only the requestor can cancel this booking.")
        self.status = self.Status.CANCELLED
        self.save(update_fields=["status", "updated_at"])

    # ── Properties ────────────────────────────────────────────────────────────

    @property
    def total_guests(self) -> int:
        return self.num_guests_male + self.num_guests_female

    @property
    def is_cancellable(self) -> bool:
        return self.status in {self.Status.DRAFT, self.Status.PENDING_HOD_APPROVAL}

    @property
    def is_editable(self) -> bool:
        """Only DRAFT bookings can be edited."""
        return self.status == self.Status.DRAFT

    @property
    def requires_form_c(self) -> bool:
        """Foreign guests require Form C (police registration)."""
        return self.is_foreign_guest


class Guest(TimeStampedModel):
    """
    An individual guest associated with a BookingRequest.
    Multiple guests can be added to a single booking.
    """

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
    """
    Backup contact person for a booking.
    A maximum of 4 alternate contacts is enforced in the serializer.
    """

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
