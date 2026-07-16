from rest_framework import serializers

from .models import Guest


class GuestSerializer(serializers.ModelSerializer):
    class Meta:
        model = Guest
        fields = ("id", "guest_name", "guest_phone", "guest_email", "id_number", "nationality", "created_at")
        read_only_fields = ("created_at",)