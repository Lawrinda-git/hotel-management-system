"""
Full StayHub demo dataset — implemented as a Django management command.

Mirrors the complete seed SQL (all 15 sections: hotels, departments, staff,
guests, room types, rooms, reservations, room_reservations, invoices,
payments, services, service requests, feedback, maintenance, notifications)
using the project's ORM models.

Merge-safe: every row is upserted by its natural key, so existing data that is
not part of this dataset (e.g. real guest accounts) is preserved and the
command can be re-run safely.

Usage:
    python manage.py seed_full_demo
"""
from datetime import datetime

from django.contrib.auth.hashers import make_password
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from apps.accounts.models import Staff
from apps.billing.models import Invoice, Payment
from apps.feedback.models import Feedback
from apps.guests.models import Guest
from apps.hotels.models import Department, Hotel
from apps.notifications.models import Notification
from apps.reservations.models import Reservation, RoomReservation
from apps.rooms.models import Maintenance, Room, RoomType
from apps.services.models import Service, ServiceRequest


def dt(value):
    """Parse 'YYYY-MM-DD HH:MM:SS' into a timezone-aware datetime."""
    return timezone.make_aware(datetime.strptime(value, "%Y-%m-%d %H:%M:%S"))


def stamp(model, instance, **fields):
    """Set auto_now_add fields explicitly (bypasses auto_now_add on save)."""
    model.objects.filter(pk=instance.pk).update(**fields)


