import json
import smtplib
from unittest.mock import Mock, patch

from django.core import mail
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client, TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from apps.accounts.models import Staff
from apps.hotels.models import Hotel
from apps.reservations.models import Reservation
from apps.rooms.models import Room, RoomType


@override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
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
            "splash", "splash_page", "signin", "create_account",
            "guest_home", "explore_stays", "hotel_details", "booking", "design_system",
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

    def test_authenticated_users_are_redirected_from_registration(self):
        user = Staff.objects.create_user(
            username="already@example.com", email="already@example.com", password="SafePass123",
            staff_name="Already Registered", role="guest",
        )
        self.client.force_login(user)
        response = self.client.get(reverse("create_account"))
        self.assertRedirects(response, reverse("guest_home"))

    def test_explore_search_value_is_preserved(self):
        response = self.client.get(reverse("explore_stays"), {"q": "Accra"})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'value="Accra"')

    def test_staff_can_sign_in_with_email(self):
        Staff.objects.create_user(
            username="manager@example.com", email="manager@example.com", password="SafePass123",
            staff_name="Manager User", role="manager",
        )
        response = self.client.post(
            reverse("api_login"),
            data=json.dumps({"email": "manager@example.com", "password": "SafePass123", "staff_login": True}),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["redirect_url"], "/manager/")

    def test_login_challenges_when_two_factor_enabled(self):
        Staff.objects.create_user(
            username="secure@example.com", email="secure@example.com", password="SafePass123",
            staff_name="Secure Manager", role="manager", two_factor_enabled=True,
        )
        response = self.client.post(
            reverse("api_login"),
            data=json.dumps({"email": "secure@example.com", "password": "SafePass123", "staff_login": True}),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 202)
        self.assertTrue(response.json()["verification_method_required"])
        self.assertEqual(response.json()["redirect_url"], "/verification-method/")
        # Not logged in yet until the code is verified
        self.assertFalse("_auth_user_id" in self.client.session)

    def test_guest_cannot_use_staff_login(self):
        Staff.objects.create_user(
            username="guest-staff@example.com", email="guest-staff@example.com", password="SafePass123",
            staff_name="Guest User", role="guest",
        )
        response = self.client.post(
            reverse("api_login"),
            data=json.dumps({"email": "guest-staff@example.com", "password": "SafePass123", "staff_login": True}),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 403)

    def test_profile_updates_name_and_picture(self):
        user = Staff.objects.create_user(
            username="profile@example.com", email="profile@example.com", password="SafePass123",
            staff_name="Profile User", role="guest",
        )
        self.client.force_login(user)
        response = self.client.post(
            reverse("profile"),
            {"full_name": "Updated User", "email": "profile@example.com", "staff_phone": "+233201234567", "profile_picture": SimpleUploadedFile("avatar.png", b"fake-image", content_type="image/png")},
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

    def test_profile_toggles_two_factor(self):
        user = Staff.objects.create_user(
            username="2fa@example.com", email="2fa@example.com", password="SafePass123",
            staff_name="2FA User", role="guest",
        )
        self.client.force_login(user)
        # Enable
        response = self.client.post(
            reverse("profile"),
            {"full_name": "2FA User", "email": "2fa@example.com", "staff_phone": "+233201234567", "two_factor_enabled": "1"},
        )
        self.assertRedirects(response, reverse("profile"))
        user.refresh_from_db()
        self.assertTrue(user.two_factor_enabled)
        # Disable
        self.client.post(
            reverse("profile"),
            {"full_name": "2FA User", "email": "2fa@example.com", "staff_phone": "+233201234567"},
        )
        user.refresh_from_db()
        self.assertFalse(user.two_factor_enabled)
        # Toggle is shown on the page
        self.client.post(
            reverse("profile"),
            {"full_name": "2FA User", "email": "2fa@example.com", "staff_phone": "+233201234567", "two_factor_enabled": "1"},
        )
        page = self.client.get(reverse("profile")).content.decode()
        self.assertIn("two_factor_enabled", page)
        self.assertIn("checked", page)

    def test_registration_and_login(self):
        registration = self.client.post(
            reverse("api_register"),
            data=json.dumps({"full_name": "Test User", "email": "user@example.com", "phone": "+233201234567", "password": "SafePass123"}),
            content_type="application/json",
        )
        self.assertEqual(registration.status_code, 201)
        Staff.objects.filter(email="user@example.com").update(two_factor_enabled=True)
        with patch("frontend.views.secrets.randbelow", return_value=123456), patch("frontend.views._send_verification_sms") as send_sms:
            login = self.client.post(
                reverse("api_login"),
                data=json.dumps({"email": "user@example.com", "password": "SafePass123"}),
                content_type="application/json",
            )
        self.assertEqual(login.status_code, 202)
        self.assertTrue(login.json()["verification_method_required"])
        self.assertEqual(len(mail.outbox), 0)

        with patch("frontend.views.secrets.randbelow", return_value=123456), patch("frontend.views._send_verification_sms") as send_sms:
            method = self.client.post(reverse("verification_method"), {"verification_channel": "sms"})
        self.assertRedirects(method, reverse("verification"))
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
            staff_name="SMTP User", role="guest", two_factor_enabled=True,
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
        self.assertEqual(response.status_code, 202)
        with patch("django.core.mail.send_mail", side_effect=smtplib.SMTPAuthenticationError(535, b"authentication failed")):
            method = self.client.post(reverse("verification_method"), {"verification_channel": "email"})
        self.assertEqual(method.status_code, 200)
        self.assertContains(method, "could not send")

    def test_password_reset_sends_an_email(self):
        self.client.post(
            reverse("api_register"),
            data=json.dumps({"full_name": "Reset User", "email": "reset@example.com", "password": "SafePass123", "phone": "+233201234567"}),
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
        # Pre-create the Google user with 2FA enabled so the callback challenges them
        Staff.objects.create_user(
            username="google@example.com", email="google@example.com",
            password="SafePass123", staff_name="Google User", role="guest", two_factor_enabled=True,
        )
        token_response = Mock()
        token_response.status_code = 200
        token_response.json.return_value = {"id_token": "test-id-token"}
        with patch("frontend.views.requests.post", return_value=token_response), patch(
            "frontend.views.jwt.decode",
            return_value={
                "aud": "test-client.apps.googleusercontent.com",
                "iss": "https://accounts.google.com", "email_verified": True,
                "email": "google@example.com", "name": "Google User", "given_name": "Google",
            },
        ):
            callback = self.client.get(reverse("google_callback"), {"state": state, "code": "test-code"})
        self.assertRedirects(callback, reverse("verification_method"))
        self.assertTrue(Staff.objects.filter(email="google@example.com").exists())
        self.assertEqual(len(mail.outbox), 0)

    @override_settings(
        GOOGLE_OAUTH_CLIENT_ID="test-client.apps.googleusercontent.com",
        GOOGLE_OAUTH_CLIENT_SECRET="test-secret",
        GOOGLE_OAUTH_REDIRECT_URI="http://testserver/api/auth/google/callback/",
    )
    def test_google_oauth_new_user_logs_in_directly_without_2fa(self):
        start = self.client.get(reverse("google_login"))
        state = self.client.session["google_oauth_state"]
        token_response = Mock()
        token_response.status_code = 200
        token_response.json.return_value = {"id_token": "test-id-token"}
        with patch("frontend.views.requests.post", return_value=token_response), patch(
            "frontend.views.jwt.decode",
            return_value={
                "aud": "test-client.apps.googleusercontent.com",
                "iss": "https://accounts.google.com", "email_verified": True,
                "email": "fresh-google@example.com", "name": "Fresh Google", "given_name": "Fresh",
            },
        ):
            callback = self.client.get(reverse("google_callback"), {"state": state, "code": "test-code"})
        self.assertRedirects(callback, reverse("guest_home"))
        self.assertFalse(
            Staff.objects.get(email="fresh-google@example.com").two_factor_enabled
        )

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
                "guest_name": "Booking Guest", "guest_email": "guest@example.com", "guest_phone": "+233201234567",
                "id_number": "P1234567", "nationality": "Testland", "room_id": self.room.id,
                "check_in": "2027-06-10T14:00:00Z", "check_out": "2027-06-11T11:00:00Z",
            }),
            content_type="application/json",
        )
        self.assertEqual(duplicate.status_code, 409)

