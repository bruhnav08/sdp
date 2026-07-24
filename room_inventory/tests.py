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
