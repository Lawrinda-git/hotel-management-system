from rest_framework import serializers

from apps.accounts.models import Staff
from apps.hotels.models import Hotel

from .models import Maintenance, Room, RoomType


class HotelMiniSerializer(serializers.ModelSerializer):
    class Meta:
        model = Hotel
        fields = ("id", "hotel_name")


class RoomTypeSerializer(serializers.ModelSerializer):
    class Meta:
        model = RoomType
        fields = ("id", "type_name", "price_per_night", "description")


class RoomSerializer(serializers.ModelSerializer):
    hotel_detail = HotelMiniSerializer(source="hotel", read_only=True)
    room_type_detail = RoomTypeSerializer(source="room_type", read_only=True)

    class Meta:
        model = Room
        fields = (
            "id",
            "hotel",
            "hotel_detail",
            "room_type",
            "room_type_detail",
            "room_number",
            "status",
            "floor",
            "housekeeping_status",
        )


class StaffMiniSerializer(serializers.ModelSerializer):
    class Meta:
        model = Staff
        fields = ("id", "username", "staff_name", "role")


class MaintenanceSerializer(serializers.ModelSerializer):
    staff_detail = StaffMiniSerializer(source="staff", read_only=True)
    room_detail = RoomSerializer(source="room", read_only=True)

    class Meta:
        model = Maintenance
        fields = (
            "id",
            "staff",
            "staff_detail",
            "room",
            "room_detail",
            "issue",
            "report_date",
            "resolve_date",
            "status",
        )
        read_only_fields = ("report_date",)