from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APIClient

from housekeeping.models import RoomStatusHistory
from housekeeping.services import change_room_status
from room_inventory.models import Campus, GuestHouse, Room

User = get_user_model()


class HousekeepingModule2Test(TestCase):
    def setUp(self):
        self.staff_user = User.objects.create_user(
            username="staffuser", password="password123", role=User.Role.GUEST_HOUSE_TEAM
        )
        self.client.force_login(self.staff_user)

        self.api_client = APIClient()
        self.api_client.force_authenticate(user=self.staff_user)

        self.campus = Campus.objects.create(name="Main Campus")
        self.gh = GuestHouse.objects.create(name="KE Hall", campus=self.campus)

        self.room1 = Room.objects.create(
            room_number="101", guest_house=self.gh, status=Room.Status.VACANT_DIRTY
        )
        self.room2 = Room.objects.create(
            room_number="102", guest_house=self.gh, status=Room.Status.UNDER_MAINTENANCE
        )

    def test_workflow_vacant_dirty_to_cleaning_to_vacant_clean(self):
        """Test complete workflow: VACANT_DIRTY -> CLEANING_IN_PROGRESS -> VACANT_CLEAN."""
        # Step 1: Start cleaning
        h1 = change_room_status(self.room1, Room.Status.CLEANING_IN_PROGRESS, self.staff_user)
        self.room1.refresh_from_db()
        self.assertEqual(self.room1.status, Room.Status.CLEANING_IN_PROGRESS)
        self.assertEqual(h1.previous_status, Room.Status.VACANT_DIRTY)
        self.assertEqual(h1.new_status, Room.Status.CLEANING_IN_PROGRESS)
        self.assertEqual(h1.changed_by, self.staff_user)

        # Step 2: Mark Clean
        h2 = change_room_status(self.room1, Room.Status.VACANT_CLEAN, self.staff_user)
        self.room1.refresh_from_db()
        self.assertEqual(self.room1.status, Room.Status.VACANT_CLEAN)
        self.assertEqual(h2.previous_status, Room.Status.CLEANING_IN_PROGRESS)
        self.assertEqual(h2.new_status, Room.Status.VACANT_CLEAN)

        # Verify audit history log entries
        self.assertEqual(self.room1.status_history.count(), 2)

    def test_invalid_transition_duplicate_cleaning(self):
        """Room already marked as Cleaning In Progress should not start cleaning again."""
        change_room_status(self.room1, Room.Status.CLEANING_IN_PROGRESS, self.staff_user)
        self.room1.refresh_from_db()

        with self.assertRaises(ValidationError):
            change_room_status(self.room1, Room.Status.CLEANING_IN_PROGRESS, self.staff_user)

    def test_clear_maintenance_workflow(self):
        """Test under maintenance transition and clearing maintenance."""
        # Put room under maintenance
        change_room_status(self.room1, Room.Status.UNDER_MAINTENANCE, self.staff_user, remarks="Broken AC")
        self.room1.refresh_from_db()
        self.assertEqual(self.room1.status, Room.Status.UNDER_MAINTENANCE)

        # Clear maintenance to VACANT_DIRTY
        change_room_status(self.room1, Room.Status.VACANT_DIRTY, self.staff_user, remarks="AC Repaired")
        self.room1.refresh_from_db()
        self.assertEqual(self.room1.status, Room.Status.VACANT_DIRTY)

    def test_housekeeping_dashboard_view(self):
        """Test dashboard page loads with status counts and room rows."""
        url = reverse("housekeeping_ui:dashboard")
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "KE Hall")
        self.assertContains(response, "Room 101")
        self.assertContains(response, "Room 102")

    def test_room_history_view(self):
        """Test room-specific audit history view."""
        change_room_status(self.room1, Room.Status.CLEANING_IN_PROGRESS, self.staff_user, remarks="Morning shift")
        url = reverse("housekeeping_ui:room-history", kwargs={"pk": self.room1.pk})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "VACANT_DIRTY")
        self.assertContains(response, "CLEANING_IN_PROGRESS")
        self.assertContains(response, "Morning shift")

    def test_rest_api_room_status(self):
        """Test REST API endpoint GET /api/housekeeping/room-status/?room=<id>."""
        url = reverse("housekeeping:room-status")
        response = self.api_client.get(f"{url}?room={self.room1.pk}")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["room_id"], self.room1.pk)
        self.assertEqual(data["status"], Room.Status.VACANT_DIRTY)
        self.assertEqual(data["room_number"], "101")

    def test_housekeeping_rbac_permissions(self):
        """Verify Requestors and HODs cannot access housekeeping views/API, but GH Team and Admin can."""
        req_user = User.objects.create_user(username="req_user_hk", password="password123", role=User.Role.REQUESTOR)
        hod_user = User.objects.create_user(username="hod_user_hk", password="password123", role=User.Role.HOD_DIRECTOR)
        admin_user = User.objects.create_superuser(username="admin_user_hk", email="adminhk@example.com", password="password123")

        url = reverse("housekeeping_ui:dashboard")

        # 1. Requestor is blocked
        self.client.force_login(req_user)
        self.assertEqual(self.client.get(url).status_code, 403)

        # 2. HOD is blocked
        self.client.force_login(hod_user)
        self.assertEqual(self.client.get(url).status_code, 403)

        # 3. Guest House Team has access
        self.client.force_login(self.staff_user)
        self.assertEqual(self.client.get(url).status_code, 200)

        # 4. Admin has access
        self.client.force_login(admin_user)
        self.assertEqual(self.client.get(url).status_code, 200)

        # Check API protection
        api_url = reverse("housekeeping:room-status")
        api_client = APIClient()

        api_client.force_authenticate(user=req_user)
        self.assertEqual(api_client.get(f"{api_url}?room={self.room1.pk}").status_code, 403)

        api_client.force_authenticate(user=self.staff_user)
        self.assertEqual(api_client.get(f"{api_url}?room={self.room1.pk}").status_code, 200)

