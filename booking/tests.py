from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APIClient

from booking.models import ApprovalHistory, BookingRequest
from room_inventory.models import Campus, GuestHouse, Room, RoomCategory

User = get_user_model()


class Sprint1ApprovalWorkflowTest(TestCase):
    def setUp(self):
        # Create users for each role
        self.requestor = User.objects.create_user(
            username="requestor_user", password="password123", role=User.Role.REQUESTOR, department="CS"
        )
        self.hod = User.objects.create_user(
            username="hod_user", password="password123", role=User.Role.HOD_DIRECTOR, department="CS"
        )
        self.gh_team = User.objects.create_user(
            username="gh_user", password="password123", role=User.Role.GUEST_HOUSE_TEAM
        )
        self.mgmt = User.objects.create_user(
            username="mgmt_user", password="password123", role=User.Role.MANAGEMENT
        )
        self.admin = User.objects.create_superuser(
            username="admin_user", email="admin@example.com", password="password123"
        )

        # Create room inventory fixtures
        self.campus = Campus.objects.create(name="Main Campus")
        self.gh1 = GuestHouse.objects.create(name="KE Hall", campus=self.campus)
        self.gh2 = GuestHouse.objects.create(name="DVK Guest House", campus=self.campus)
        self.category = RoomCategory.objects.create(name="Single", guest_house=self.gh1, default_capacity=1)

        self.room1 = Room.objects.create(
            room_number="101", guest_house=self.gh1, room_category=self.category, capacity=1, status=Room.Status.VACANT_CLEAN
        )
        self.room2 = Room.objects.create(
            room_number="202", guest_house=self.gh2, room_category=self.category, capacity=1, status=Room.Status.VACANT_CLEAN
        )

        self.api_client = APIClient()

    def test_full_happy_path_approval_workflow(self):
        """
        Complete end-to-end workflow:
        Draft → Submitted → Pending HOD Approval → HOD Approved → Pending Room Allotment → Room Allotted → Pending Management Approval → Confirmed
        """
        # Step 1: Requestor creates booking draft
        self.client.force_login(self.requestor)
        booking = BookingRequest.objects.create(
            requestor=self.requestor,
            mobile_number="9876543210",
            is_faculty_incharge=True,
            campus_id=self.campus.pk,
            campus_name=self.campus.name,
            purpose_of_booking="International Conference",
            num_guests_male=1,
            num_guests_female=0,
            num_rooms_required=1,
            preferred_guest_house_id=self.gh1.pk,
            preferred_guest_house_name=self.gh1.name,
        )
        self.assertEqual(booking.status, BookingRequest.Status.DRAFT)

        # Step 2: Requestor submits booking request
        booking.submit(self.requestor)
        booking.refresh_from_db()
        self.assertEqual(booking.status, BookingRequest.Status.PENDING_HOD_APPROVAL)
        self.assertTrue(booking.booking_id.startswith("BK-"))

        # Step 3: HOD approves booking
        self.client.force_login(self.hod)
        res_hod = self.client.post(
            reverse("booking:hod-action", kwargs={"pk": booking.pk}),
            {"action_type": "approve", "comments": "Approved for department conference."},
        )
        self.assertEqual(res_hod.status_code, 302)
        booking.refresh_from_db()
        self.assertEqual(booking.status, BookingRequest.Status.PENDING_ALLOTMENT)
        self.assertEqual(booking.hod_approved_by, self.hod)

        # Step 4: Guest House Team allots room
        self.client.force_login(self.gh_team)
        res_allot = self.client.post(
            reverse("booking:allotment-action", kwargs={"pk": booking.pk}),
            {"action_type": "allot", "room_id": self.room1.pk, "comments": "Assigned Room 101 in KE Hall."},
        )
        self.assertEqual(res_allot.status_code, 302)
        booking.refresh_from_db()
        self.assertEqual(booking.status, BookingRequest.Status.PENDING_MANAGEMENT_APPROVAL)
        self.assertEqual(booking.allotted_room, self.room1)
        self.assertEqual(booking.allotted_guest_house, self.gh1)

        # Step 5: Management grants final approval
        self.client.force_login(self.mgmt)
        res_mgmt = self.client.post(
            reverse("booking:management-action", kwargs={"pk": booking.pk}),
            {"action_type": "approve", "comments": "Final management approval granted."},
        )
        self.assertEqual(res_mgmt.status_code, 302)
        booking.refresh_from_db()
        self.assertEqual(booking.status, BookingRequest.Status.CONFIRMED)
        self.assertEqual(booking.management_approved_by, self.mgmt)

        # Verify Approval Audit Trail Timeline
        history = booking.approval_history.all()
        actions = [h.action for h in history]
        self.assertIn("SUBMIT", actions)
        self.assertIn("HOD_APPROVE", actions)
        self.assertIn("ALLOT_ROOM", actions)
        self.assertIn("MGMT_APPROVE", actions)

    def test_hod_query_and_response_workflow(self):
        """Test HOD raising query and requestor submitting clarification response."""
        booking = BookingRequest.objects.create(
            requestor=self.requestor,
            mobile_number="9876543210",
            is_faculty_incharge=True,
            purpose_of_booking="Research Seminar",
        )
        booking.submit(self.requestor)

        # HOD raises query
        self.client.force_login(self.hod)
        self.client.post(
            reverse("booking:hod-action", kwargs={"pk": booking.pk}),
            {"action_type": "query", "comments": "Please clarify list of visiting delegates."},
        )
        booking.refresh_from_db()
        self.assertEqual(booking.status, BookingRequest.Status.QUERY_RAISED)
        self.assertEqual(booking.query_text, "Please clarify list of visiting delegates.")

        # Requestor responds to query
        self.client.force_login(self.requestor)
        self.client.post(
            reverse("booking:respond-query", kwargs={"pk": booking.pk}),
            {"response_text": "Visiting delegates are Prof. Smith and Dr. Jones."},
        )
        booking.refresh_from_db()
        self.assertEqual(booking.status, BookingRequest.Status.PENDING_HOD_APPROVAL)
        self.assertEqual(booking.query_response, "Visiting delegates are Prof. Smith and Dr. Jones.")

    def test_alternative_room_proposal_workflow(self):
        """Test GH Team proposing alternative room and requestor accepting."""
        booking = BookingRequest.objects.create(
            requestor=self.requestor,
            mobile_number="9876543210",
            is_faculty_incharge=True,
            purpose_of_booking="Guest Speaker",
        )
        booking.submit(self.requestor)
        booking.approve_by_hod(self.hod)

        # GH Team proposes alternative room
        self.client.force_login(self.gh_team)
        self.client.post(
            reverse("booking:allotment-action", kwargs={"pk": booking.pk}),
            {"action_type": "propose", "room_id": self.room2.pk, "comments": "KE Hall full, proposing DVK Guest House Room 202."},
        )
        booking.refresh_from_db()
        self.assertEqual(booking.status, BookingRequest.Status.ALTERNATIVE_PROPOSED)
        self.assertEqual(booking.proposed_room, self.room2)

        # Requestor accepts alternative
        self.client.force_login(self.requestor)
        self.client.post(
            reverse("booking:alternative-response", kwargs={"pk": booking.pk}),
            {"response_action": "accept"},
        )
        booking.refresh_from_db()
        self.assertEqual(booking.status, BookingRequest.Status.PENDING_MANAGEMENT_APPROVAL)
        self.assertEqual(booking.allotted_room, self.room2)

    def test_management_hold_and_rejection(self):
        """Test Management putting booking on hold and rejecting."""
        booking = BookingRequest.objects.create(
            requestor=self.requestor,
            mobile_number="9876543210",
            is_faculty_incharge=True,
            purpose_of_booking="Workshop",
        )
        booking.submit(self.requestor)
        booking.approve_by_hod(self.hod)
        booking.allot_room(self.gh_team, self.room1)

        # Management places on hold
        self.client.force_login(self.mgmt)
        self.client.post(
            reverse("booking:management-action", kwargs={"pk": booking.pk}),
            {"action_type": "hold", "comments": "Awaiting budget approval."},
        )
        booking.refresh_from_db()
        self.assertEqual(booking.status, BookingRequest.Status.ON_HOLD)
        self.assertEqual(booking.hold_reason, "Awaiting budget approval.")

        # Management rejects
        self.client.post(
            reverse("booking:management-action", kwargs={"pk": booking.pk}),
            {"action_type": "reject", "comments": "Budget allocation denied."},
        )
        booking.refresh_from_db()
        self.assertEqual(booking.status, BookingRequest.Status.REJECTED)
        self.assertEqual(booking.rejection_reason, "Budget allocation denied.")

    def test_role_permissions_and_unauthorized_blocking(self):
        """Verify role protection on approval dashboards and direct action URLs."""
        # Requestor cannot access HOD approvals or Management approvals
        self.client.force_login(self.requestor)
        self.assertEqual(self.client.get(reverse("booking:approvals")).status_code, 403)
        self.assertEqual(self.client.get(reverse("booking:allotment")).status_code, 403)
        self.assertEqual(self.client.get(reverse("booking:management-approvals")).status_code, 403)

        # HOD cannot access Room Allotment or Management Approvals
        self.client.force_login(self.hod)
        self.assertEqual(self.client.get(reverse("booking:approvals")).status_code, 200)
        self.assertEqual(self.client.get(reverse("booking:allotment")).status_code, 403)
        self.assertEqual(self.client.get(reverse("booking:management-approvals")).status_code, 403)

        # DRF API action protection
        booking = BookingRequest.objects.create(
            requestor=self.requestor,
            mobile_number="9876543210",
            is_faculty_incharge=True,
            purpose_of_booking="Test API Guards",
        )
        self.api_client.force_authenticate(user=self.requestor)
        res_submit = self.api_client.post(f"/api/bookings/{booking.pk}/submit/")
        self.assertEqual(res_submit.status_code, 200)
