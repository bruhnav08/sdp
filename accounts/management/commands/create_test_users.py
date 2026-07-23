"""
Management command to create all HSRS test users in one shot.
Run:  python manage.py create_test_users
"""

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand

User = get_user_model()

TEST_USERS = [
    {
        "username": "admin",
        "password": "Admin@1234",
        "first_name": "System",
        "last_name": "Admin",
        "email": "admin@hsrs.edu",
        "role": "ADMIN",
        "is_staff": True,
        "is_superuser": True,
        "department": "IT",
        "campus": "Main Campus",
        "mobile_number": "9000000001",
    },
    {
        "username": "requestor1",
        "password": "Pass@1234",
        "first_name": "Rahul",
        "last_name": "Sharma",
        "email": "rahul.sharma@hsrs.edu",
        "role": "REQUESTOR",
        "department": "Computer Science",
        "campus": "Main Campus",
        "mobile_number": "9000000002",
    },
    {
        "username": "faculty1",
        "password": "Pass@1234",
        "first_name": "Priya",
        "last_name": "Verma",
        "email": "priya.verma@hsrs.edu",
        "role": "FACULTY_INCHARGE",
        "department": "Mechanical Engineering",
        "campus": "Main Campus",
        "mobile_number": "9000000003",
    },
    {
        "username": "hod1",
        "password": "Pass@1234",
        "first_name": "Dr. Arun",
        "last_name": "Mehta",
        "email": "arun.mehta@hsrs.edu",
        "role": "HOD_DIRECTOR",
        "department": "Computer Science",
        "campus": "Main Campus",
        "mobile_number": "9000000004",
    },
    {
        "username": "ghteam1",
        "password": "Pass@1234",
        "first_name": "Sunita",
        "last_name": "Patel",
        "email": "sunita.patel@hsrs.edu",
        "role": "GUEST_HOUSE_TEAM",
        "department": "Guest House Administration",
        "campus": "Main Campus",
        "mobile_number": "9000000005",
    },
    {
        "username": "mgmt1",
        "password": "Pass@1234",
        "first_name": "Prof. Ramesh",
        "last_name": "Iyer",
        "email": "ramesh.iyer@hsrs.edu",
        "role": "MANAGEMENT",
        "department": "Administration",
        "campus": "Main Campus",
        "mobile_number": "9000000006",
    },
]


class Command(BaseCommand):
    help = "Create HSRS test users for all roles (dev/demo only)"

    def handle(self, *args, **options):
        created = 0
        skipped = 0
        for data in TEST_USERS:
            username = data.pop("username")
            password = data.pop("password")
            if User.objects.filter(username=username).exists():
                self.stdout.write(self.style.WARNING(f"  SKIP  {username} (already exists)"))
                skipped += 1
                data["username"] = username  # restore for next iteration
                data["password"] = password
                continue
            user = User.objects.create_user(username=username, password=password, **data)
            self.stdout.write(self.style.SUCCESS(f"  CREATE {username} -> role={user.role}"))
            created += 1

        self.stdout.write("")
        self.stdout.write(self.style.SUCCESS(f"Done — {created} created, {skipped} skipped."))
        self.stdout.write("")
        self.stdout.write("Test credentials:")
        self.stdout.write("  Username      Password     Role")
        self.stdout.write("  admin         Admin@1234   ADMIN (superuser)")
        self.stdout.write("  requestor1    Pass@1234    REQUESTOR")
        self.stdout.write("  faculty1      Pass@1234    FACULTY_INCHARGE")
        self.stdout.write("  hod1          Pass@1234    HOD_DIRECTOR")
        self.stdout.write("  ghteam1       Pass@1234    GUEST_HOUSE_TEAM")
        self.stdout.write("  mgmt1         Pass@1234    MANAGEMENT")
