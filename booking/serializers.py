"""
booking/serializers.py
-----------------------
DRF serializers for the booking module.

Serializers
-----------
AlternateContactSerializer — nested write for alternate contacts (max 4)
GuestSerializer            — nested write for individual guests
ApprovalHistorySerializer  — nested read for approval audit history timeline
NotificationLogSerializer  — notifications list for workflow events
BookingRequestSerializer   — full create/update with nested writes + validation
BookingRequestListSerializer — lightweight for list views (no nested details)
"""

from rest_framework import serializers

from booking.models import AlternateContact, ApprovalHistory, BookingRequest, Guest, NotificationLog


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


class ApprovalHistorySerializer(serializers.ModelSerializer):
    class Meta:
        model = ApprovalHistory
        fields = [
            "id",
            "user",
            "user_name",
            "role",
            "action",
            "comments",
            "previous_status",
            "new_status",
            "created_at",
        ]


class NotificationLogSerializer(serializers.ModelSerializer):
    class Meta:
        model = NotificationLog
        fields = ["id", "booking", "title", "message", "is_read", "created_at"]


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
    Full serializer with nested guests, alternate contacts, and approval history.
    """

    guests = GuestSerializer(many=True, required=False, default=list)
    alternate_contacts = AlternateContactSerializer(many=True, required=False, default=list)
    approval_history = ApprovalHistorySerializer(many=True, read_only=True)

    requestor_name = serializers.SerializerMethodField()
    requestor_email = serializers.SerializerMethodField()
    requestor_department = serializers.SerializerMethodField()
    requestor_campus = serializers.SerializerMethodField()
    status_display = serializers.CharField(source="get_status_display", read_only=True)

    allotted_room_number = serializers.SerializerMethodField()
    allotted_guest_house_name = serializers.SerializerMethodField()
    proposed_room_number = serializers.SerializerMethodField()
    proposed_guest_house_name = serializers.SerializerMethodField()

    class Meta:
        model = BookingRequest
        fields = [
            "id",
            "booking_id",
            "status",
            "status_display",
            "requestor",
            "requestor_name",
            "requestor_email",
            "requestor_department",
            "requestor_campus",
            "mobile_number",
            "is_faculty_incharge",
            "incharge_name",
            "incharge_email",
            "incharge_mobile",
            "campus_id",
            "campus_name",
            "purpose_of_booking",
            "event_id",
            "event_name",
            "event_date",
            "event_type",
            "num_guests_male",
            "num_guests_female",
            "num_rooms_required",
            "is_foreign_guest",
            "preferred_guest_house_id",
            "preferred_guest_house_name",
            "room_configuration",
            "special_requests",
            "allotted_room",
            "allotted_room_number",
            "allotted_guest_house",
            "allotted_guest_house_name",
            "proposed_room",
            "proposed_room_number",
            "proposed_guest_house",
            "proposed_guest_house_name",
            "proposed_note",
            "query_text",
            "query_stage",
            "query_response",
            "hold_reason",
            "food_arrangement",
            "travel_arrangement",
            "local_transport_arrangement",
            "payment_arrangement",
            "room_sharing_grouping",
            "rejection_reason",
            "rejection_stage",
            "guests",
            "alternate_contacts",
            "approval_history",
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
            "allotted_room",
            "allotted_room_number",
            "allotted_guest_house",
            "allotted_guest_house_name",
            "proposed_room",
            "proposed_room_number",
            "proposed_guest_house",
            "proposed_guest_house_name",
            "proposed_note",
            "query_text",
            "query_stage",
            "query_response",
            "hold_reason",
            "rejection_reason",
            "rejection_stage",
            "approval_history",
            "created_at",
            "updated_at",
        ]

    def get_requestor_name(self, obj) -> str:
        return obj.requestor.get_full_name() or obj.requestor.username

    def get_requestor_email(self, obj) -> str:
        return obj.requestor.email

    def get_requestor_department(self, obj) -> str:
        return obj.requestor.department

    def get_requestor_campus(self, obj) -> str:
        return obj.requestor.campus

    def get_allotted_room_number(self, obj) -> str:
        return obj.allotted_room.room_number if obj.allotted_room else ""

    def get_allotted_guest_house_name(self, obj) -> str:
        return obj.allotted_guest_house.name if obj.allotted_guest_house else ""

    def get_proposed_room_number(self, obj) -> str:
        return obj.proposed_room.room_number if obj.proposed_room else ""

    def get_proposed_guest_house_name(self, obj) -> str:
        return obj.proposed_guest_house.name if obj.proposed_guest_house else ""

    def validate_alternate_contacts(self, value):
        if len(value) > 4:
            raise serializers.ValidationError(
                "Maximum 4 alternate contacts are allowed per booking."
            )
        return value

    def validate(self, data):
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

    def create(self, validated_data):
        guests_data = validated_data.pop("guests", [])
        contacts_data = validated_data.pop("alternate_contacts", [])

        validated_data["requestor"] = self.context["request"].user

        booking = BookingRequest.objects.create(**validated_data)

        for guest_data in guests_data:
            Guest.objects.create(booking=booking, **guest_data)

        for contact_data in contacts_data:
            AlternateContact.objects.create(booking=booking, **contact_data)

        return booking

    def update(self, instance, validated_data):
        if instance.status != BookingRequest.Status.DRAFT:
            raise serializers.ValidationError(
                "Only bookings in DRAFT status can be edited."
            )

        guests_data = validated_data.pop("guests", None)
        contacts_data = validated_data.pop("alternate_contacts", None)

        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()

        if guests_data is not None:
            instance.guests.all().delete()
            for guest_data in guests_data:
                Guest.objects.create(booking=instance, **guest_data)

        if contacts_data is not None:
            instance.alternate_contacts.all().delete()
            for contact_data in contacts_data:
                AlternateContact.objects.create(booking=instance, **contact_data)

        return instance
