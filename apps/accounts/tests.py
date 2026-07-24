"""
Tests for branch-scoped data access (Step 1).

Every branch-level staff role (receptionist, housekeeping, accountant)
must only see data belonging to their own hotel (branch). Manager and
System Administrator roles may see across branches.

These tests confirm:
  - A receptionist at Branch A CANNOT retrieve Branch B's rooms,
    reservations, invoices, payments, maintenance records, or guests.
  - Same for housekeeping and accountant roles.
  - Manager/admin CAN access data across branches.
  - Direct ID guessing via URL returns 404 or empty for other branches.
"""
import json

from django.test import TestCase
from rest_framework.test import APIClient

from apps.accounts.models import Staff
from apps.billing.models import Invoice, Payment
from apps.guests.models import Guest
from apps.hotels.models import Department, Hotel
from apps.reservations.models import Reservation, RoomReservation
from apps.rooms.models import Maintenance, Room, RoomType
from apps.services.models import Service, ServiceRequest


def _create_hotel(name, suffix):
    """Create a hotel with a unique email."""
    return Hotel.objects.create(
        hotel_name=name,
        hotel_email=f"{suffix}@stayhub.local",
        hotel_address=f"123 {name} St",
        hotel_phone=f"+233-{suffix}",
    )


def _create_staff(hotel, role, suffix):
    """Create a staff member belonging to a specific hotel."""
    return Staff.objects.create_user(
        username=f"{role}_{suffix}@stayhub.local",
        email=f"{role}_{suffix}@stayhub.local",
        password="testpass123",
        staff_name=f"{role.title()} {suffix}",
        staff_phone="+233-555-000-111",
        role=role,
        hotel=hotel,
    )


