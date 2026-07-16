from rest_framework import serializers

from apps.guests.models import Guest
from apps.reservations.models import Reservation

from .models import Feedback


class GuestMiniSerializer(serializers.ModelSerializer):
    class Meta:
        model = Guest
        fields = ("id", "guest_name", "guest_email")


class ReservationMiniSerializer(serializers.ModelSerializer):
    class Meta:
        model = Reservation
        fields = ("id", "guest", "status", "check_in", "check_out")


class FeedbackSerializer(serializers.ModelSerializer):
    guest_detail = GuestMiniSerializer(source="guest", read_only=True)
    resv_detail = ReservationMiniSerializer(source="resv", read_only=True)

    class Meta:
        model = Feedback
        fields = ("id", "guest", "guest_detail", "resv", "resv_detail", "rating", "comments", "date")
        read_only_fields = ("date",)