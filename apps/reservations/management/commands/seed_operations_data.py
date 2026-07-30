from datetime import datetime, time, timedelta

from django.core.management.base import BaseCommand
from django.utils import timezone

from apps.billing.models import Invoice
from apps.guests.models import Guest
from apps.reservations.models import Reservation, RoomReservation
from apps.rooms.models import Maintenance, Room


class Command(BaseCommand):
    help = "Create repeatable reservations, invoices, and housekeeping records for dashboard development."

    def handle(self, *args, **options):
        today = timezone.localdate()
        tomorrow = today + timedelta(days=1)
        examples = [
            ("Ama Mensah", "ama.dashboard@example.com", "+233201111111", "GHA-123456789-0", today, tomorrow, "CHECKIN"),
            ("Kojo Boateng", "kojo.dashboard@example.com", "+233202222222", "GHA-223456789-1", today, today, "CHECKOUT"),
            ("Esi Owusu", "esi.dashboard@example.com", "+233203333333", "GHA-323456789-2", tomorrow, today + timedelta(days=3), "UPCOMING"),
        ]
        rooms = list(Room.objects.filter(status=Room.RoomStatus.AVAILABLE).select_related("hotel")[:3])
        if not rooms:
            self.stdout.write(self.style.WARNING("No available rooms found; run seed_demo_data first."))
            return

        for index, (name, email, phone, id_number, check_in_date, check_out_date, _) in enumerate(examples):
            guest, _ = Guest.objects.update_or_create(
                guest_email=email,
                defaults={"guest_name": name, "guest_phone": phone, "id_number": id_number, "nationality": "Ghana"},
            )
            room = rooms[index % len(rooms)]
            check_in = timezone.make_aware(datetime.combine(check_in_date, time(14, 0)))
            check_out = timezone.make_aware(datetime.combine(check_out_date, time(11, 0)))
            reservation, created = Reservation.objects.get_or_create(
                guest=guest,
                check_in=check_in,
                defaults={
                    "hotel": room.hotel,
                    "check_out": check_out,
                    "status": Reservation.ReservationStatus.CONFIRMED,
                },
            )
            RoomReservation.objects.get_or_create(resv=reservation, room=room)
            Invoice.objects.get_or_create(
                reservation=reservation,
                defaults={"hotel": room.hotel, "total_amount": room.price_per_night or 250},
            )
            if created:
                room.reservation = reservation
                room.status = Room.RoomStatus.RESERVED
                room.save(update_fields=["reservation", "status"])

        dirty_room = Room.objects.filter(housekeeping_status=Room.HousekeepingStatus.DIRTY).first()
        if dirty_room:
            Maintenance.objects.get_or_create(
                room=dirty_room,
                issue="Turnover clean required before next arrival",
                defaults={"hotel": dirty_room.hotel, "status": Maintenance.MaintenanceStatus.OPEN},
            )
        self.stdout.write(self.style.SUCCESS("Operations demo data is ready for arrivals, departures, invoices, and housekeeping."))