class AdminManagementCrudTests(TestCase):
    """CRUD endpoints for the admin management page (rooms, staff, hotels)."""

    def setUp(self):
        self.hotel = Hotel.objects.create(
            hotel_name="CRUD Hotel", hotel_email="crud@test.example",
            hotel_address="1 Test St", hotel_phone="+233200000000",
        )
        self.other_hotel = Hotel.objects.create(
            hotel_name="Other Hotel", hotel_email="other@test.example",
            hotel_address="2 Test St", hotel_phone="+233200000001",
        )
        self.room_type = RoomType.objects.create(hotel=self.hotel, type_name="Suite", price_per_night="300.00")
        self.admin = Staff.objects.create_user(
            username="crudadmin@test.example", email="crudadmin@test.example",
            password="AdminPass123", staff_name="CRUD Admin", role="admin",
        )
        self.manager = Staff.objects.create_user(
            username="crudmanager@test.example", email="crudmanager@test.example",
            password="ManagerPass123", staff_name="CRUD Manager", role="manager", hotel=self.hotel,
        )

    def _post(self, url, payload, user=None):
        client = Client()
        if user:
            client.force_login(user)
        return client.post(url, data=json.dumps(payload), content_type="application/json")

    def test_room_create_update_delete(self):
        create = self._post("/admin-api/rooms/save/", {
            "room_number": "101", "floor": 1, "price_per_night": "250.00",
            "status": "AVAILABLE", "housekeeping_status": "DIRTY",
            "hotel_id": self.hotel.id, "room_type_id": self.room_type.id,
        }, user=self.admin)
        self.assertEqual(create.status_code, 200)
        room = Room.objects.get(room_number="101")
        self.assertEqual(room.price_per_night, 250)

        duplicate = self._post("/admin-api/rooms/save/", {
            "room_number": "101", "hotel_id": self.hotel.id,
        }, user=self.admin)
        self.assertEqual(duplicate.status_code, 409)

        update = self._post("/admin-api/rooms/save/", {
            "id": room.id, "room_number": "102", "floor": 2, "price_per_night": "275.00",
            "status": "MAINTENANCE", "housekeeping_status": "CLEAN", "hotel_id": self.hotel.id,
        }, user=self.admin)
        self.assertEqual(update.status_code, 200)
        room.refresh_from_db()
        self.assertEqual(room.room_number, "102")
        self.assertEqual(room.status, "MAINTENANCE")

        delete = self._post("/admin-api/rooms/delete/", {"id": room.id}, user=self.admin)
        self.assertEqual(delete.status_code, 200)
        self.assertFalse(Room.objects.filter(pk=room.id).exists())

    def test_manager_is_scoped_to_own_hotel(self):
        response = self._post("/admin-api/rooms/save/", {
            "room_number": "103", "price_per_night": "100", "hotel_id": self.other_hotel.id,
        }, user=self.manager)
        self.assertEqual(response.status_code, 200)
        room = Room.objects.get(room_number="103")
        self.assertEqual(room.hotel_id, self.hotel.id)

    def test_staff_create_edit_delete_and_protections(self):
        create = self._post("/admin-api/staff/save/", {
            "staff_name": "New Staff", "email": "newstaff@test.example",
            "staff_phone": "+233241234567", "role": "housekeeping",
            "hotel_id": self.hotel.id, "password": "NewStaffPass123",
        }, user=self.admin)
        self.assertEqual(create.status_code, 200)
        staff = Staff.objects.get(email="newstaff@test.example")

        edit = self._post("/admin-api/staff/save/", {
            "id": staff.id, "staff_name": "Renamed Staff", "email": "newstaff@test.example",
            "role": "accountant", "hotel_id": self.hotel.id,
        }, user=self.admin)
        self.assertEqual(edit.status_code, 200)
        staff.refresh_from_db()
        self.assertEqual(staff.role, "accountant")

        delete = self._post("/admin-api/staff/delete/", {"id": staff.id}, user=self.admin)
        self.assertEqual(delete.status_code, 200)
        self.assertFalse(Staff.objects.filter(pk=staff.id).exists())

        # Cannot delete your own account or admin accounts
        self.assertEqual(self._post("/admin-api/staff/delete/", {"id": self.admin.id}, user=self.admin).status_code, 400)
        other_admin = Staff.objects.create_user(
            username="crudadmin2@test.example", email="crudadmin2@test.example",
            password="AdminPass123", staff_name="CRUD Admin 2", role="admin",
        )
        self.assertEqual(self._post("/admin-api/staff/delete/", {"id": other_admin.id}, user=self.admin).status_code, 403)

    def test_hotel_create_admin_only(self):
        create = self._post("/admin-api/hotels/save/", {
            "hotel_name": "New Resort", "hotel_email": "resort@test.example",
            "hotel_phone": "+233200000002", "hotel_address": "3 Beach Rd", "category": "RESORT",
        }, user=self.admin)
        self.assertEqual(create.status_code, 200)
        self.assertTrue(Hotel.objects.filter(hotel_email="resort@test.example").exists())

        denied = self._post("/admin-api/hotels/save/", {
            "hotel_name": "Nope", "hotel_email": "nope@test.example",
            "hotel_phone": "+233200000003", "hotel_address": "4 St", "category": "HOTEL",
        }, user=self.manager)
        self.assertEqual(denied.status_code, 403)

    def test_anonymous_is_blocked(self):
        response = self._post("/admin-api/rooms/save/", {"room_number": "1"}, user=None)
        self.assertIn(response.status_code, (302, 403))

    def test_admin_management_page_renders(self):
        client = Client()
        client.force_login(self.admin)
        response = client.get(reverse("admin_management"))
        self.assertEqual(response.status_code, 200)


