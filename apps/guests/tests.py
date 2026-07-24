"""
Tests for guest functionality — both the Guest model (hotel guests) and
Staff accounts with role="guest" (public users of the web app).

These tests cover:
  - Creating a Guest model instance
  - Creating a Staff user with role="guest" via the registration API
  - Guest login
  - Access control: guests cannot access staff-only endpoints
  - Guest data scoping via reservations
"""
import json

from django.test import TestCase
from rest_framework.test import APIClient

from apps.accounts.models import Staff
from apps.guests.models import Guest
from apps.hotels.models import Hotel
from apps.reservations.models import Reservation
from apps.rooms.models import Room, RoomType


class GuestModelTests(TestCase):
    """Tests for creating and querying Guest model instances."""

    def test_create_guest(self):
        guest = Guest.objects.create(
            guest_name="Test Guest",
            guest_email="testguest@example.com",
            guest_phone="+233-500-000-001",
            id_number="GHA-123456789-0",
            nationality="Ghanaian",
        )
        self.assertEqual(guest.guest_name, "Test Guest")
        self.assertEqual(guest.guest_email, "testguest@example.com")
        self.assertEqual(str(guest), "Test Guest (testguest@example.com)")

    def test_guest_email_unique_constraint(self):
        Guest.objects.create(
            guest_name="First Guest",
            guest_email="dupe@example.com",
            guest_phone="+233-500-000-001",
        )
        with self.assertRaises(Exception):
            Guest.objects.create(
                guest_name="Second Guest",
                guest_email="dupe@example.com",
                guest_phone="+233-500-000-002",
            )


class GuestStaffAccountTests(TestCase):
    """
    Tests for creating a public user account (Staff with role="guest")
    via the API registration endpoint and verifying access controls.
    """

    def setUp(self):
        self.client = APIClient()

    def test_register_guest_user(self):
        """A public user can register via the API."""
        response = self.client.post(
            "/api/auth/register/",
            {
                "full_name": "Jane Doe",
                "email": "jane.doe@example.com",
                "password": "SecurePass123!",
                "staff_phone": "+233-500-000-001",
            },
            format="json",
        )
        self.assertEqual(response.status_code, 201)
        data = response.json()
        self.assertEqual(data["user"]["email"], "jane.doe@example.com")
        self.assertEqual(data["user"]["role"], "guest")
        self.assertTrue(Staff.objects.filter(email="jane.doe@example.com", role="guest").exists())

    def test_register_duplicate_email_returns_409(self):
        """Registering with an existing email returns 409."""
        Staff.objects.create_user(
            username="existing@example.com",
            email="existing@example.com",
            password="SomePass123!",
            staff_name="Existing User",
            staff_phone="+233-500-000-001",
            role="guest",
        )
        response = self.client.post(
            "/api/auth/register/",
            {
                "full_name": "Duplicate",
                "email": "existing@example.com",
                "password": "SecurePass123!",
                "staff_phone": "+233-500-000-002",
            },
            format="json",
        )
        self.assertEqual(response.status_code, 409)
        self.assertIn("already exists", response.json().get("detail", ""))

    def test_register_missing_fields_returns_400(self):
        """Registration without required fields returns 400."""
        response = self.client.post(
            "/api/auth/register/",
            {"full_name": "Incomplete"},
            format="json",
        )
        self.assertEqual(response.status_code, 400)

    def test_guest_can_login(self):
        """A registered guest user can log in."""
        Staff.objects.create_user(
            username="guestlogin@example.com",
            email="guestlogin@example.com",
            password="MyPassword123",
            staff_name="Guest Login",
            staff_phone="+233-500-000-001",
            role="guest",
        )
        response = self.client.post(
            "/api/auth/login/",
            {"email": "guestlogin@example.com", "password": "MyPassword123"},
            format="json",
        )
        self.assertEqual(response.status_code, 200)

    def test_guest_cannot_login_as_staff(self):
        """A guest user is blocked from staff login."""
        Staff.objects.create_user(
            username="gueststaff@example.com",
            email="gueststaff@example.com",
            password="MyPassword123",
            staff_name="Guest Staff",
            staff_phone="+233-500-000-001",
            role="guest",
        )
        response = self.client.post(
            "/api/auth/login/",
            {"email": "gueststaff@example.com", "password": "MyPassword123", "staff_login": True},
            format="json",
        )
        self.assertEqual(response.status_code, 403)
        self.assertIn("not a staff account", response.json().get("detail", "").lower())

    def test_guest_cannot_access_staff_dashboard(self):
        """Guest users are redirected away from staff dashboards."""
        guest = Staff.objects.create_user(
            username="guestdashboard@example.com",
            email="guestdashboard@example.com",
            password="MyPassword123",
            staff_name="Guest Dashboard",
            staff_phone="+233-500-000-001",
            role="guest",
        )
        self.client.force_login(guest)
        response = self.client.get("/manager/")
        self.assertEqual(response.status_code, 302)  # redirected to guest home
        response = self.client.get("/receptionist/")
        self.assertEqual(response.status_code, 302)

    def test_guest_home_redirects_staff_to_dashboard(self):
        """Staff users (admin, receptionist, etc.) are redirected to their dashboards."""
        for role, dashboard_path in [
            ("admin", "/manager/"),
            ("manager", "/manager/"),
            ("receptionist", "/receptionist/"),
            ("accountant", "/accountant/"),
            ("housekeeping", "/housekeeping/"),
        ]:
            staff_user = Staff.objects.create_user(
                username=f"{role}@stayhub.local",
                email=f"{role}@stayhub.local",
                password="testpass123",
                staff_name=f"{role.title()} User",
                staff_phone="+233-555-000-001",
                role=role,
            )
            self.client.force_login(staff_user)
            response = self.client.get("/home/")
            self.assertRedirects(
                response, dashboard_path,
                msg_prefix=f"Role '{role}' should redirect to '{dashboard_path}'",
            )
            self.client.logout()

    def test_guest_home_shows_for_guest_role(self):
        """Guest users see the guest home page, not a redirect."""
        guest = Staff.objects.create_user(
            username="guesthome@example.com",
            email="guesthome@example.com",
            password="testpass123",
            staff_name="Guest Home Test",
            staff_phone="+233-555-000-001",
            role="guest",
        )
        self.client.force_login(guest)
        response = self.client.get("/home/")
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "frontend/guest_home.html")


