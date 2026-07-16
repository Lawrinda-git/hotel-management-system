from rest_framework import serializers

from .models import Department, Hotel


class HotelSerializer(serializers.ModelSerializer):
    class Meta:
        model = Hotel
        fields = ("id", "hotel_email", "hotel_address", "hotel_name", "hotel_phone", "created_at")
        read_only_fields = ("created_at",)


class HotelMiniSerializer(serializers.ModelSerializer):
    class Meta:
        model = Hotel
        fields = ("id", "hotel_name")


class DepartmentSerializer(serializers.ModelSerializer):
    hotel_detail = HotelMiniSerializer(source="hotel", read_only=True)

    class Meta:
        model = Department
        fields = ("id", "hotel", "hotel_detail", "dept_name")