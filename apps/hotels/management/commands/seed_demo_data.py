from django.core.management.base import BaseCommand

from apps.hotels.models import Department, Hotel
from apps.rooms.models import Room, RoomType


class Command(BaseCommand):
    help = "Create realistic, repeatable Ghanaian hotel and room data for local development."

    def handle(self, *args, **options):
        hotels = [
            ("La Palm Royal Beach Hotel", "reservations@lapalm.example", "+233 30 277 2200", "Liberation Road, Accra"),
            ("Kempinski Hotel Gold Coast City", "stay@kempinski-accra.example", "+233 30 224 2000", "Gamel Abdul Nasser Avenue, Accra"),
            ("Royal Senchi Resort", "hello@royalsenchi.example", "+233 50 158 5000", "Senchi, Eastern Region"),
            ("Busua Beach Resort", "info@busuabeach.example", "+233 31 209 3580", "Busua, Western Region"),
            ("Mövenpick Ambassador Hotel Accra", "reservations@movenpick-accra.example", "+233 30 261 0600", "Independence Avenue, Accra"),
            ("Cape Coast Castle Hotel", "bookings@capecoast.example", "+233 33 209 0250", "Cape Coast, Central Region"),
        ]
        room_types = [
            ("Standard Room", "250.00", "A comfortable room with a queen bed, work desk, air conditioning, and city views. Perfect for business travellers."),
            ("Deluxe Room", "400.00", "Spacious room with a king bed, seating area, rainfall shower, premium amenities, and complimentary breakfast."),
            ("Ocean View Suite", "650.00", "Separate living room, private balcony overlooking the Atlantic Ocean, and a fully stocked minibar."),
            ("Executive Suite", "900.00", "A refined suite with lounge, dining table, airport transfer, concierge service, and executive lounge access."),
            ("Mansion Suite", "1400.00", "Premium two-bedroom suite with a kitchen, private dining, and butler service."),
            ("Beach Villa", "2200.00", "Private beachfront villa with a plunge pool, terrace, dedicated host, and full-board service."),
            ("Garden Cabin", "350.00", "Cosy cabin set in lush tropical gardens with a private verandah, ceiling fan, and outdoor shower."),
            ("Penthouse Suite", "3000.00", "Top-floor penthouse with panoramic views, wrap-around terrace, jacuzzi, and personal chef service."),
        ]
        created_hotels = 0
        created_rooms = 0
        hotel_objects = {}
        for name, email, phone, address in hotels:
            hotel, created = Hotel.objects.update_or_create(
                hotel_email=email,
                defaults={"hotel_name": name, "hotel_phone": phone, "hotel_address": address},
            )
            created_hotels += int(created)
            hotel_objects[name] = hotel
            for department_name in ("Front Office", "Housekeeping", "Food and Beverage"):
                Department.objects.get_or_create(hotel=hotel, dept_name=department_name)

        type_objects = {}
        for hotel_name, hotel in hotel_objects.items():
            for name, price, description in room_types:
                type_objects[(hotel_name, name)], _ = RoomType.objects.update_or_create(
                    hotel=hotel,
                    type_name=name,
                    defaults={"price_per_night": price, "description": description},
                )

        room_plan = {
            "La Palm Royal Beach Hotel": [
                ("101", "Standard Room", 1), ("102", "Standard Room", 1), ("103", "Standard Room", 1),
                ("201", "Deluxe Room", 2), ("202", "Deluxe Room", 2),
                ("301", "Ocean View Suite", 3), ("302", "Executive Suite", 3),
                ("401", "Beach Villa", 4),
            ],
            "Kempinski Hotel Gold Coast City": [
                ("501", "Standard Room", 5), ("502", "Standard Room", 5), ("503", "Standard Room", 5),
                ("601", "Deluxe Room", 6), ("602", "Deluxe Room", 6),
                ("701", "Executive Suite", 7), ("702", "Mansion Suite", 7),
                ("801", "Penthouse Suite", 8),
            ],
            "Royal Senchi Resort": [
                ("C01", "Garden Cabin", 0), ("C02", "Garden Cabin", 0), ("C03", "Garden Cabin", 0),
                ("R01", "Standard Room", 1), ("R02", "Deluxe Room", 1),
                ("S01", "Ocean View Suite", 2), ("S02", "Executive Suite", 2),
                ("V01", "Beach Villa", 0),
            ],
            "Busua Beach Resort": [
                ("B01", "Garden Cabin", 0), ("B02", "Garden Cabin", 0),
                ("101", "Standard Room", 1), ("102", "Standard Room", 1),
                ("201", "Ocean View Suite", 2), ("202", "Ocean View Suite", 2),
                ("301", "Beach Villa", 0),
            ],
            "Mövenpick Ambassador Hotel Accra": [
                ("1001", "Deluxe Room", 10), ("1002", "Deluxe Room", 10), ("1003", "Deluxe Room", 10),
                ("1101", "Executive Suite", 11), ("1102", "Executive Suite", 11),
                ("1201", "Mansion Suite", 12),
                ("1301", "Penthouse Suite", 13),
            ],
            "Cape Coast Castle Hotel": [
                ("01", "Standard Room", 0), ("02", "Standard Room", 0), ("03", "Standard Room", 0),
                ("04", "Deluxe Room", 0),
                ("05", "Ocean View Suite", 0),
                ("06", "Executive Suite", 0),
                ("07", "Beach Villa", 0),
            ],
        }
        unavailable = {
            ("Kempinski Hotel Gold Coast City", "702"): Room.RoomStatus.OCCUPIED,
            ("Busua Beach Resort", "B02"): Room.RoomStatus.MAINTENANCE,
            ("Royal Senchi Resort", "S01"): Room.RoomStatus.RESERVED,
        }
        for hotel_name, rooms in room_plan.items():
            hotel = Hotel.objects.get(hotel_name=hotel_name)
            for room_number, type_name, floor in rooms:
                room, created = Room.objects.update_or_create(
                    hotel=hotel,
                    room_number=room_number,
                    defaults={
                        "room_type": type_objects[(hotel_name, type_name)],
                        "price_per_night": type_objects[(hotel_name, type_name)].price_per_night,
                        "floor": floor,
                        "status": unavailable.get((hotel_name, room_number), Room.RoomStatus.AVAILABLE),
                        "housekeeping_status": Room.HousekeepingStatus.CLEAN,
                    },
                )
                created_rooms += int(created)
        self.stdout.write(self.style.SUCCESS(
            f"Demo data ready: {len(hotels)} hotels, {len(room_types)} room types, "
            f"{Room.objects.count()} rooms ({created_hotels} hotels and {created_rooms} rooms created)."
        ))