class BranchScopedAPIAccessTests(TestCase):
    """Confirm that branch-level staff cannot access another branch's data."""

    @classmethod
    def setUpTestData(cls):
        # ── Two branches ────────────────────────────────────
        cls.hotel_a = _create_hotel("StayHub Accra", "accra")
        cls.hotel_b = _create_hotel("StayHub Kumasi", "kumasi")

        # ── Staff per branch and role ────────────────────────
        cls.receptionist_a = _create_staff(cls.hotel_a, "receptionist", "a")
        cls.housekeeping_a = _create_staff(cls.hotel_a, "housekeeping", "a")
        cls.accountant_a  = _create_staff(cls.hotel_a, "accountant", "a")
        cls.manager_a     = _create_staff(cls.hotel_a, "manager", "a")

        cls.receptionist_b = _create_staff(cls.hotel_b, "receptionist", "b")
        cls.housekeeping_b = _create_staff(cls.hotel_b, "housekeeping", "b")
        cls.accountant_b  = _create_staff(cls.hotel_b, "accountant", "b")
        cls.manager_b     = _create_staff(cls.hotel_b, "manager", "b")

        # Admin (no hotel)
        cls.admin = Staff.objects.create_superuser(
            username="admin@stayhub.local", email="admin@stayhub.local",
            password="adminpass123", staff_name="System Admin",
            staff_phone="+233-555-999-999", role="admin",
        )

        # ── Data for Hotel A ──────────────────────────────────
        cls.room_type_a = RoomType.objects.create(
            hotel=cls.hotel_a, type_name="Standard A", price_per_night=100,
        )
        cls.room_a = Room.objects.create(
            hotel=cls.hotel_a, room_type=cls.room_type_a,
            room_number="101", price_per_night=100,
        )
        cls.guest_a = Guest.objects.create(
            guest_name="Guest A", guest_email="guest_a@test.com",
            guest_phone="+233-500-000-001", id_number="GHA-111111111-1",
            nationality="Ghanaian",
        )
        cls.reservation_a = Reservation.objects.create(
            guest=cls.guest_a, hotel=cls.hotel_a,
            check_in="2026-08-01T14:00:00Z", check_out="2026-08-03T11:00:00Z",
            status=Reservation.ReservationStatus.CONFIRMED,
        )
        RoomReservation.objects.create(resv=cls.reservation_a, room=cls.room_a)
        cls.invoice_a = Invoice.objects.create(
            hotel=cls.hotel_a, reservation=cls.reservation_a, total_amount=300,
        )
        cls.payment_a = Payment.objects.create(
            hotel=cls.hotel_a, invoice=cls.invoice_a,
            amount=300, method=Payment.PaymentMethod.CASH,
            status=Payment.PaymentStatus.SUCCESS,
        )
        cls.maintenance_a = Maintenance.objects.create(
            hotel=cls.hotel_a, room=cls.room_a, issue="Leaky faucet",
            status=Maintenance.MaintenanceStatus.OPEN,
        )

        # ── Data for Hotel B ──────────────────────────────────
        cls.room_type_b = RoomType.objects.create(
            hotel=cls.hotel_b, type_name="Deluxe B", price_per_night=200,
        )
        cls.room_b = Room.objects.create(
            hotel=cls.hotel_b, room_type=cls.room_type_b,
            room_number="201", price_per_night=200,
        )
        cls.guest_b = Guest.objects.create(
            guest_name="Guest B", guest_email="guest_b@test.com",
            guest_phone="+233-500-000-002", id_number="GHA-222222222-2",
            nationality="Ghanaian",
        )
        cls.reservation_b = Reservation.objects.create(
            guest=cls.guest_b, hotel=cls.hotel_b,
            check_in="2026-08-05T14:00:00Z", check_out="2026-08-07T11:00:00Z",
            status=Reservation.ReservationStatus.CONFIRMED,
        )
        RoomReservation.objects.create(resv=cls.reservation_b, room=cls.room_b)
        cls.invoice_b = Invoice.objects.create(
            hotel=cls.hotel_b, reservation=cls.reservation_b, total_amount=400,
        )
        cls.payment_b = Payment.objects.create(
            hotel=cls.hotel_b, invoice=cls.invoice_b,
            amount=200, method=Payment.PaymentMethod.MOBILE_MONEY,
            status=Payment.PaymentStatus.PENDING,
        )
        cls.maintenance_b = Maintenance.objects.create(
            hotel=cls.hotel_b, room=cls.room_b, issue="Broken AC",
            status=Maintenance.MaintenanceStatus.OPEN,
        )

    def setUp(self):
        self.client = APIClient()

    # ── Helper: log in and hit an endpoint ──────────────────

    def _get(self, staff, url, expected_status=200):
        self.client.force_authenticate(user=staff)
        response = self.client.get(url, format="json")
        self.assertEqual(response.status_code, expected_status, msg=f"URL={url}")
        return response.json()

    def _get_detail(self, staff, url, expected_status=404):
        self.client.force_authenticate(user=staff)
        response = self.client.get(url, format="json")
        self.assertEqual(response.status_code, expected_status, msg=f"URL={url}")
        return response

    # ── Tests per role: receptionist at hotel A ────────────

    def test_receptionist_a_cannot_see_hotel_b_rooms(self):
        data = self._get(self.receptionist_a, "/api/rooms/rooms/")
        ids = [r["id"] for r in data]
        self.assertIn(self.room_a.id, ids)
        self.assertNotIn(self.room_b.id, ids)

    def test_receptionist_a_cannot_access_hotel_b_room_by_id(self):
        self._get_detail(self.receptionist_a, f"/api/rooms/rooms/{self.room_b.id}/")

    def test_receptionist_a_cannot_see_hotel_b_reservations(self):
        data = self._get(self.receptionist_a, "/api/reservations/reservations/")
        ids = [r["id"] for r in data]
        self.assertIn(self.reservation_a.id, ids)
        self.assertNotIn(self.reservation_b.id, ids)

    def test_receptionist_a_cannot_access_hotel_b_reservation_by_id(self):
        self._get_detail(self.receptionist_a,
                         f"/api/reservations/reservations/{self.reservation_b.id}/")

    def test_receptionist_a_cannot_see_hotel_b_invoices(self):
        data = self._get(self.receptionist_a, "/api/billing/invoices/")
        ids = [r["id"] for r in data]
        self.assertIn(self.invoice_a.id, ids)
        self.assertNotIn(self.invoice_b.id, ids)

    def test_receptionist_a_cannot_access_hotel_b_invoice_by_id(self):
        self._get_detail(self.receptionist_a,
                         f"/api/billing/invoices/{self.invoice_b.id}/")

    # ── Tests per role: housekeeping at hotel A ────────────

    def test_housekeeping_a_cannot_see_hotel_b_maintenance(self):
        data = self._get(self.housekeeping_a, "/api/rooms/maintenance/")
        ids = [r["id"] for r in data]
        self.assertIn(self.maintenance_a.id, ids)
        self.assertNotIn(self.maintenance_b.id, ids)

    def test_housekeeping_a_cannot_access_hotel_b_maintenance_by_id(self):
        self._get_detail(self.housekeeping_a,
                         f"/api/rooms/maintenance/{self.maintenance_b.id}/")

    def test_housekeeping_a_cannot_see_hotel_b_rooms(self):
        data = self._get(self.housekeeping_a, "/api/rooms/rooms/")
        ids = [r["id"] for r in data]
        self.assertIn(self.room_a.id, ids)
        self.assertNotIn(self.room_b.id, ids)

    # ── Tests per role: accountant at hotel A ──────────────

    def test_accountant_a_cannot_see_hotel_b_payments(self):
        data = self._get(self.accountant_a, "/api/billing/payments/")
        ids = [r["id"] for r in data]
        self.assertIn(self.payment_a.id, ids)
        self.assertNotIn(self.payment_b.id, ids)

    def test_accountant_a_cannot_see_hotel_b_invoices(self):
        data = self._get(self.accountant_a, "/api/billing/invoices/")
        ids = [r["id"] for r in data]
        self.assertIn(self.invoice_a.id, ids)
        self.assertNotIn(self.invoice_b.id, ids)

    # ── Manager can see across branches ────────────────────

    def test_manager_a_can_see_hotel_b_reservations(self):
        data = self._get(self.manager_a, "/api/reservations/reservations/")
        ids = [r["id"] for r in data]
        self.assertIn(self.reservation_a.id, ids)
        # Manager sees all (unless scoped by ?scope=)
        self.assertIn(self.reservation_b.id, ids)

    def test_manager_a_can_see_hotel_b_rooms(self):
        data = self._get(self.manager_a, "/api/rooms/rooms/")
        ids = [r["id"] for r in data]
        self.assertIn(self.room_b.id, ids)

    # ── Admin can see across branches ──────────────────────

    def test_admin_can_see_hotel_b_data(self):
        data = self._get(self.admin, "/api/rooms/rooms/")
        ids = [r["id"] for r in data]
        self.assertIn(self.room_b.id, ids)

        data = self._get(self.admin, "/api/reservations/reservations/")
        ids = [r["id"] for r in data]
        self.assertIn(self.reservation_b.id, ids)

        data = self._get(self.admin, "/api/billing/invoices/")
        ids = [r["id"] for r in data]
        self.assertIn(self.invoice_b.id, ids)

    # ── Guest access: no hotel FK, scoped via reservations ─

    def test_receptionist_a_cannot_see_hotel_b_guests(self):
        data = self._get(self.receptionist_a, "/api/guests/guests/")
        ids = [g["id"] for g in data]
        self.assertIn(self.guest_a.id, ids)
        self.assertNotIn(self.guest_b.id, ids)

    def test_receptionist_a_cannot_access_hotel_b_guest_by_id(self):
        self._get_detail(self.receptionist_a,
                         f"/api/guests/guests/{self.guest_b.id}/")

    # ── Staff list scoping ─────────────────────────────────

    def test_receptionist_a_cannot_see_hotel_b_staff(self):
        data = self._get(self.receptionist_a, "/api/accounts/staff/")
        ids = [s["id"] for s in data]
        self.assertIn(self.receptionist_a.id, ids)
        self.assertNotIn(self.receptionist_b.id, ids)
</file_content>
</write_to_file>