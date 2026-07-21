from django.db import models


class Reservation(models.Model):
    """
    A guest's booking at the hotel.

    check_in / check_out     : the PLANNED dates when booking
    actual_check_in / out    : the REAL dates recorded when it actually happens
    (they often differ — guest arrives early, leaves late, etc.)

    One reservation can cover multiple rooms — that many-to-many
    relationship is handled by the RoomReservation junction table below.
    """

    class ReservationStatus(models.TextChoices):
        PENDING     = "Pending",      "Pending"
        CONFIRMED   = "Confirmed",    "Confirmed"
        CHECKED_IN  = "Checked_In",   "Checked In"
        CHECKED_OUT = "Checked_Out",  "Checked Out"
        CANCELLED   = "Cancelled",    "Cancelled"
        NO_SHOW     = "No_Show",      "No Show"

    guest = models.ForeignKey(
        "guests.Guest",
        on_delete=models.CASCADE,       # guest deleted → their reservations deleted too
        related_name="reservations",
    )
    hotel = models.ForeignKey(
        "hotels.Hotel", on_delete=models.CASCADE, null=True, blank=True, related_name="reservations",
    )
    check_in         = models.DateTimeField()
    check_out        = models.DateTimeField()
    actual_check_in  = models.DateTimeField(null=True, blank=True)  # filled on arrival
    actual_check_out = models.DateTimeField(null=True, blank=True)  # filled on departure
    status           = models.CharField(
        max_length=20,
        choices=ReservationStatus.choices,
        default=ReservationStatus.PENDING,
    )
    booking_date     = models.DateTimeField(auto_now_add=True)  # when the booking was made

    class Meta:
        db_table = "reservation"

    def __str__(self):
        return (
            f"Reservation #{self.pk} — {self.guest.guest_name} "
            f"({self.check_in.date()} to {self.check_out.date()})"
        )


class RoomReservation(models.Model):
    """
    Junction table linking Rooms to Reservations.

    WHY this table exists:
    A single reservation can cover more than one room
    (e.g. a family books rooms 101 and 102 under one reservation).
    A single room appears in many reservations over time.
    That is a many-to-many relationship — Django handles it with
    an explicit junction table like this one.

    unique_together prevents the same room being assigned to
    the same reservation twice by accident.
    """

    resv = models.ForeignKey(
        Reservation,
        on_delete=models.CASCADE,
        related_name="room_reservations",
    )
    room = models.ForeignKey(
        "rooms.Room",
        on_delete=models.CASCADE,
        related_name="room_reservations",
    )

    class Meta:
        db_table       = "room_reservation"
        unique_together = ("resv", "room")

    def __str__(self):
        return f"Resv #{self.resv_id} ↔ Room {self.room.room_number}"