class StaffDashboardOperationsTests(TestCase):
    """Dashboard operations: check-in/out, housekeeping, maintenance, assign room, CSV export."""

    def setUp(self):
        self.hotel = Hotel.objects.create(
            hotel_name="Ops Hotel", hotel_email="ops@test.example",
            hotel_address="1 Ops St", hotel_phone="+233200000010",
        )
        self.room = Room.objects.create(
            hotel=self.hotel, room_number="201", floor=2, status="AVAILABLE",
            housekeeping_status="DIRTY", price_per_night="180.00",
        )
        self.guest = self._make_guest("ops-guest@example.com", "Ops Guest")
        self.receptionist = Staff.objects.create_user(
            username="reception@test.example", email="reception@test.example",
            password="ReceptionPass123", staff_name="Ops Receptionist", role="receptionist",
            hotel=self.hotel,
        )
        self.housekeeper = Staff.objects.create_user(
            username="hk@test.example", email="hk@test.example",
            password="HousekeepingPass123", staff_name="Ops Housekeeper", role="housekeeping",
            hotel=self.hotel,
        )
        self.accountant = Staff.objects.create_user(
            username="acc@test.example", email="acc@test.example",
            password="AccountantPass123", staff_name="Ops Accountant", role="accountant",
            hotel=self.hotel,
        )

    def _make_guest(self, email, name):
        from apps.guests.models import Guest

        return Guest.objects.create(
            guest_email=email, guest_name=name, guest_phone="+233241111111",
            id_number="GHA-123456789-0", nationality="Ghana",
        )

    def _make_reservation(self, status="Pending"):
        return Reservation.objects.create(
            guest=self.guest, hotel=self.hotel, status=status,
            check_in=timezone.now() - timezone.timedelta(hours=1),
            check_out=timezone.now() + timezone.timedelta(days=1),
        )

    def _post(self, url, payload, user):
        client = Client()
        client.force_login(user)
        return client.post(url, data=json.dumps(payload), content_type="application/json")

    def test_dashboard_pages_render_for_their_roles(self):
        checks = [
            (self.receptionist, "/receptionist/"),
            (self.housekeeper, "/housekeeping/"),
            (self.accountant, "/accountant/"),
        ]
        for user, url in checks:
            client = Client()
            client.force_login(user)
            self.assertEqual(client.get(url).status_code, 200, url)

        # json_script data blocks must be present (XSS-safe JSON injection)
        client = Client()
        client.force_login(self.receptionist)
        reception_body = client.get("/receptionist/").content.decode()
        self.assertIn("reception-reservations-data", reception_body)
        self.assertIn("reception-rooms-data", reception_body)
        client = Client()
        client.force_login(self.housekeeper)
        hk_body = client.get("/housekeeping/").content.decode()
        self.assertIn("hk-rooms-data", hk_body)

    def test_sidebar_renders_and_manager_admin_can_view_finance_and_housekeeping(self):
        admin = Staff.objects.create_user(
            username="opsadmin@test.example", email="opsadmin@test.example",
            password="AdminPass123", staff_name="Ops Admin", role="admin", hotel=self.hotel,
        )
        manager = Staff.objects.create_user(
            username="opsmanager@test.example", email="opsmanager@test.example",
            password="ManagerPass123", staff_name="Ops Manager", role="manager", hotel=self.hotel,
        )
        checks = [
            (self.receptionist, "/receptionist/"),
            (self.accountant, "/accountant/"),
            (self.housekeeper, "/housekeeping/"),
            (admin, "/manager/"),
            (admin, "/accountant/"),
            (admin, "/housekeeping/"),
            (admin, "/admin-management/"),
            (manager, "/accountant/"),
            (manager, "/housekeeping/"),
        ]
        for user, url in checks:
            client = Client()
            client.force_login(user)
            response = client.get(url)
            self.assertEqual(response.status_code, 200, url)
            self.assertIn("sidebar hide-mobile", response.content.decode(), url)

    def test_assign_checkin_checkout_lifecycle(self):
        reservation = self._make_reservation()

        # No room yet -> check-in is rejected
        denied = self._post("/staff-api/checkin/", {"reservation_id": reservation.id}, self.receptionist)
        self.assertEqual(denied.status_code, 409)

        # Assign the room
        assign = self._post("/staff-api/assign-room/", {
            "reservation_id": reservation.id, "room_id": self.room.id,
        }, self.receptionist)
        self.assertEqual(assign.status_code, 200)
        self.room.refresh_from_db()
        self.assertEqual(self.room.status, "RESERVED")

        # Check in
        checkin = self._post("/staff-api/checkin/", {"reservation_id": reservation.id}, self.receptionist)
        self.assertEqual(checkin.status_code, 200)
        reservation.refresh_from_db()
        self.room.refresh_from_db()
        self.assertEqual(reservation.status, "Checked_In")
        self.assertEqual(self.room.status, "OCCUPIED")

        # Double check-in rejected
        again = self._post("/staff-api/checkin/", {"reservation_id": reservation.id}, self.receptionist)
        self.assertEqual(again.status_code, 409)

        # Check out -> room available + dirty for housekeeping
        checkout = self._post("/staff-api/checkout/", {"reservation_id": reservation.id}, self.receptionist)
        self.assertEqual(checkout.status_code, 200)
        reservation.refresh_from_db()
        self.room.refresh_from_db()
        self.assertEqual(reservation.status, "Checked_Out")
        self.assertEqual(self.room.status, "AVAILABLE")
        self.assertEqual(self.room.housekeeping_status, "DIRTY")

    def test_housekeeping_and_maintenance_updates(self):
        from apps.rooms.models import Maintenance

        # Mark room clean
        clean = self._post("/staff-api/housekeeping/update/", {
            "room_id": self.room.id, "status": "CLEAN",
        }, self.housekeeper)
        self.assertEqual(clean.status_code, 200)
        self.room.refresh_from_db()
        self.assertEqual(self.room.housekeeping_status, "CLEAN")

        # Advance a maintenance task
        task = Maintenance.objects.create(room=self.room, issue="Broken AC", status="OPEN")
        start = self._post("/staff-api/maintenance/update/", {
            "task_id": task.id, "status": "IN_PROGRESS",
        }, self.housekeeper)
        self.assertEqual(start.status_code, 200)
        resolve = self._post("/staff-api/maintenance/update/", {
            "task_id": task.id, "status": "RESOLVED",
        }, self.housekeeper)
        self.assertEqual(resolve.status_code, 200)
        task.refresh_from_db()
        self.assertEqual(task.status, "RESOLVED")

    def test_role_guards_and_no_hotel_message(self):
        # Housekeeper cannot check in
        denied = self._post("/staff-api/checkin/", {"reservation_id": 1}, self.housekeeper)
        self.assertEqual(denied.status_code, 403)

        # Receptionist without a hotel gets a clear message
        unassigned = Staff.objects.create_user(
            username="unassigned@test.example", email="unassigned@test.example",
            password="UnassignedPass123", staff_name="No Hotel", role="receptionist",
        )
        response = self._post("/staff-api/checkin/", {"reservation_id": 1}, unassigned)
        self.assertEqual(response.status_code, 400)
        self.assertIn("not assigned to a hotel", response.json()["detail"])

        # Anonymous is blocked
        anon = Client().post("/staff-api/checkin/", data=json.dumps({"reservation_id": 1}), content_type="application/json")
        self.assertEqual(anon.status_code, 403)

    def test_accountant_export_csv(self):
        client = Client()
        client.force_login(self.accountant)
        response = client.get("/staff-api/export/csv/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "text/csv; charset=utf-8")
        self.assertIn("Invoice #", response.content.decode())

        # Unassigned accountant is blocked from exporting everything
        unassigned = Staff.objects.create_user(
            username="acc-unassigned@test.example", email="acc-unassigned@test.example",
            password="AccountantPass123", staff_name="No Hotel Acc", role="accountant",
        )
        client = Client()
        client.force_login(unassigned)
        denied = client.get("/staff-api/export/csv/")
        self.assertEqual(denied.status_code, 400)
        self.assertIn("not assigned to a hotel", denied.json()["detail"])

    def test_guest_search_finds_guests_and_requires_role(self):
        client = Client()
        client.force_login(self.receptionist)
        response = client.get("/staff-api/guests/search/", {"q": "ops-guest"})
        self.assertEqual(response.status_code, 200)
        results = response.json()["results"]
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["guest_email"], "ops-guest@example.com")
        self.assertEqual(results[0]["guest_name"], "Ops Guest")

        # Empty query returns no results
        empty = client.get("/staff-api/guests/search/")
        self.assertEqual(empty.json()["results"], [])

        # Housekeepers are not allowed to search guests
        denied = Client()
        denied.force_login(self.housekeeper)
        blocked = denied.get("/staff-api/guests/search/", {"q": "ops"})
        self.assertEqual(blocked.status_code, 403)

    def test_record_payment_updates_invoice_status(self):
        from apps.billing.models import Invoice, Payment

        reservation = self._make_reservation()
        invoice = Invoice.objects.create(hotel=self.hotel, reservation=reservation, total_amount="100.00")

        # Partial payment -> invoice becomes partial
        partial = self._post("/staff-api/payments/record/", {
            "invoice_id": invoice.id, "amount": "40.00", "method": "Cash",
        }, self.accountant)
        self.assertEqual(partial.status_code, 200)
        invoice.refresh_from_db()
        self.assertEqual(invoice.status, "partial")
        self.assertEqual(Payment.objects.filter(invoice=invoice).count(), 1)

        # Overpayment is rejected
        overpay = self._post("/staff-api/payments/record/", {
            "invoice_id": invoice.id, "amount": "1000.00", "method": "Cash",
        }, self.accountant)
        self.assertEqual(overpay.status_code, 400)

        # Remaining balance -> invoice becomes paid
        full = self._post("/staff-api/payments/record/", {
            "invoice_id": invoice.id, "amount": "60.00", "method": "Mobile_Money",
        }, self.accountant)
        self.assertEqual(full.status_code, 200)
        invoice.refresh_from_db()
        self.assertEqual(invoice.status, "paid")

        # Already-paid invoices reject further payments with a clear message
        already_paid = self._post("/staff-api/payments/record/", {
            "invoice_id": invoice.id, "amount": "10.00", "method": "Cash",
        }, self.accountant)
        self.assertEqual(already_paid.status_code, 409)
        self.assertIn("already fully paid", already_paid.json()["detail"])

        # Bad method / bad amount are rejected
        bad_method = self._post("/staff-api/payments/record/", {
            "invoice_id": invoice.id, "amount": "10.00", "method": "Bitcoin",
        }, self.accountant)
        self.assertEqual(bad_method.status_code, 400)
        bad_amount = self._post("/staff-api/payments/record/", {
            "invoice_id": invoice.id, "amount": "0", "method": "Cash",
        }, self.accountant)
        self.assertEqual(bad_amount.status_code, 400)

        # Receptionists cannot record payments
        denied = self._post("/staff-api/payments/record/", {
            "invoice_id": invoice.id, "amount": "10.00", "method": "Cash",
        }, self.receptionist)
        self.assertEqual(denied.status_code, 403)
