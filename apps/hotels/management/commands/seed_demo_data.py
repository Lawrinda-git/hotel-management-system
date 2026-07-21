from django.core.management.base import BaseCommand

from apps.hotels.models import Department, Hotel
from apps.rooms.models import Room, RoomType


class Command(BaseCommand):
    help = "Create realistic, repeatable hotel and room data for local development."

    def handle(self, *args, **options):
        hotels = [
            ("Azure Sands Resort", "reservations@azuresands.example", "+233 30 290 4100", "Baa Atoll, Maldives"),
            ("The Golden Palm Accra", "stay@goldenpalm.example", "+233 30 277 1840", "15 Independence Avenue, Accra"),
            ("Cape Coast Heritage Hotel", "hello@cape-heritage.example", "+233 24 601 8821", "Victoria Road, Cape Coast"),
        ]
        room_types = [
            ("Classic Room", "145.00", "A bright, comfortable room with a queen bed, work desk, and city views."),
            ("Deluxe King", "220.00", "Spacious king room with a sitting area, rainfall shower, and breakfast included."),
            ("Ocean View Suite", "380.00", "Separate living room, private balcony, and uninterrupted ocean views."),
            ("Family Residence", "460.00", "Two connected bedrooms with a kitchenette and space for up to four guests."),
            ("Executive Suite", "625.00", "A refined suite with lounge, dining table, airport transfer, and concierge service."),
            ("Presidential Villa", "1200.00", "Private villa with pool, terrace, dedicated host, and full-board service."),
        ]
        created_hotels = 0
        created_rooms = 0
        for name, email, phone, address in hotels:
            hotel, created = Hotel.objects.update_or_create(
                hotel_email=email,
                defaults={"hotel_name": name, "hotel_phone": phone, "hotel_address": address},
            )
            created_hotels += int(created)
            for department_name in ("Front Office", "Housekeeping", "Food and Beverage"):
                Department.objects.get_or_create(hotel=hotel, dept_name=department_name)

        type_objects = {}
        for name, price, description in room_types:
            type_objects[name], _ = RoomType.objects.update_or_create(
                type_name=name,
                defaults={"price_per_night": price, "description": description},
            )

        room_plan = {
            "Azure Sands Resort": [("101", "Ocean View Suite", 1), ("102", "Ocean View Suite", 1), ("201", "Executive Suite", 2), ("301", "Presidential Villa", 3)],
            "The Golden Palm Accra": [("110", "Classic Room", 1), ("111", "Classic Room", 1), ("210", "Deluxe King", 2), ("211", "Deluxe King", 2), ("310", "Family Residence", 3), ("311", "Executive Suite", 3)],
            "Cape Coast Heritage Hotel": [("05", "Classic Room", 0), ("06", "Classic Room", 0), ("12", "Deluxe King", 1), ("14", "Ocean View Suite", 1), ("20", "Family Residence", 2), ("21", "Executive Suite", 2)],
        }
        unavailable = {("Azure Sands Resort", "201"): Room.RoomStatus.RESERVED, ("The Golden Palm Accra", "211"): Room.RoomStatus.OCCUPIED, ("Cape Coast Heritage Hotel", "14"): Room.RoomStatus.MAINTENANCE}
        for hotel_name, rooms in room_plan.items():
            hotel = Hotel.objects.get(hotel_name=hotel_name)
            for room_number, type_name, floor in rooms:
                room, created = Room.objects.update_or_create(
                    hotel=hotel,
                    room_number=room_number,
                    defaults={
                        "room_type": type_objects[type_name],
                        "floor": floor,
                        "status": unavailable.get((hotel_name, room_number), Room.RoomStatus.AVAILABLE),
                        "housekeeping_status": Room.HousekeepingStatus.CLEAN,
                    },
                )
                created_rooms += int(created)
        self.stdout.write(self.style.SUCCESS(f"Demo data ready: {len(hotels)} hotels, {len(room_types)} room types, {Room.objects.count()} rooms ({created_hotels} hotels and {created_rooms} rooms created)."))
