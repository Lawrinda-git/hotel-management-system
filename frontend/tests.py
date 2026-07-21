import json
import smtplib
from unittest.mock import Mock, patch

from django.core import mail
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse

from apps.accounts.models import Staff
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

    def test_home_uses_the_signed_in_users_name(self):
        user = Staff.objects.create_user(
            username="member@example.com", email="member@example.com", password="SafePass123",
            staff_name="Morgan Member", first_name="Morgan", role="guest",
        )
        self.client.force_login(user)
        response = self.client.get(reverse("guest_home"))
        self.assertContains(response, "Morgan")
        self.assertNotContains(response, ">Alex<")

    def test_profile_updates_name_and_picture(self):
        user = Staff.objects.create_user(
            username="profile@example.com", email="profile@example.com", password="SafePass123",
            staff_name="Profile User", role="guest",
        )
        self.client.force_login(user)
        response = self.client.post(
            reverse("profile"),
            {"full_name": "Updated User", "email": "profile@example.com", "profile_picture": SimpleUploadedFile("avatar.png", b"fake-image", content_type="image/png")},
        )
        self.assertRedirects(response, reverse("profile"))
        user.refresh_from_db()
        self.assertEqual(user.staff_name, "Updated User")
        self.assertTrue(user.profile_picture.name.startswith("profile_pictures/"))

    def test_profile_updates_phone_number(self):
        user = Staff.objects.create_user(
            username="phone@example.com", email="phone@example.com", password="SafePass123",
            staff_name="Phone User", role="guest",
        )
        self.client.force_login(user)
        response = self.client.post(
            reverse("profile"),
            {"full_name": "Phone User", "email": "phone@example.com", "staff_phone": "+233201234567"},
        )
        self.assertRedirects(response, reverse("profile"))
        user.refresh_from_db()
        self.assertEqual(user.staff_phone, "+233201234567")

    def test_registration_and_login(self):
        registration = self.client.post(
            reverse("api_register"),
            data=json.dumps({"full_name": "Test User", "email": "user@example.com", "phone": "+233201234567", "password": "SafePass123"}),
            content_type="application/json",
        )
        self.assertEqual(registration.status_code, 201)
        with patch("frontend.views.secrets.randbelow", return_value=123456), patch("frontend.views._send_verification_sms") as send_sms:
            login = self.client.post(
                reverse("api_login"),
                data=json.dumps({"email": "user@example.com", "password": "SafePass123", "verification_channel": "sms"}),
                content_type="application/json",
            )
        self.assertEqual(login.status_code, 202)
        self.assertTrue(login.json()["two_factor_required"])
        self.assertEqual(len(mail.outbox), 0)
        send_sms.assert_called_once()

        verification = self.client.post(
            reverse("api_two_factor_verify"),
            data=json.dumps({"code": "123456"}),
            content_type="application/json",
        )
        self.assertEqual(verification.status_code, 200)
        self.assertEqual(verification.json()["redirect_url"], "/home/")

    @override_settings(DEBUG=False)
    def test_smtp_auth_failure_does_not_bypass_two_factor(self):
        Staff.objects.create_user(
            username="smtp@example.com", email="smtp@example.com", password="SafePass123",
            staff_name="SMTP User", role="guest",
        )
        with patch(
            "django.core.mail.send_mail",
            side_effect=smtplib.SMTPAuthenticationError(535, b"authentication failed"),
        ):
            response = self.client.post(
                reverse("api_login"),
                data=json.dumps({"email": "smtp@example.com", "password": "SafePass123"}),
                content_type="application/json",
            )
        self.assertEqual(response.status_code, 503)
        self.assertNotIn("dev_code", response.json())

    def test_password_reset_sends_an_email(self):
        self.client.post(
            reverse("api_register"),
            data=json.dumps({"full_name": "Reset User", "email": "reset@example.com", "password": "SafePass123"}),
            content_type="application/json",
        )
        response = self.client.post(reverse("password_reset"), {"email": "reset@example.com"})
        self.assertRedirects(response, reverse("password_reset_done"))
        self.assertEqual(len(mail.outbox), 1)

    @override_settings(
        GOOGLE_OAUTH_CLIENT_ID="test-client.apps.googleusercontent.com",
        GOOGLE_OAUTH_CLIENT_SECRET="test-secret",
        GOOGLE_OAUTH_REDIRECT_URI="http://testserver/api/auth/google/callback/",
    )
    def test_google_oauth_redirect_and_callback(self):
        start = self.client.get(reverse("google_login"))
        self.assertEqual(start.status_code, 302)
        self.assertIn("accounts.google.com", start["Location"])
        state = self.client.session["google_oauth_state"]
        token_response = Mock()
        token_response.read.return_value = b'{"id_token": "test-id-token"}'
        with patch("frontend.views.urlopen", return_value=token_response), patch(
            "frontend.views.jwt.decode",
            return_value={
                "aud": "test-client.apps.googleusercontent.com",
                "iss": "https://accounts.google.com", "email_verified": True,
                "email": "google@example.com", "name": "Google User", "given_name": "Google",
            },
        ):
            callback = self.client.get(reverse("google_callback"), {"state": state, "code": "test-code"})
        self.assertRedirects(callback, reverse("verification"))
        self.assertTrue(Staff.objects.filter(email="google@example.com").exists())
        self.assertEqual(len(mail.outbox), 1)

    def test_verification_page_renders(self):
        user = Staff.objects.create_user(
            username="verify@example.com", email="verify@example.com", password="SafePass123",
            staff_name="Verify User", role="guest",
        )
        session = self.client.session
        session["pending_login_user_id"] = user.id
        session["pending_login_channel"] = "sms"
        session.save()
        response = self.client.get(reverse("verification"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Current method: SMS")

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
