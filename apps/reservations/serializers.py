from rest_framework import serializers

from apps.guests.models import Guest
from apps.rooms.models import Room

from .models import Reservation, RoomReservation


class GuestMiniSerializer(serializers.ModelSerializer):
    class Meta:
        model = Guest
        fields = ("id", "guest_name", "guest_email", "guest_phone")


class RoomMiniSerializer(serializers.ModelSerializer):
    class Meta:
        model = Room
        fields = ("id", "room_number", "status", "floor")


class RoomReservationSerializer(serializers.ModelSerializer):
    room_detail = RoomMiniSerializer(source="room", read_only=True)

    class Meta:
        model = RoomReservation
        fields = ("id", "resv", "room", "room_detail")


class ReservationSerializer(serializers.ModelSerializer):
    guest_detail = GuestMiniSerializer(source="guest", read_only=True)
    room_reservations = RoomReservationSerializer(many=True, read_only=True)

    class Meta:
        model = Reservation
        fields = (
            "id",
            "guest",
            "guest_detail",
            "check_in",
            "check_out",
            "actual_check_in",
            "actual_check_out",
            "status",
            "booking_date",
            "room_reservations",
        )
        read_only_fields = ("booking_date",)