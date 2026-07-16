from rest_framework import serializers

from apps.accounts.models import Staff
from apps.reservations.models import Reservation

from .models import Service, ServiceRequest


class ServiceSerializer(serializers.ModelSerializer):
    class Meta:
        model = Service
        fields = ("id", "service_name", "price", "category")


class StaffMiniSerializer(serializers.ModelSerializer):
    class Meta:
        model = Staff
        fields = ("id", "username", "staff_name", "role")


class ReservationMiniSerializer(serializers.ModelSerializer):
    class Meta:
        model = Reservation
        fields = ("id", "guest", "status", "check_in", "check_out")


class ServiceRequestSerializer(serializers.ModelSerializer):
    service_detail = ServiceSerializer(source="service", read_only=True)
    staff_detail = StaffMiniSerializer(source="staff", read_only=True)
    resv_detail = ReservationMiniSerializer(source="resv", read_only=True)

    class Meta:
        model = ServiceRequest
        fields = (
            "id",
            "service",
            "service_detail",
            "staff",
            "staff_detail",
            "resv",
            "resv_detail",
            "request_time",
            "status",
        )
        read_only_fields = ("request_time",)