class GuestModelAPITests(TestCase):
    """Tests for the Guest model API endpoints (staff-facing guest records)."""

    @classmethod
    def setUpTestData(cls):
        cls.hotel = Hotel.objects.create(
            hotel_name="Test Hotel",
            hotel_email="test@stayhub.local",
            hotel_address="123 Test St",
            hotel_phone="+233-555-000-001",
        )
        cls.other_hotel = Hotel.objects.create(
            hotel_name="Other Hotel",
            hotel_email="other@stayhub.local",
            hotel_address="456 Other St",
            hotel_phone="+233-555-000-002",
        )
        cls.receptionist = Staff.objects.create_user(
            username="receptest@stayhub.local",
            email="receptest@stayhub.local",
            password="testpass123",
            staff_name="Recep Test",
            staff_phone="+233-555-000-003",
            role="receptionist",
            hotel=cls.hotel,
        )
        cls.manager = Staff.objects.create_user(
            username="mgrtest@stayhub.local",
            email="mgrtest@stayhub.local",
            password="testpass123",
            staff_name="Manager Test",
            staff_phone="+233-555-000-004",
            role="manager",
        )
        cls.guest_a = Guest.objects.create(
            guest_name="Guest Alpha",
            guest_email="alpha@test.com",
            guest_phone="+233-500-000-001",
            id_number="GHA-111111111-1",
            nationality="Ghanaian",
        )
        cls.guest_b = Guest.objects.create(
            guest_name="Guest Beta",
            guest_email="beta@test.com",
            guest_phone="+233-500-000-002",
            id_number="GHA-222222222-2",
            nationality="Ghanaian",
        )
        room_type = RoomType.objects.create(
            hotel=cls.hotel, type_name="Standard", price_per_night=100,
        )
        room = Room.objects.create(
            hotel=cls.hotel, room_type=room_type,
            room_number="101", price_per_night=100,
        )
        cls.reservation_a = Reservation.objects.create(
            guest=cls.guest_a, hotel=cls.hotel,
            check_in="2026-08-01T14:00:00Z",
            check_out="2026-08-03T11:00:00Z",
            status=Reservation.ReservationStatus.CONFIRMED,
        )
        from apps.reservations.models import RoomReservation
        RoomReservation.objects.create(resv=cls.reservation_a, room=room)

    def setUp(self):
        self.client = APIClient()

    def test_receptionist_sees_only_their_hotel_guests(self):
        self.client.force_authenticate(user=self.receptionist)
        response = self.client.get("/api/guests/guests/", format="json")
        self.assertEqual(response.status_code, 200)
        ids = [g["id"] for g in response.json()]
        self.assertIn(self.guest_a.id, ids)
        self.assertNotIn(self.guest_b.id, ids)

    def test_manager_sees_all_guests(self):
        self.client.force_authenticate(user=self.manager)
        response = self.client.get("/api/guests/guests/", format="json")
        self.assertEqual(response.status_code, 200)
        ids = [g["id"] for g in response.json()]
        self.assertIn(self.guest_a.id, ids)
        self.assertIn(self.guest_b.id, ids)