class Command(BaseCommand):
    help = "Create the full StayHub demo dataset (hotels, staff, rooms, reservations, billing, services, feedback, maintenance, notifications)."

    # ── SECTION 1 — HOTELS (3 real Ghanaian hotels) ──────────────────────
    hotels = [
        ("Kempinski Hotel Gold Coast City", "reservations@kempinski-accra.com",
         "Gamel Abdul Nasser Avenue, Accra, Greater Accra Region, Ghana",
         "+233302611000", Hotel.Category.HOTEL, "2024-01-15 08:00:00"),
        ("Labadi Beach Hotel", "info@labadibeach.com",
         "La Beach Road, Labadi, Accra, Greater Accra Region, Ghana",
         "+233302772501", Hotel.Category.RESORT, "2024-02-01 09:00:00"),
        ("Elmina Beach Resort", "reservations@elminabeach.com",
         "Coastal Road, Elmina, Central Region, Ghana",
         "+233332133400", Hotel.Category.RESORT, "2024-03-10 10:00:00"),
    ]

    # ── SECTION 2 — DEPARTMENTS (5 per hotel) ────────────────────────────
    departments = [
        ("Kempinski Hotel Gold Coast City", "Front Desk"),
        ("Kempinski Hotel Gold Coast City", "Housekeeping"),
        ("Kempinski Hotel Gold Coast City", "Maintenance"),
        ("Kempinski Hotel Gold Coast City", "Food & Beverage"),
        ("Kempinski Hotel Gold Coast City", "Finance"),
        ("Labadi Beach Hotel", "Front Desk"),
        ("Labadi Beach Hotel", "Housekeeping"),
        ("Labadi Beach Hotel", "Maintenance"),
        ("Labadi Beach Hotel", "Food & Beverage"),
        ("Labadi Beach Hotel", "Finance"),
        ("Elmina Beach Resort", "Front Desk"),
        ("Elmina Beach Resort", "Housekeeping"),
        ("Elmina Beach Resort", "Maintenance"),
        ("Elmina Beach Resort", "Food & Beverage"),
        ("Elmina Beach Resort", "Finance"),
    ]

    # ── SECTION 3 — STAFF ACCOUNTS ───────────────────────────────────────
    # (username, email, first_name, last_name, staff_name, phone, role,
    #  department, hotel_email, is_superuser)
    staff = [
        ("admin@stayhub.com", "admin@stayhub.com", "Kofi", "Asante", "Kofi Asante",
         "+233244000001", "admin", None, None, True),
        ("manager.kempinski", "manager@kempinski-accra.com", "Akua", "Mensah", "Akua Mensah",
         "+233244000002", "manager", "Front Desk", "Kempinski Hotel Gold Coast City", False),
        ("reception.kempinski1", "reception1@kempinski-accra.com", "Ama", "Boateng", "Ama Boateng",
         "+233244000003", "receptionist", "Front Desk", "Kempinski Hotel Gold Coast City", False),
        ("reception.kempinski2", "reception2@kempinski-accra.com", "Kwame", "Darko", "Kwame Darko",
         "+233244000004", "receptionist", "Front Desk", "Kempinski Hotel Gold Coast City", False),
        ("housekeeping.kempinski1", "hk1@kempinski-accra.com", "Abena", "Frimpong", "Abena Frimpong",
         "+233244000005", "housekeeping", "Housekeeping", "Kempinski Hotel Gold Coast City", False),
        ("housekeeping.kempinski2", "hk2@kempinski-accra.com", "Yaw", "Owusu", "Yaw Owusu",
         "+233244000006", "housekeeping", "Housekeeping", "Kempinski Hotel Gold Coast City", False),
        ("maintenance.kempinski1", "maintenance1@kempinski-accra.com", "Kojo", "Agyei", "Kojo Agyei",
         "+233244000007", "housekeeping", "Maintenance", "Kempinski Hotel Gold Coast City", False),
        ("accountant.kempinski", "accounts@kempinski-accra.com", "Efua", "Asiedu", "Efua Asiedu",
         "+233244000008", "accountant", "Finance", "Kempinski Hotel Gold Coast City", False),
        ("manager.labadi", "manager@labadibeach.com", "Nana", "Osei", "Nana Osei",
         "+233244000009", "manager", "Front Desk", "Labadi Beach Hotel", False),
        ("reception.labadi1", "reception1@labadibeach.com", "Adwoa", "Kyei", "Adwoa Kyei",
         "+233244000010", "receptionist", "Front Desk", "Labadi Beach Hotel", False),
        ("housekeeping.labadi1", "hk1@labadibeach.com", "Akosua", "Gyamfi", "Akosua Gyamfi",
         "+233244000011", "housekeeping", "Housekeeping", "Labadi Beach Hotel", False),
        ("maintenance.labadi1", "maintenance1@labadibeach.com", "Fiifi", "Baah", "Fiifi Baah",
         "+233244000012", "housekeeping", "Maintenance", "Labadi Beach Hotel", False),
        ("accountant.labadi", "accounts@labadibeach.com", "Maame", "Amoah", "Maame Amoah",
         "+233244000013", "accountant", "Finance", "Labadi Beach Hotel", False),
        ("manager.elmina", "manager@elminabeach.com", "Kweku", "Annan", "Kweku Annan",
         "+233244000014", "manager", "Front Desk", "Elmina Beach Resort", False),
        ("reception.elmina1", "reception1@elminabeach.com", "Afia", "Mensah", "Afia Mensah",
         "+233244000015", "receptionist", "Front Desk", "Elmina Beach Resort", False),
        ("housekeeping.elmina1", "hk1@elminabeach.com", "Esi", "Appiah", "Esi Appiah",
         "+233244000016", "housekeeping", "Housekeeping", "Elmina Beach Resort", False),
        ("maintenance.elmina1", "maintenance1@elminabeach.com", "Kobina", "Essel", "Kobina Essel",
         "+233244000017", "housekeeping", "Maintenance", "Elmina Beach Resort", False),
        ("accountant.elmina", "accounts@elminabeach.com", "Araba", "Quaye", "Araba Quaye",
         "+233244000018", "accountant", "Finance", "Elmina Beach Resort", False),
    ]

    # Per-role passwords (mirrors the seed SQL's password-reset instructions).
    # NOTE: re-running this seed resets seed staff passwords to these values
    # (intentional — matches the SQL instructions; use the app to change them after).
    staff_passwords = {
        "admin": "admin123456",
        "manager": "manager123",
        "receptionist": "reception123",
        "accountant": "accountant123",
        "housekeeping": "housekeeping123",
    }

    # Per-staff hired_at / date_joined (mirrors the seed SQL's timestamps).
    staff_hired_at = {
        "admin@stayhub.com": "2024-01-15 08:00:00",
        "manager@kempinski-accra.com": "2024-01-20 08:00:00",
        "reception1@kempinski-accra.com": "2024-02-01 08:00:00",
        "reception2@kempinski-accra.com": "2024-02-01 08:00:00",
        "hk1@kempinski-accra.com": "2024-02-10 08:00:00",
        "hk2@kempinski-accra.com": "2024-02-10 08:00:00",
        "maintenance1@kempinski-accra.com": "2024-03-01 08:00:00",
        "accounts@kempinski-accra.com": "2024-02-15 08:00:00",
        "manager@labadibeach.com": "2024-02-01 08:00:00",
        "reception1@labadibeach.com": "2024-02-05 08:00:00",
        "hk1@labadibeach.com": "2024-02-10 08:00:00",
        "maintenance1@labadibeach.com": "2024-03-01 08:00:00",
        "accounts@labadibeach.com": "2024-02-15 08:00:00",
        "manager@elminabeach.com": "2024-03-10 08:00:00",
        "reception1@elminabeach.com": "2024-03-15 08:00:00",
        "hk1@elminabeach.com": "2024-03-20 08:00:00",
        "maintenance1@elminabeach.com": "2024-03-25 08:00:00",
        "accounts@elminabeach.com": "2024-03-25 08:00:00",
    }

    # ── SECTION 4 — GUESTS (Ghanaian + international) ────────────────────
    guests = [
        ("Kwame Asante Mensah", "+233244123001", "kwame.mensah@gmail.com", "GHA-0987654321", "Ghanaian", "2024-03-01 10:00:00"),
        ("Abena Osei Boateng", "+233244123002", "abena.boateng@gmail.com", "GHA-1122334455", "Ghanaian", "2024-03-15 11:00:00"),
        ("Yaw Darko Frimpong", "+233244123003", "yaw.frimpong@yahoo.com", "GHA-2233445566", "Ghanaian", "2024-04-01 09:00:00"),
        ("Akosua Ama Gyamfi", "+233244123004", "akosua.gyamfi@gmail.com", "GHA-3344556677", "Ghanaian", "2024-04-10 14:00:00"),
        ("Kofi Nkrumah Agyei", "+233244123005", "kofi.agyei@outlook.com", "GHA-4455667788", "Ghanaian", "2024-04-20 16:00:00"),
        ("Adwoa Serwaa Asiedu", "+233244123006", "adwoa.asiedu@gmail.com", "GHA-5566778899", "Ghanaian", "2024-05-01 10:00:00"),
        ("Kweku Baah Antwi", "+233244123007", "kweku.antwi@gmail.com", "GHA-6677889900", "Ghanaian", "2024-05-10 13:00:00"),
        ("Efua Kyei Appiah", "+233244123008", "efua.appiah@yahoo.com", "GHA-7788990011", "Ghanaian", "2024-05-20 11:00:00"),
        ("Nana Ama Owusu", "+233244123009", "nana.owusu@gmail.com", "GHA-8899001122", "Ghanaian", "2024-06-01 09:00:00"),
        ("Fiifi Quaye Nyarko", "+233244123010", "fiifi.nyarko@gmail.com", "GHA-9900112233", "Ghanaian", "2024-06-10 15:00:00"),
        ("James Okafor", "+2348012345678", "james.okafor@gmail.com", "NGA-112233445", "Nigerian", "2024-06-15 10:00:00"),
        ("Sarah Mitchell", "+14155551234", "sarah.mitchell@email.com", "US-A12345678", "American", "2024-06-20 14:00:00"),
        ("Emma Williams", "+447911123456", "emma.williams@email.co.uk", "UK-PQ9876543", "British", "2024-07-01 12:00:00"),
        ("Jean-Pierre Dubois", "+33612345678", "jp.dubois@email.fr", "FR-AB1234567", "French", "2024-07-05 11:00:00"),
        ("Amara Diallo", "+221701234567", "amara.diallo@email.sn", "SEN-CD789012", "Senegalese", "2024-07-10 09:00:00"),
    ]

    # ── SECTION 5 — ROOM TYPES (per-hotel pricing in GHS) ────────────────
    room_types = [
        ("Kempinski Hotel Gold Coast City", "Superior Room", "850.00",
         "Elegantly furnished room with king or twin beds, city or pool views, marble bathroom, and all modern amenities."),
        ("Kempinski Hotel Gold Coast City", "Deluxe Room", "1100.00",
         "Spacious deluxe room with premium furnishings, large work desk, 55-inch smart TV, and enhanced bathroom amenities."),
        ("Kempinski Hotel Gold Coast City", "Junior Suite", "1800.00",
         "Generously sized suite with separate living area, panoramic city views, butler service, and exclusive lounge access."),
        ("Kempinski Hotel Gold Coast City", "Presidential Suite", "4500.00",
         "The pinnacle of luxury — two-bedroom suite with private dining room, personal butler, panoramic Accra skyline views."),
        ("Labadi Beach Hotel", "Standard Garden View", "480.00",
         "Comfortable room overlooking lush tropical gardens with queen bed, air conditioning, and private balcony."),
        ("Labadi Beach Hotel", "Deluxe Ocean View", "720.00",
         "Stunning Atlantic Ocean views from a spacious room with king bed, premium linens, and sundeck access."),
        ("Labadi Beach Hotel", "Beach Bungalow", "1200.00",
         "Private beachfront bungalow steps from the ocean, with outdoor shower, four-poster bed, and direct beach access."),
        ("Labadi Beach Hotel", "Executive Suite", "1950.00",
         "Two-room suite with living area, ocean-facing terrace, private plunge pool, and dedicated concierge service."),
        ("Elmina Beach Resort", "Heritage Room", "380.00",
         "Tastefully decorated room inspired by Elmina Castle history, with queen bed, local art, and garden view."),
        ("Elmina Beach Resort", "Ocean Chalet", "650.00",
         "Standalone chalet with direct ocean frontage, outdoor deck, hammock, and breathtaking Cape Coast views."),
        ("Elmina Beach Resort", "Family Suite", "950.00",
         "Spacious two-room suite ideal for families, with bunk beds for children, kitchenette, and private courtyard."),
    ]

    # ── SECTION 6 — ROOMS (42 total) ─────────────────────────────────────
    # (hotel_name, room_number, floor, status, housekeeping_status, price, type_name)
    rooms = [
        # Kempinski — floors 1-4
        ("Kempinski Hotel Gold Coast City", "101", 1, Room.RoomStatus.OCCUPIED, Room.HousekeepingStatus.DIRTY, "850.00", "Superior Room"),
        ("Kempinski Hotel Gold Coast City", "102", 1, Room.RoomStatus.AVAILABLE, Room.HousekeepingStatus.CLEAN, "850.00", "Superior Room"),
        ("Kempinski Hotel Gold Coast City", "103", 1, Room.RoomStatus.AVAILABLE, Room.HousekeepingStatus.INSPECTED, "850.00", "Superior Room"),
        ("Kempinski Hotel Gold Coast City", "104", 1, Room.RoomStatus.RESERVED, Room.HousekeepingStatus.CLEAN, "850.00", "Superior Room"),
        ("Kempinski Hotel Gold Coast City", "201", 2, Room.RoomStatus.OCCUPIED, Room.HousekeepingStatus.DIRTY, "1100.00", "Deluxe Room"),
        ("Kempinski Hotel Gold Coast City", "202", 2, Room.RoomStatus.OCCUPIED, Room.HousekeepingStatus.DIRTY, "1100.00", "Deluxe Room"),
        ("Kempinski Hotel Gold Coast City", "203", 2, Room.RoomStatus.AVAILABLE, Room.HousekeepingStatus.CLEAN, "1100.00", "Deluxe Room"),
        ("Kempinski Hotel Gold Coast City", "204", 2, Room.RoomStatus.MAINTENANCE, Room.HousekeepingStatus.OUT_OF_SERVICE, "1100.00", "Deluxe Room"),
        ("Kempinski Hotel Gold Coast City", "301", 3, Room.RoomStatus.OCCUPIED, Room.HousekeepingStatus.DIRTY, "1800.00", "Junior Suite"),
        ("Kempinski Hotel Gold Coast City", "302", 3, Room.RoomStatus.AVAILABLE, Room.HousekeepingStatus.INSPECTED, "1800.00", "Junior Suite"),
        ("Kempinski Hotel Gold Coast City", "303", 3, Room.RoomStatus.RESERVED, Room.HousekeepingStatus.CLEAN, "1800.00", "Junior Suite"),
        ("Kempinski Hotel Gold Coast City", "304", 3, Room.RoomStatus.AVAILABLE, Room.HousekeepingStatus.CLEAN, "1800.00", "Junior Suite"),
        ("Kempinski Hotel Gold Coast City", "401", 4, Room.RoomStatus.OCCUPIED, Room.HousekeepingStatus.DIRTY, "4500.00", "Presidential Suite"),
        ("Kempinski Hotel Gold Coast City", "402", 4, Room.RoomStatus.AVAILABLE, Room.HousekeepingStatus.INSPECTED, "4500.00", "Presidential Suite"),
        ("Kempinski Hotel Gold Coast City", "403", 4, Room.RoomStatus.MAINTENANCE, Room.HousekeepingStatus.OUT_OF_SERVICE, "4500.00", "Presidential Suite"),
        ("Kempinski Hotel Gold Coast City", "404", 4, Room.RoomStatus.AVAILABLE, Room.HousekeepingStatus.CLEAN, "4500.00", "Presidential Suite"),
        # Labadi — floors 1-3
        ("Labadi Beach Hotel", "101", 1, Room.RoomStatus.OCCUPIED, Room.HousekeepingStatus.DIRTY, "480.00", "Standard Garden View"),
        ("Labadi Beach Hotel", "102", 1, Room.RoomStatus.AVAILABLE, Room.HousekeepingStatus.CLEAN, "480.00", "Standard Garden View"),
        ("Labadi Beach Hotel", "103", 1, Room.RoomStatus.AVAILABLE, Room.HousekeepingStatus.INSPECTED, "480.00", "Standard Garden View"),
        ("Labadi Beach Hotel", "104", 1, Room.RoomStatus.RESERVED, Room.HousekeepingStatus.CLEAN, "480.00", "Standard Garden View"),
        ("Labadi Beach Hotel", "201", 2, Room.RoomStatus.OCCUPIED, Room.HousekeepingStatus.DIRTY, "720.00", "Deluxe Ocean View"),
        ("Labadi Beach Hotel", "202", 2, Room.RoomStatus.OCCUPIED, Room.HousekeepingStatus.DIRTY, "720.00", "Deluxe Ocean View"),
        ("Labadi Beach Hotel", "203", 2, Room.RoomStatus.AVAILABLE, Room.HousekeepingStatus.CLEAN, "720.00", "Deluxe Ocean View"),
        ("Labadi Beach Hotel", "204", 2, Room.RoomStatus.AVAILABLE, Room.HousekeepingStatus.INSPECTED, "720.00", "Deluxe Ocean View"),
        ("Labadi Beach Hotel", "B01", 1, Room.RoomStatus.OCCUPIED, Room.HousekeepingStatus.DIRTY, "1200.00", "Beach Bungalow"),
        ("Labadi Beach Hotel", "B02", 1, Room.RoomStatus.AVAILABLE, Room.HousekeepingStatus.CLEAN, "1200.00", "Beach Bungalow"),
        ("Labadi Beach Hotel", "B03", 1, Room.RoomStatus.MAINTENANCE, Room.HousekeepingStatus.OUT_OF_SERVICE, "1200.00", "Beach Bungalow"),
        ("Labadi Beach Hotel", "S01", 3, Room.RoomStatus.OCCUPIED, Room.HousekeepingStatus.DIRTY, "1950.00", "Executive Suite"),
        ("Labadi Beach Hotel", "S02", 3, Room.RoomStatus.AVAILABLE, Room.HousekeepingStatus.INSPECTED, "1950.00", "Executive Suite"),
        ("Labadi Beach Hotel", "S03", 3, Room.RoomStatus.RESERVED, Room.HousekeepingStatus.CLEAN, "1950.00", "Executive Suite"),
        # Elmina — floors 1-2
        ("Elmina Beach Resort", "101", 1, Room.RoomStatus.OCCUPIED, Room.HousekeepingStatus.DIRTY, "380.00", "Heritage Room"),
        ("Elmina Beach Resort", "102", 1, Room.RoomStatus.AVAILABLE, Room.HousekeepingStatus.CLEAN, "380.00", "Heritage Room"),
        ("Elmina Beach Resort", "103", 1, Room.RoomStatus.AVAILABLE, Room.HousekeepingStatus.INSPECTED, "380.00", "Heritage Room"),
        ("Elmina Beach Resort", "104", 1, Room.RoomStatus.RESERVED, Room.HousekeepingStatus.CLEAN, "380.00", "Heritage Room"),
        ("Elmina Beach Resort", "C01", 1, Room.RoomStatus.OCCUPIED, Room.HousekeepingStatus.DIRTY, "650.00", "Ocean Chalet"),
        ("Elmina Beach Resort", "C02", 1, Room.RoomStatus.AVAILABLE, Room.HousekeepingStatus.CLEAN, "650.00", "Ocean Chalet"),
        ("Elmina Beach Resort", "C03", 1, Room.RoomStatus.OCCUPIED, Room.HousekeepingStatus.DIRTY, "650.00", "Ocean Chalet"),
        ("Elmina Beach Resort", "C04", 1, Room.RoomStatus.MAINTENANCE, Room.HousekeepingStatus.OUT_OF_SERVICE, "650.00", "Ocean Chalet"),
        ("Elmina Beach Resort", "F01", 2, Room.RoomStatus.OCCUPIED, Room.HousekeepingStatus.DIRTY, "950.00", "Family Suite"),
        ("Elmina Beach Resort", "F02", 2, Room.RoomStatus.AVAILABLE, Room.HousekeepingStatus.CLEAN, "950.00", "Family Suite"),
        ("Elmina Beach Resort", "F03", 2, Room.RoomStatus.RESERVED, Room.HousekeepingStatus.INSPECTED, "950.00", "Family Suite"),
        ("Elmina Beach Resort", "F04", 2, Room.RoomStatus.AVAILABLE, Room.HousekeepingStatus.CLEAN, "950.00", "Family Suite"),
    ]

    # ── SECTION 7 — RESERVATIONS ─────────────────────────────────────────
    # (guest_email, hotel_name, check_in, check_out, actual_check_in,
    #  actual_check_out, status, booking_date)
    reservations = [
        ("kwame.mensah@gmail.com", "Kempinski Hotel Gold Coast City",
         "2025-07-15 14:00:00", "2025-07-20 11:00:00", "2025-07-15 15:30:00", None,
         Reservation.ReservationStatus.CHECKED_IN, "2025-07-01 10:00:00"),
        ("sarah.mitchell@email.com", "Kempinski Hotel Gold Coast City",
         "2025-07-16 14:00:00", "2025-07-19 11:00:00", "2025-07-16 14:45:00", None,
         Reservation.ReservationStatus.CHECKED_IN, "2025-07-03 14:00:00"),
        ("emma.williams@email.co.uk", "Kempinski Hotel Gold Coast City",
         "2025-07-17 14:00:00", "2025-07-22 11:00:00", "2025-07-17 13:55:00", None,
         Reservation.ReservationStatus.CHECKED_IN, "2025-07-05 09:00:00"),
        ("jp.dubois@email.fr", "Kempinski Hotel Gold Coast City",
         "2025-07-18 14:00:00", "2025-07-21 11:00:00", "2025-07-18 16:00:00", None,
         Reservation.ReservationStatus.CHECKED_IN, "2025-07-06 11:00:00"),
        ("abena.boateng@gmail.com", "Kempinski Hotel Gold Coast City",
         "2025-07-21 14:00:00", "2025-07-25 11:00:00", None, None,
         Reservation.ReservationStatus.CONFIRMED, "2025-07-10 16:00:00"),
        ("yaw.frimpong@yahoo.com", "Kempinski Hotel Gold Coast City",
         "2025-07-22 14:00:00", "2025-07-26 11:00:00", None, None,
         Reservation.ReservationStatus.CONFIRMED, "2025-07-12 10:00:00"),
        ("akosua.gyamfi@gmail.com", "Kempinski Hotel Gold Coast City",
         "2025-07-28 14:00:00", "2025-07-30 11:00:00", None, None,
         Reservation.ReservationStatus.PENDING, "2025-07-15 09:30:00"),
        ("kofi.agyei@outlook.com", "Kempinski Hotel Gold Coast City",
         "2025-07-10 14:00:00", "2025-07-14 11:00:00", "2025-07-10 15:00:00", "2025-07-14 10:30:00",
         Reservation.ReservationStatus.CHECKED_OUT, "2025-06-25 11:00:00"),
        ("amara.diallo@email.sn", "Kempinski Hotel Gold Coast City",
         "2025-07-08 14:00:00", "2025-07-12 11:00:00", "2025-07-08 14:30:00", "2025-07-12 11:00:00",
         Reservation.ReservationStatus.CHECKED_OUT, "2025-06-28 09:00:00"),
        ("adwoa.asiedu@gmail.com", "Kempinski Hotel Gold Coast City",
         "2025-07-20 14:00:00", "2025-07-23 11:00:00", None, None,
         Reservation.ReservationStatus.CANCELLED, "2025-07-05 13:00:00"),
        ("kweku.antwi@gmail.com", "Labadi Beach Hotel",
         "2025-07-15 14:00:00", "2025-07-18 11:00:00", "2025-07-15 14:30:00", None,
         Reservation.ReservationStatus.CHECKED_IN, "2025-07-02 10:00:00"),
        ("james.okafor@gmail.com", "Labadi Beach Hotel",
         "2025-07-16 14:00:00", "2025-07-20 11:00:00", "2025-07-16 15:00:00", None,
         Reservation.ReservationStatus.CHECKED_IN, "2025-07-04 14:00:00"),
        ("efua.appiah@yahoo.com", "Labadi Beach Hotel",
         "2025-07-17 14:00:00", "2025-07-19 11:00:00", "2025-07-17 14:15:00", None,
         Reservation.ReservationStatus.CHECKED_IN, "2025-07-06 09:00:00"),
        ("nana.owusu@gmail.com", "Labadi Beach Hotel",
         "2025-07-22 14:00:00", "2025-07-27 11:00:00", None, None,
         Reservation.ReservationStatus.CONFIRMED, "2025-07-11 16:00:00"),
        ("fiifi.nyarko@gmail.com", "Labadi Beach Hotel",
         "2025-07-09 14:00:00", "2025-07-13 11:00:00", "2025-07-09 14:00:00", "2025-07-13 10:45:00",
         Reservation.ReservationStatus.CHECKED_OUT, "2025-06-29 09:00:00"),
        ("kwame.mensah@gmail.com", "Elmina Beach Resort",
         "2025-07-15 14:00:00", "2025-07-20 11:00:00", "2025-07-15 15:00:00", None,
         Reservation.ReservationStatus.CHECKED_IN, "2025-07-03 11:00:00"),
        ("abena.boateng@gmail.com", "Elmina Beach Resort",
         "2025-07-16 14:00:00", "2025-07-18 11:00:00", "2025-07-16 14:30:00", None,
         Reservation.ReservationStatus.CHECKED_IN, "2025-07-05 14:00:00"),
        ("yaw.frimpong@yahoo.com", "Elmina Beach Resort",
         "2025-07-18 14:00:00", "2025-07-22 11:00:00", "2025-07-18 14:00:00", None,
         Reservation.ReservationStatus.CHECKED_IN, "2025-07-07 10:00:00"),
        ("akosua.gyamfi@gmail.com", "Elmina Beach Resort",
         "2025-07-21 14:00:00", "2025-07-25 11:00:00", None, None,
         Reservation.ReservationStatus.CONFIRMED, "2025-07-12 09:00:00"),
        ("emma.williams@email.co.uk", "Elmina Beach Resort",
         "2025-07-07 14:00:00", "2025-07-11 11:00:00", "2025-07-07 14:00:00", "2025-07-11 10:30:00",
         Reservation.ReservationStatus.CHECKED_OUT, "2025-06-27 15:00:00"),
    ]

    # ── SECTION 8 — ROOM RESERVATIONS (junction table) ───────────────────
    # (reservation index in `reservations`, hotel_name, room_number)
    room_reservations = [
        (1, "Kempinski Hotel Gold Coast City", "101"),
        (2, "Kempinski Hotel Gold Coast City", "201"),
        (3, "Kempinski Hotel Gold Coast City", "301"),
        (4, "Kempinski Hotel Gold Coast City", "401"),
        (5, "Kempinski Hotel Gold Coast City", "104"),
        (6, "Kempinski Hotel Gold Coast City", "303"),
        (7, "Kempinski Hotel Gold Coast City", "203"),
        (8, "Kempinski Hotel Gold Coast City", "102"),
        (9, "Kempinski Hotel Gold Coast City", "202"),
        (11, "Labadi Beach Hotel", "101"),
        (12, "Labadi Beach Hotel", "201"),
        (13, "Labadi Beach Hotel", "B01"),
        (14, "Labadi Beach Hotel", "104"),
        (15, "Labadi Beach Hotel", "102"),
        (16, "Elmina Beach Resort", "101"),
        (17, "Elmina Beach Resort", "C01"),
        (18, "Elmina Beach Resort", "C03"),
        (19, "Elmina Beach Resort", "F01"),
        (20, "Elmina Beach Resort", "103"),
    ]

    # ── SECTION 9 — INVOICES ─────────────────────────────────────────────
    # (reservation index, total_amount, issue_date, status)
    invoices = [
        (1, "4590.00", "2025-07-15 15:30:00", Invoice.InvoiceStatus.PARTIAL),
        (2, "3300.00", "2025-07-16 14:45:00", Invoice.InvoiceStatus.UNPAID),
        (3, "9000.00", "2025-07-17 13:55:00", Invoice.InvoiceStatus.PAID),
        (4, "13500.00", "2025-07-18 16:00:00", Invoice.InvoiceStatus.UNPAID),
        (5, "3400.00", "2025-07-10 16:00:00", Invoice.InvoiceStatus.UNPAID),
        (6, "7200.00", "2025-07-12 10:00:00", Invoice.InvoiceStatus.UNPAID),
        (8, "3400.00", "2025-07-10 15:00:00", Invoice.InvoiceStatus.PAID),
        (9, "4400.00", "2025-07-08 14:30:00", Invoice.InvoiceStatus.PAID),
        (11, "1440.00", "2025-07-15 14:30:00", Invoice.InvoiceStatus.PARTIAL),
        (12, "2880.00", "2025-07-16 15:00:00", Invoice.InvoiceStatus.UNPAID),
        (13, "2400.00", "2025-07-17 14:15:00", Invoice.InvoiceStatus.PAID),
        (14, "2400.00", "2025-07-11 16:00:00", Invoice.InvoiceStatus.UNPAID),
        (15, "1920.00", "2025-07-09 14:00:00", Invoice.InvoiceStatus.PAID),
        (16, "1900.00", "2025-07-15 15:00:00", Invoice.InvoiceStatus.PARTIAL),
        (17, "1300.00", "2025-07-16 14:30:00", Invoice.InvoiceStatus.PAID),
        (18, "2600.00", "2025-07-18 14:00:00", Invoice.InvoiceStatus.UNPAID),
        (19, "3800.00", "2025-07-12 09:00:00", Invoice.InvoiceStatus.UNPAID),
        (20, "1520.00", "2025-07-07 14:00:00", Invoice.InvoiceStatus.PAID),
    ]

    # ── SECTION 10 — PAYMENTS ────────────────────────────────────────────
    # (invoice reservation index, amount, method, status, provider_reference,
    #  provider_response, payment_date)
    payments = [
        (1, "2000.00", Payment.PaymentMethod.MOBILE_MONEY, Payment.PaymentStatus.SUCCESS,
         "MTN-PAY-20250715-001",
         {"network": "MTN", "phone": "+233244123001", "status": "success"},
         "2025-07-15 16:00:00"),
        (3, "9000.00", Payment.PaymentMethod.CARD, Payment.PaymentStatus.SUCCESS,
         "CARD-VISA-20250717-001",
         {"card_type": "VISA", "last4": "4242", "status": "success"},
         "2025-07-17 14:00:00"),
        (8, "3400.00", Payment.PaymentMethod.MOBILE_MONEY, Payment.PaymentStatus.SUCCESS,
         "VOD-PAY-20250710-001",
         {"network": "Vodafone", "phone": "+233244123005", "status": "success"},
         "2025-07-14 09:00:00"),
        (9, "4400.00", Payment.PaymentMethod.CASH, Payment.PaymentStatus.SUCCESS,
         None, None, "2025-07-12 10:00:00"),
        (11, "700.00", Payment.PaymentMethod.CASH, Payment.PaymentStatus.SUCCESS,
         None, None, "2025-07-15 15:00:00"),
        (13, "2400.00", Payment.PaymentMethod.PAYSTACK, Payment.PaymentStatus.SUCCESS,
         "PSK-REF-20250717-78901",
         {"reference": "PSK-REF-20250717-78901", "status": "success", "amount": 240000, "currency": "GHS"},
         "2025-07-17 14:20:00"),
        (15, "1920.00", Payment.PaymentMethod.CASH, Payment.PaymentStatus.SUCCESS,
         None, None, "2025-07-13 10:00:00"),
        (16, "1000.00", Payment.PaymentMethod.MOBILE_MONEY, Payment.PaymentStatus.SUCCESS,
         "MTN-PAY-20250715-002",
         {"network": "MTN", "phone": "+233244123001", "status": "success"},
         "2025-07-15 15:30:00"),
        (17, "1300.00", Payment.PaymentMethod.CARD, Payment.PaymentStatus.SUCCESS,
         "CARD-MAST-20250716-002",
         {"card_type": "Mastercard", "last4": "5555", "status": "success"},
         "2025-07-16 15:00:00"),
        (20, "1520.00", Payment.PaymentMethod.CASH, Payment.PaymentStatus.SUCCESS,
         None, None, "2025-07-11 10:00:00"),
        (12, "2880.00", Payment.PaymentMethod.PAYSTACK, Payment.PaymentStatus.PENDING,
         "PSK-REF-20250718-99001",
         {"reference": "PSK-REF-20250718-99001", "status": "pending"},
         "2025-07-18 09:00:00"),
    ]

    # ── SECTION 11 — SERVICES ────────────────────────────────────────────
    # (hotel_name, service_name, price, category)
    services = [
        ("Kempinski Hotel Gold Coast City", "In-Room Dining", "85.00", "Food"),
        ("Kempinski Hotel Gold Coast City", "Laundry & Pressing", "60.00", "Housekeeping"),
        ("Kempinski Hotel Gold Coast City", "Airport Transfer (Accra)", "200.00", "Transport"),
        ("Kempinski Hotel Gold Coast City", "Spa Treatment (60 min)", "350.00", "Wellness"),
        ("Kempinski Hotel Gold Coast City", "Business Centre Access", "50.00", "Business"),
        ("Kempinski Hotel Gold Coast City", "Extra Toiletries", "20.00", "Housekeeping"),
        ("Kempinski Hotel Gold Coast City", "Babysitting Service", "120.00", "Family"),
        ("Kempinski Hotel Gold Coast City", "Dry Cleaning", "80.00", "Housekeeping"),
        ("Labadi Beach Hotel", "Beach Bar Tab", "45.00", "Food"),
        ("Labadi Beach Hotel", "Surfboard Rental", "80.00", "Recreation"),
        ("Labadi Beach Hotel", "Beach Bonfire Setup", "250.00", "Recreation"),
        ("Labadi Beach Hotel", "Laundry", "50.00", "Housekeeping"),
        ("Labadi Beach Hotel", "Airport Transfer (Accra)", "180.00", "Transport"),
        ("Labadi Beach Hotel", "Snorkelling Gear Rental", "60.00", "Recreation"),
        ("Elmina Beach Resort", "Castle Tour Package", "120.00", "Tourism"),
        ("Elmina Beach Resort", "Fishing Excursion", "200.00", "Recreation"),
        ("Elmina Beach Resort", "Local Cuisine Tasting", "90.00", "Food"),
        ("Elmina Beach Resort", "Laundry", "40.00", "Housekeeping"),
        ("Elmina Beach Resort", "Cape Coast Day Trip", "250.00", "Tourism"),
        ("Elmina Beach Resort", "Canoe Rental", "70.00", "Recreation"),
    ]

    # ── SECTION 12 — SERVICE REQUESTS ────────────────────────────────────
    # (reservation index, service_name, staff_email, request_time, status)
    service_requests = [
        (1, "In-Room Dining", "hk1@kempinski-accra.com", "2025-07-16 08:30:00", ServiceRequest.RequestStatus.COMPLETED),
        (1, "Laundry & Pressing", "hk1@kempinski-accra.com", "2025-07-16 10:00:00", ServiceRequest.RequestStatus.COMPLETED),
        (2, "In-Room Dining", "hk2@kempinski-accra.com", "2025-07-17 07:45:00", ServiceRequest.RequestStatus.IN_PROGRESS),
        (3, "Spa Treatment (60 min)", None, "2025-07-17 09:00:00", ServiceRequest.RequestStatus.PENDING),
        (4, "Airport Transfer (Accra)", None, "2025-07-18 11:00:00", ServiceRequest.RequestStatus.PENDING),
        (1, "Dry Cleaning", "hk1@kempinski-accra.com", "2025-07-18 08:00:00", ServiceRequest.RequestStatus.IN_PROGRESS),
        (11, "Beach Bar Tab", "hk1@labadibeach.com", "2025-07-15 09:00:00", ServiceRequest.RequestStatus.COMPLETED),
        (12, "Surfboard Rental", "hk1@labadibeach.com", "2025-07-16 10:30:00", ServiceRequest.RequestStatus.IN_PROGRESS),
        (13, "Laundry", None, "2025-07-17 08:00:00", ServiceRequest.RequestStatus.PENDING),
        (16, "Castle Tour Package", "hk1@elminabeach.com", "2025-07-15 09:30:00", ServiceRequest.RequestStatus.COMPLETED),
        (17, "Fishing Excursion", "hk1@elminabeach.com", "2025-07-16 10:00:00", ServiceRequest.RequestStatus.IN_PROGRESS),
        (18, "Cape Coast Day Trip", None, "2025-07-18 11:00:00", ServiceRequest.RequestStatus.PENDING),
        (8, "In-Room Dining", "hk1@kempinski-accra.com", "2025-07-11 08:00:00", ServiceRequest.RequestStatus.COMPLETED),
        (9, "Airport Transfer (Accra)", "hk1@kempinski-accra.com", "2025-07-10 09:00:00", ServiceRequest.RequestStatus.COMPLETED),
        (15, "Laundry", "hk1@labadibeach.com", "2025-07-10 10:00:00", ServiceRequest.RequestStatus.COMPLETED),
        (20, "Castle Tour Package", "hk1@elminabeach.com", "2025-07-08 14:00:00", ServiceRequest.RequestStatus.COMPLETED),
    ]

    # ── SECTION 13 — FEEDBACK ────────────────────────────────────────────
    # (guest_email, reservation index, rating, comments, date)
    # NOTE: the SQL's 5th feedback row duplicated (guest 13, resv 20) which the
    # model forbids (unique_together), so only 4 reviews are created.
    feedback = [
        ("kofi.agyei@outlook.com", 8, 5,
         "Exceptional service throughout our stay. The staff, especially at the front desk, were incredibly professional and warm. The room was spotless and the view of Accra at night was breathtaking. Will definitely return.",
         "2025-07-14 14:00:00"),
        ("amara.diallo@email.sn", 9, 4,
         "Very comfortable stay at the Kempinski. Breakfast was outstanding — fresh local fruits and international options. The only minor issue was the air conditioning in our room was a bit loud at night.",
         "2025-07-12 12:00:00"),
        ("fiifi.nyarko@gmail.com", 15, 5,
         "Labadi Beach Hotel exceeded all expectations! Waking up to the sound of the Atlantic was magical. The beach bungalow was pristine and the staff were so friendly. The Ghanaian cuisine at the restaurant was authentic and delicious.",
         "2025-07-13 11:00:00"),
        ("emma.williams@email.co.uk", 20, 5,
         "The Elmina Beach Resort is a hidden gem. Staying so close to the historic Elmina Castle was surreal. The staff arranged an incredible guided tour for us. The ocean chalet with the hammock on the deck was absolutely perfect.",
         "2025-07-11 15:00:00"),
    ]

    # ── SECTION 14 — MAINTENANCE ─────────────────────────────────────────
    # (hotel_name, room_number, issue, report_date, resolve_date, status, staff_email)
    maintenance = [
        ("Kempinski Hotel Gold Coast City", "204",
         "Air conditioning unit making loud grinding noise. Guest in room 204 complained at 11pm. AC was switched off and guest moved to room 207.",
         "2025-07-16", None, Maintenance.MaintenanceStatus.OPEN, "maintenance1@kempinski-accra.com"),
        ("Kempinski Hotel Gold Coast City", "403",
         "Bathroom shower tile cracked along the south wall. Non-urgent — flagged during routine housekeeping inspection.",
         "2025-07-14", None, Maintenance.MaintenanceStatus.IN_PROGRESS, "maintenance1@kempinski-accra.com"),
        ("Kempinski Hotel Gold Coast City", "103",
         "TV remote control not pairing with smart TV. Batteries replaced but issue persists. New remote ordered.",
         "2025-07-13", "2025-07-15", Maintenance.MaintenanceStatus.RESOLVED, "maintenance1@kempinski-accra.com"),
        ("Kempinski Hotel Gold Coast City", "301",
         "Minibar refrigerator not cooling. Compressor issue suspected. Unit replaced with spare from stores.",
         "2025-07-10", "2025-07-11", Maintenance.MaintenanceStatus.CLOSED, "maintenance1@kempinski-accra.com"),
        ("Kempinski Hotel Gold Coast City", "401",
         "Wardrobe door hinge broken. Door hanging and cannot close properly. Carpenter called.",
         "2025-07-17", None, Maintenance.MaintenanceStatus.OPEN, "maintenance1@kempinski-accra.com"),
        ("Labadi Beach Hotel", "B03",
         "Beach bungalow B03 roof leak detected after last night rainfall. Water dripping near the bathroom area. Guest relocated to B02.",
         "2025-07-16", None, Maintenance.MaintenanceStatus.IN_PROGRESS, "maintenance1@labadibeach.com"),
        ("Labadi Beach Hotel", "101",
         "Swimming pool pump pressure low. Pool depth reducing. Technical team contacted.",
         "2025-07-15", None, Maintenance.MaintenanceStatus.OPEN, "maintenance1@labadibeach.com"),
        ("Labadi Beach Hotel", "202",
         "Room 202 bathroom sink drain blocked. Plumber attended and cleared blockage with drain snake.",
         "2025-07-12", "2025-07-13", Maintenance.MaintenanceStatus.CLOSED, "maintenance1@labadibeach.com"),
        ("Elmina Beach Resort", "C04",
         "Ocean chalet C04 outdoor deck has loose planks creating a safety hazard. Roped off until carpenter repairs.",
         "2025-07-15", None, Maintenance.MaintenanceStatus.OPEN, "maintenance1@elminabeach.com"),
        ("Elmina Beach Resort", "F01",
         "Family suite F01 water heater not working. Cold water only. Guest affected — discount offered on bill.",
         "2025-07-17", None, Maintenance.MaintenanceStatus.IN_PROGRESS, "maintenance1@elminabeach.com"),
        ("Elmina Beach Resort", "101",
         "Generator fuel line inspection required. Minor fuel smell detected near the back of the resort. Preventive check carried out.",
         "2025-07-10", "2025-07-11", Maintenance.MaintenanceStatus.RESOLVED, "maintenance1@elminabeach.com"),
    ]

    # ── SECTION 15 — NOTIFICATIONS ───────────────────────────────────────
    # (staff_email, notification_type, message, is_read, created_at)
    notifications = [
        ("admin@stayhub.com", Notification.NotificationType.USER_CREATED,
         "New staff account created: Ama Boateng (Receptionist) at Kempinski Hotel Gold Coast City.",
         True, "2024-02-01 08:05:00"),
        ("manager@kempinski-accra.com", Notification.NotificationType.BOOKING_CREATED,
         "New reservation #1 created for Kwame Asante Mensah — Kempinski Hotel, 5 nights from 15 Jul 2025.",
         False, "2025-07-01 10:05:00"),
        ("manager@kempinski-accra.com", Notification.NotificationType.BOOKING_CREATED,
         "New reservation #2 created for Sarah Mitchell — Kempinski Hotel, 3 nights from 16 Jul 2025.",
         True, "2025-07-03 14:05:00"),
        ("accounts@kempinski-accra.com", Notification.NotificationType.PAYMENT_RECEIVED,
         "Payment of GHS 2,000.00 received via MTN Mobile Money for Invoice #1 (Kwame Asante Mensah).",
         False, "2025-07-15 16:05:00"),
        ("accounts@kempinski-accra.com", Notification.NotificationType.PAYMENT_RECEIVED,
         "Full payment of GHS 9,000.00 received via Visa Card for Invoice #3 (Emma Williams).",
         True, "2025-07-17 14:05:00"),
        ("reception1@kempinski-accra.com", Notification.NotificationType.BOOKING_CANCELLED,
         "Reservation #10 for Adwoa Serwaa Asiedu has been cancelled. Room 104 is now available.",
         True, "2025-07-05 13:10:00"),
        ("manager@kempinski-accra.com", Notification.NotificationType.LOGIN_SUCCESS,
         "Manager Akua Mensah logged in successfully from IP 197.255.64.12 at 08:15.",
         True, "2025-07-18 08:15:00"),
        ("manager@kempinski-accra.com", Notification.NotificationType.LOGIN_FAILED,
         "Failed login attempt for username \"manager.kempinski\" from IP 41.66.132.88. Attempt 1 of 3.",
         False, "2025-07-17 23:44:00"),
        ("accounts@labadibeach.com", Notification.NotificationType.PAYMENT_RECEIVED,
         "Paystack payment of GHS 2,400.00 confirmed for Invoice #11 (Efua Kyei Appiah). Reference: PSK-REF-20250717-78901.",
         True, "2025-07-17 14:25:00"),
        ("manager@elminabeach.com", Notification.NotificationType.BOOKING_CREATED,
         "New reservation #16 created for Kwame Asante Mensah — Elmina Beach Resort, 5 nights from 15 Jul 2025.",
         False, "2025-07-03 11:05:00"),
        ("admin@stayhub.com", Notification.NotificationType.USER_CREATED,
         "New staff account created: Afia Mensah (Receptionist) at Elmina Beach Resort.",
         True, "2024-03-15 08:10:00"),
        ("accounts@elminabeach.com", Notification.NotificationType.PAYMENT_RECEIVED,
         "Full payment of GHS 1,300.00 received via Mastercard for Invoice #15 (Abena Osei Boateng at Elmina).",
         False, "2025-07-16 15:05:00"),
        ("manager@elminabeach.com", Notification.NotificationType.BOOKING_CREATED,
         "New reservation #19 created for Akosua Ama Gyamfi — Elmina Beach Resort, Family Suite, 4 nights.",
         False, "2025-07-12 09:05:00"),
        ("reception1@labadibeach.com", Notification.NotificationType.LOGIN_SUCCESS,
         "Receptionist Adwoa Kyei logged in from IP 154.160.5.200 at 06:55.",
         True, "2025-07-18 06:55:00"),
        ("manager@labadibeach.com", Notification.NotificationType.PASSWORD_CHANGED,
         "Password for account manager.labadi was changed successfully.",
         True, "2025-07-10 09:00:00"),
    ]

    def _upsert_staff(self, username, email, first_name, last_name, staff_name,
                      phone, role, department, hotel, is_superuser, password):
        """Update-or-create a staff member keyed on email (safe against duplicates)."""
        fields = dict(
            username=username, first_name=first_name, last_name=last_name,
            staff_name=staff_name, staff_phone=phone, role=role,
            department=department, hotel=hotel, is_superuser=is_superuser,
            is_staff=is_superuser, is_active=True,
            password=make_password(password),
        )
        existing = Staff.objects.filter(email=email).first()
        if existing:
            for key, value in fields.items():
                setattr(existing, key, value)
            existing.save()
            return existing, False
        return Staff.objects.create(email=email, **fields), True

    @transaction.atomic
    def handle(self, *args, **options):
        self.stdout.write(self.style.MIGRATE_HEADING("Seeding full StayHub demo dataset…"))

        # ── 1. Hotels ─────────────────────────────────────────────────────
        hotels = {}
        for name, email, address, phone, category, created in self.hotels:
            hotel, _ = Hotel.objects.update_or_create(
                hotel_email=email,
                defaults={"hotel_name": name, "hotel_address": address,
                          "hotel_phone": phone, "category": category},
            )
            stamp(Hotel, hotel, created_at=dt(created))
            hotels[name] = hotel

        # ── 2. Departments ────────────────────────────────────────────────
        for hotel_name, dept_name in self.departments:
            Department.objects.get_or_create(hotel=hotels[hotel_name], dept_name=dept_name)

        # ── 3. Staff ──────────────────────────────────────────────────────
        staff_by_email = {}
        for (username, email, first, last, full_name, phone, role,
             dept_name, hotel_name, is_super) in self.staff:
            staff, created = self._upsert_staff(
                username, email, first, last, full_name, phone, role,
                hotels[hotel_name].departments.filter(dept_name=dept_name).first() if dept_name else None,
                hotels[hotel_name] if hotel_name else None,
                is_super, self.staff_passwords[role],
            )
            if created:
                # Only stamp NEW staff so merge mode never clobbers existing
                # accounts' hired_at / date_joined timestamps.
                stamp(Staff, staff, hired_at=dt(self.staff_hired_at[email]),
                      date_joined=dt(self.staff_hired_at[email]))
                staff_by_email[email] = staff
                self.stdout.write(self.style.SUCCESS(f"  Created staff: {full_name} ({role}) — {email}"))
            else:
                staff_by_email[email] = staff

        # ── 4. Guests ─────────────────────────────────────────────────────
        guests = {}
        for name, phone, email, id_number, nationality, created in self.guests:
            guest, _ = Guest.objects.update_or_create(
                guest_email=email,
                defaults={"guest_name": name, "guest_phone": phone,
                          "id_number": id_number, "nationality": nationality},
            )
            stamp(Guest, guest, created_at=dt(created))
            guests[email] = guest

        # ── 5. Room types ─────────────────────────────────────────────────
        types = {}
        for hotel_name, type_name, price, description in self.room_types:
            room_type, _ = RoomType.objects.update_or_create(
                hotel=hotels[hotel_name], type_name=type_name,
                defaults={"price_per_night": price, "description": description},
            )
            types[(hotel_name, type_name)] = room_type

        # ── 6. Rooms ──────────────────────────────────────────────────────
        rooms = {}
        for (hotel_name, room_number, floor, status, hk_status,
             price, type_name) in self.rooms:
            room, _ = Room.objects.update_or_create(
                hotel=hotels[hotel_name], room_number=room_number,
                defaults={"room_type": types[(hotel_name, type_name)],
                          "floor": floor, "status": status,
                          "housekeeping_status": hk_status,
                          "price_per_night": price},
            )
            rooms[(hotel_name, room_number)] = room

        # ── 7. Reservations ───────────────────────────────────────────────
        reservations = {}
        for index, (guest_email, hotel_name, check_in, check_out,
                    actual_in, actual_out, status, booked) in enumerate(self.reservations, start=1):
            resv, _ = Reservation.objects.get_or_create(
                guest=guests[guest_email], hotel=hotels[hotel_name],
                check_in=dt(check_in), check_out=dt(check_out),
                defaults={"status": status},
            )
            resv.status = status
            resv.actual_check_in = dt(actual_in) if actual_in else None
            resv.actual_check_out = dt(actual_out) if actual_out else None
            resv.save()
            stamp(Reservation, resv, booking_date=dt(booked))
            reservations[index] = resv

        # ── 8. Room reservations ──────────────────────────────────────────
        for resv_index, hotel_name, room_number in self.room_reservations:
            RoomReservation.objects.get_or_create(
                resv=reservations[resv_index], room=rooms[(hotel_name, room_number)],
            )

        # ── 9. Invoices ───────────────────────────────────────────────────
        invoices = {}
        for resv_index, total, issued, status in self.invoices:
            invoice, _ = Invoice.objects.update_or_create(
                reservation=reservations[resv_index],
                defaults={"hotel": reservations[resv_index].hotel,
                          "total_amount": total, "status": status},
            )
            stamp(Invoice, invoice, issue_date=dt(issued))
            invoices[resv_index] = invoice

        # ── 10. Payments ──────────────────────────────────────────────────
        for resv_index, amount, method, status, ref, response, paid in self.payments:
            invoice = invoices[resv_index]
            payment, _ = Payment.objects.get_or_create(
                invoice=invoice, amount=amount, method=method,
                defaults={"status": status, "provider_reference": ref,
                          "provider_response": response,
                          "hotel": invoice.hotel},
            )
            Payment.objects.filter(pk=payment.pk).update(
                status=status, provider_reference=ref,
                provider_response=response,
            )
            stamp(Payment, payment, payment_date=dt(paid))

        # ── 11. Services ──────────────────────────────────────────────────
        services = {}
        for hotel_name, service_name, price, category in self.services:
            service, _ = Service.objects.update_or_create(
                hotel=hotels[hotel_name], service_name=service_name,
                defaults={"price": price, "category": category},
            )
            services[(hotel_name, service_name)] = service

        # ── 12. Service requests ──────────────────────────────────────────
        for resv_index, service_name, staff_email, requested, status in self.service_requests:
            resv = reservations[resv_index]
            service = services[(resv.hotel.hotel_name, service_name)]
            request, _ = ServiceRequest.objects.get_or_create(
                resv=resv, service=service,
                defaults={"status": status,
                          "staff": staff_by_email.get(staff_email)},
            )
            ServiceRequest.objects.filter(pk=request.pk).update(
                status=status, staff=staff_by_email.get(staff_email),
            )
            stamp(ServiceRequest, request, request_time=dt(requested))

        # ── 13. Feedback ──────────────────────────────────────────────────
        for guest_email, resv_index, rating, comments, submitted in self.feedback:
            resv = reservations[resv_index]
            feedback, _ = Feedback.objects.get_or_create(
                guest=guests[guest_email], resv=resv,
                defaults={"hotel": resv.hotel, "rating": rating, "comments": comments},
            )
            stamp(Feedback, feedback, date=dt(submitted))

        # ── 14. Maintenance ───────────────────────────────────────────────
        for hotel_name, room_number, issue, reported, resolved, status, staff_email in self.maintenance:
            room = rooms[(hotel_name, room_number)]
            task, _ = Maintenance.objects.get_or_create(
                room=room, issue=issue,
                defaults={"hotel": hotels[hotel_name], "status": status,
                          "staff": staff_by_email.get(staff_email)},
            )
            Maintenance.objects.filter(pk=task.pk).update(
                status=status, staff=staff_by_email.get(staff_email),
                resolve_date=resolved,
            )
            stamp(Maintenance, task, report_date=dt(reported + " 00:00:00").date())

        # ── 15. Notifications ─────────────────────────────────────────────
        for email, ntype, message, is_read, created in self.notifications:
            note, _ = Notification.objects.get_or_create(
                user=staff_by_email[email], notification_type=ntype, message=message,
                defaults={"is_read": is_read},
            )
            stamp(Notification, note, created_at=dt(created))

        # ── Summary ───────────────────────────────────────────────────────
        counts = [
            ("Hotels", Hotel.objects.count()),
            ("Departments", Department.objects.count()),
            ("Staff", Staff.objects.count()),
            ("Guests", Guest.objects.count()),
            ("Room types", RoomType.objects.count()),
            ("Rooms", Room.objects.count()),
            ("Reservations", Reservation.objects.count()),
            ("Room reservations", RoomReservation.objects.count()),
            ("Invoices", Invoice.objects.count()),
            ("Payments", Payment.objects.count()),
            ("Services", Service.objects.count()),
            ("Service requests", ServiceRequest.objects.count()),
            ("Feedback", Feedback.objects.count()),
            ("Maintenance", Maintenance.objects.count()),
            ("Notifications", Notification.objects.count()),
        ]
        self.stdout.write(self.style.MIGRATE_HEADING("Dataset ready:"))
        for label, count in counts:
            self.stdout.write(f"  {label:<18} {count}")

        self.stdout.write(self.style.SUCCESS(
            "\nStaff passwords (per-role): admin123456 · manager123 · reception123 · "
            "accountant123 · housekeeping123\n"
            "Sample logins: admin@stayhub.com (admin) · manager@kempinski-accra.com "
            "(manager) · reception1@kempinski-accra.com (receptionist)"
        ))
