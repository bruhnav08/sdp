from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APIClient

from room_inventory.models import Amenity, Campus, GuestHouse, Room, RoomCategory

User = get_user_model()


class Module1RoomInventoryTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_superuser(
            username="adminuser", email="admin@example.com", password="password123"
        )
        self.client.force_login(self.user)

        self.api_client = APIClient()
        self.api_client.force_authenticate(user=self.user)

        self.campus = Campus.objects.create(name="Main Campus", location="Zone A")

        # Create Example Guest Houses
        self.ke_hall = GuestHouse.objects.create(name="KE Hall", campus=self.campus)
        self.dvk_house = GuestHouse.objects.create(name="DVK Guest House", campus=self.campus)

        # Amenities
        self.wifi = Amenity.objects.create(name="Wi-Fi", icon="📶")
        self.ac = Amenity.objects.create(name="AC", icon="❄️")
        self.bath = Amenity.objects.create(name="Attached Bathroom", icon="🚿")
        self.tv = Amenity.objects.create(name="TV", icon="📺")

        # Categories
        self.cat_single = RoomCategory.objects.create(
            name="Single", guest_house=self.ke_hall, default_capacity=1
        )
        self.cat_king = RoomCategory.objects.create(
            name="Double King", guest_house=self.ke_hall, default_capacity=2
        )

    def test_guesthouse_crud(self):
        """Test guest house creation, editing, and deletion."""
        response = self.client.get(reverse("inventory:guesthouse-list"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "KE Hall")
        self.assertContains(response, "DVK Guest House")

        # Create new Guest House
        response = self.client.post(
            reverse("inventory:guesthouse-create"),
            {"name": "Jonas Hall", "contact_number": "1234567890", "is_active": True},
        )
        self.assertEqual(response.status_code, 302)
        self.assertTrue(GuestHouse.objects.filter(name="Jonas Hall").exists())

        # Edit Guest House
        gh = GuestHouse.objects.get(name="Jonas Hall")
        response = self.client.post(
            reverse("inventory:guesthouse-edit", kwargs={"pk": gh.pk}),
            {"name": "Jonas Executive Hall", "contact_number": "9999999999", "is_active": True},
        )
        self.assertEqual(response.status_code, 302)
        gh.refresh_from_db()
        self.assertEqual(gh.name, "Jonas Executive Hall")

    def test_room_category_association(self):
        """Test creating and associating room category with a guest house."""
        response = self.client.post(
            reverse("inventory:category-create"),
            {
                "name": "Double Queen",
                "guest_house": self.dvk_house.pk,
                "default_capacity": 2,
                "is_active": True,
            },
        )
        self.assertEqual(response.status_code, 302)
        cat = RoomCategory.objects.get(name="Double Queen")
        self.assertEqual(cat.guest_house, self.dvk_house)

    def test_room_creation_and_amenities(self):
        """Test creating a room with floor, capacity, status, and amenities."""
        room = Room.objects.create(
            room_number="101",
            floor="1",
            capacity=2,
            guest_house=self.ke_hall,
            room_category=self.cat_single,
            status=Room.Status.VACANT_CLEAN,
        )
        room.amenities.add(self.wifi, self.ac, self.bath, self.tv)

        self.assertEqual(room.amenities.count(), 4)
        self.assertTrue(room.is_available_for_booking)

    def test_under_maintenance_not_available(self):
        """Verify rooms marked as Under Maintenance are NOT available for booking."""
        room_avail = Room.objects.create(
            room_number="102",
            floor="1",
            capacity=2,
            guest_house=self.ke_hall,
            status=Room.Status.VACANT_CLEAN,
        )
        room_maint = Room.objects.create(
            room_number="103",
            floor="1",
            capacity=2,
            guest_house=self.ke_hall,
            status=Room.Status.UNDER_MAINTENANCE,
        )
        room_blocked = Room.objects.create(
            room_number="104",
            floor="1",
            capacity=2,
            guest_house=self.ke_hall,
            status=Room.Status.BLOCKED,
        )

        self.assertTrue(room_avail.is_available_for_booking)
        self.assertFalse(room_maint.is_available_for_booking)
        self.assertFalse(room_blocked.is_available_for_booking)

        # Check API endpoint
        url = reverse("room_inventory:room-availability")
        response = self.api_client.get(f"{url}?guest_house={self.ke_hall.pk}")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["available_rooms"], 1)
        self.assertEqual(data["under_maintenance_rooms"], 1)
        self.assertEqual(data["blocked_rooms"], 1)

    def test_rbac_permissions_for_roles(self):
        """Verify role-based access control for room inventory endpoints."""
        req_user = User.objects.create_user(username="req_user", password="password123", role=User.Role.REQUESTOR)
        hod_user = User.objects.create_user(username="hod_user", password="password123", role=User.Role.HOD_DIRECTOR)
        gh_user = User.objects.create_user(username="gh_user", password="password123", role=User.Role.GUEST_HOUSE_TEAM)

        # 1. Requestor is blocked from room inventory views
        self.client.force_login(req_user)
        res = self.client.get(reverse("inventory:guesthouse-list"))
        self.assertEqual(res.status_code, 403)
        res_create = self.client.get(reverse("inventory:guesthouse-create"))
        self.assertEqual(res_create.status_code, 403)

        # 2. HOD is blocked from room inventory views
        self.client.force_login(hod_user)
        res = self.client.get(reverse("inventory:guesthouse-list"))
        self.assertEqual(res.status_code, 403)

        # 3. Guest House Team has operational read-only view of list, but blocked from creation
        self.client.force_login(gh_user)
        res = self.client.get(reverse("inventory:guesthouse-list"))
        self.assertEqual(res.status_code, 200)
        res_create = self.client.get(reverse("inventory:guesthouse-create"))
        self.assertEqual(res_create.status_code, 403)

        # 4. Admin has full access
        self.client.force_login(self.user)
        res = self.client.get(reverse("inventory:guesthouse-list"))
        self.assertEqual(res.status_code, 200)
        res_create = self.client.get(reverse("inventory:guesthouse-create"))
        self.assertEqual(res_create.status_code, 200)

    def test_room_status_synchronization(self):
        """Verify dynamic status of Room shifts to RESERVED/BOOKED and back based on booking state and dates."""
        from django.utils import timezone
        from booking.models import BookingRequest, Guest
        
        # Create a room instance
        room = Room.objects.create(
            room_number="999",
            floor="1",
            capacity=1,
            guest_house=self.ke_hall,
            room_category=self.cat_single,
            status=Room.Status.VACANT_CLEAN,
        )
        
        self.assertEqual(room.dynamic_status, "VACANT_CLEAN")

        # Create requestor and booking
        req_user = User.objects.create_user(username="req_test_sync", password="password123", role=User.Role.REQUESTOR)
        booking = BookingRequest.objects.create(
            requestor=req_user,
            mobile_number="9876543210",
            is_faculty_incharge=True,
            purpose_of_booking="Board Meeting",
        )
        # Create guest to set dates
        today = timezone.localdate()
        tomorrow = today + timezone.timedelta(days=1)
        Guest.objects.create(
            booking=booking,
            name="Alice",
            gender="F",
            check_in=today,
            check_out=tomorrow,
        )
        
        booking.submit(req_user)
        self.assertEqual(room.dynamic_status, "VACANT_CLEAN")

        # Allot room to booking
        booking.approve_by_hod(self.user)
        booking.allot_room(self.user, room=room)
        
        # Verify dynamic status is RESERVED (Allotted, pending Mgmt approval)
        self.assertEqual(room.dynamic_status, "RESERVED")

        # Confirm booking
        booking.approve_by_management(self.user)
        
        # Verify dynamic status is BOOKED
        self.assertEqual(room.dynamic_status, "BOOKED")

        # Revert to vacant clean on cancel
        booking.status = BookingRequest.Status.CANCELLED
        booking.save()
        self.assertEqual(room.dynamic_status, "VACANT_CLEAN")


