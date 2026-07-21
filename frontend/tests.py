import json

from django.test import TestCase
from django.urls import reverse

from apps.hotels.models import Hotel
from apps.reservations.models import Reservation
from apps.rooms.models import Room, RoomType


class PublicJourneyTests(TestCase):
    def setUp(self):
        hotel = Hotel.objects.create(
            hotel_name="Test Hotel",
            hotel_email="hello@testhotel.example",
            hotel_address="1 Test Street",
            hotel_phone="+10000000000",
        )
        room_type = RoomType.objects.create(
            type_name="Test Suite", price_per_night="250.00", description="A test suite"
        )
        self.room = Room.objects.create(
            hotel=hotel, room_type=room_type, room_number="101", floor=1
        )

    def test_all_public_pages_render(self):
        for name in (
            "splash", "splash_page", "signin", "staff_login", "create_account",
            "guest_home", "explore_stays", "hotel_details", "booking",
            "manager_dashboard", "receptionist_dashboard", "accountant_dashboard",
            "housekeeping_dashboard", "design_system",
        ):
            response = self.client.get(reverse(name))
            self.assertEqual(response.status_code, 200, name)

    def test_registration_and_login(self):
        registration = self.client.post(
            reverse("api_register"),
            data=json.dumps({"full_name": "Test User", "email": "user@example.com", "password": "SafePass123"}),
            content_type="application/json",
        )
        self.assertEqual(registration.status_code, 201)
        login = self.client.post(
            reverse("api_login"),
            data=json.dumps({"email": "user@example.com", "password": "SafePass123"}),
            content_type="application/json",
        )
        self.assertEqual(login.status_code, 200)
        self.assertEqual(login.json()["redirect_url"], "/home/")

    def test_booking_reserves_available_room(self):
        options = self.client.get(reverse("booking_options"))
        self.assertEqual(options.status_code, 200)
        self.assertEqual(options.json()["results"][0]["id"], self.room.id)

        response = self.client.post(
            reverse("create_booking"),
            data=json.dumps({
                "guest_name": "Booking Guest", "guest_email": "guest@example.com",
                "guest_phone": "+10000000001", "id_number": "P1234567",
                "nationality": "Testland", "room_id": self.room.id,
                "check_in": "2027-06-01T14:00:00Z", "check_out": "2027-06-04T11:00:00Z",
            }),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 201)
        self.room.refresh_from_db()
        self.assertEqual(self.room.status, Room.RoomStatus.RESERVED)
        self.assertEqual(Reservation.objects.count(), 1)

        duplicate = self.client.post(
            reverse("create_booking"),
            data=json.dumps({
                "guest_name": "Booking Guest", "guest_email": "guest@example.com",
                "id_number": "P1234567", "room_id": self.room.id,
                "check_in": "2027-06-10T14:00:00Z", "check_out": "2027-06-11T11:00:00Z",
            }),
            content_type="application/json",
        )
        self.assertEqual(duplicate.status_code, 409)

# Create your tests here.
