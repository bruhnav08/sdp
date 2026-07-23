"""
booking/serializers.py
-----------------------
DRF serializers for the booking module.

Serializers
-----------
AlternateContactSerializer — nested write for alternate contacts (max 4)
GuestSerializer            — nested write for individual guests
BookingRequestSerializer   — full create/update with nested writes + validation
BookingRequestListSerializer — lightweight for list views (no nested details)

Validation rules (server-side — never trust client-only validation)
-------------------------------------------------------------------
- purpose_of_booking is always mandatory
- If is_faculty_incharge is False: incharge_name and incharge_email are required
- Maximum 4 alternate contacts
- Guest check_out must be after check_in
- On submit action: all mandatory fields must be present (enforced in view)
"""

from rest_framework import serializers

from booking.models import AlternateContact, BookingRequest, Guest


class AlternateContactSerializer(serializers.ModelSerializer):
    class Meta:
        model = AlternateContact
        fields = ["id", "name", "mobile", "email"]
        extra_kwargs = {
            "name": {"required": True},
            "mobile": {"required": True},
        }


class GuestSerializer(serializers.ModelSerializer):
    class Meta:
        model = Guest
        fields = [
            "id",
            "name",
            "mobile",
            "gender",
            "email",
            "guest_type",
            "check_in",
            "check_out",
            "disability_needs",
        ]
        extra_kwargs = {
            "name": {"required": True},
            "gender": {"required": True},
            "check_in": {"required": True},
            "check_out": {"required": True},
        }

    def validate(self, data):
        check_in = data.get("check_in")
        check_out = data.get("check_out")
        if check_in and check_out and check_out <= check_in:
            raise serializers.ValidationError(
                {"check_out": "Check-out date must be after check-in date."}
            )
        return data


class BookingRequestListSerializer(serializers.ModelSerializer):
    """Lightweight serializer for list views — omits nested details."""

    requestor_name = serializers.SerializerMethodField()
    status_display = serializers.CharField(source="get_status_display", read_only=True)

    class Meta:
        model = BookingRequest
        fields = [
            "id",
            "booking_id",
            "status",
            "status_display",
            "requestor",
            "requestor_name",
            "campus_name",
            "event_name",
            "event_date",
            "num_rooms_required",
            "total_guests",
            "is_foreign_guest",
            "created_at",
            "updated_at",
        ]
        read_only_fields = fields

    def get_requestor_name(self, obj) -> str:
        return obj.requestor.get_full_name() or obj.requestor.username


class BookingRequestSerializer(serializers.ModelSerializer):
    """
    Full serializer with nested guests and alternate contacts.
    Supports both create (POST) and update (PATCH/PUT).
    Requestor is set automatically from request.user.
    """

    # Nested collections — writable
    guests = GuestSerializer(many=True, required=False, default=list)
    alternate_contacts = AlternateContactSerializer(many=True, required=False, default=list)

    # Read-only derived fields from the requestor
    requestor_name = serializers.SerializerMethodField()
    requestor_email = serializers.SerializerMethodField()
    requestor_department = serializers.SerializerMethodField()
    requestor_campus = serializers.SerializerMethodField()
    status_display = serializers.CharField(source="get_status_display", read_only=True)

    class Meta:
        model = BookingRequest
        fields = [
            # Identity
            "id",
            "booking_id",
            "status",
            "status_display",
            # Requestor (auto-populated)
            "requestor",
            "requestor_name",
            "requestor_email",
            "requestor_department",
            "requestor_campus",
            "mobile_number",
            # Faculty in-charge
            "is_faculty_incharge",
            "incharge_name",
            "incharge_email",
            "incharge_mobile",
            # Campus / Event
            "campus_id",
            "campus_name",
            "purpose_of_booking",
            "event_id",
            "event_name",
            "event_date",
            "event_type",
            # Guest counts
            "num_guests_male",
            "num_guests_female",
            "num_rooms_required",
            # Foreign guest
            "is_foreign_guest",
            # Guest house
            "preferred_guest_house_id",
            "preferred_guest_house_name",
            "room_configuration",
            "special_requests",
            # Arrangements
            "food_arrangement",
            "travel_arrangement",
            "local_transport_arrangement",
            "payment_arrangement",
            "room_sharing_grouping",
            # Rejection
            "rejection_reason",
            "rejection_stage",
            # Nested
            "guests",
            "alternate_contacts",
            # Timestamps
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "booking_id",
            "status",
            "status_display",
            "requestor",
            "requestor_name",
            "requestor_email",
            "requestor_department",
            "requestor_campus",
            "rejection_reason",
            "rejection_stage",
            "created_at",
            "updated_at",
        ]

    # ── Read-only derived getters ─────────────────────────────────────────────

    def get_requestor_name(self, obj) -> str:
        return obj.requestor.get_full_name() or obj.requestor.username

    def get_requestor_email(self, obj) -> str:
        return obj.requestor.email

    def get_requestor_department(self, obj) -> str:
        return obj.requestor.department

    def get_requestor_campus(self, obj) -> str:
        return obj.requestor.campus

    # ── Validation ────────────────────────────────────────────────────────────

    def validate_alternate_contacts(self, value):
        if len(value) > 4:
            raise serializers.ValidationError(
                "Maximum 4 alternate contacts are allowed per booking."
            )
        return value

    def validate(self, data):
        """
        Cross-field validation.
        - If the requestor is NOT the faculty in-charge, incharge details are required.
        - purpose_of_booking is always required (also enforced at model level).
        """
        is_faculty_incharge = data.get(
            "is_faculty_incharge",
            getattr(self.instance, "is_faculty_incharge", False),
        )

        if not is_faculty_incharge:
            if not data.get("incharge_name", getattr(self.instance, "incharge_name", "")):
                raise serializers.ValidationError(
                    {"incharge_name": "Required when you are not the Faculty In-Charge."}
                )
            if not data.get("incharge_email", getattr(self.instance, "incharge_email", "")):
                raise serializers.ValidationError(
                    {"incharge_email": "Required when you are not the Faculty In-Charge."}
                )

        return data

    # ── Create with nested writes ─────────────────────────────────────────────

    def create(self, validated_data):
        guests_data = validated_data.pop("guests", [])
        contacts_data = validated_data.pop("alternate_contacts", [])

        # Requestor is always the logged-in user
        validated_data["requestor"] = self.context["request"].user

        booking = BookingRequest.objects.create(**validated_data)

        for guest_data in guests_data:
            Guest.objects.create(booking=booking, **guest_data)

        for contact_data in contacts_data:
            AlternateContact.objects.create(booking=booking, **contact_data)

        return booking

    # ── Update with nested writes ─────────────────────────────────────────────

    def update(self, instance, validated_data):
        # Only DRAFT bookings may be updated
        if instance.status != BookingRequest.Status.DRAFT:
            raise serializers.ValidationError(
                "Only bookings in DRAFT status can be edited."
            )

        guests_data = validated_data.pop("guests", None)
        contacts_data = validated_data.pop("alternate_contacts", None)

        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()

        # Full replacement of nested collections when provided
        if guests_data is not None:
            instance.guests.all().delete()
            for guest_data in guests_data:
                Guest.objects.create(booking=instance, **guest_data)

        if contacts_data is not None:
            instance.alternate_contacts.all().delete()
            for contact_data in contacts_data:
                AlternateContact.objects.create(booking=instance, **contact_data)

        return instance
