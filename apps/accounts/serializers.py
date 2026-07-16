from django.contrib.auth import get_user_model
from rest_framework import serializers

from apps.hotels.models import Department, Hotel


Staff = get_user_model()


class HotelMiniSerializer(serializers.ModelSerializer):
    class Meta:
        model = Hotel
        fields = ("id", "hotel_name")


class DepartmentMiniSerializer(serializers.ModelSerializer):
    hotel_detail = HotelMiniSerializer(source="hotel", read_only=True)

    class Meta:
        model = Department
        fields = ("id", "dept_name", "hotel", "hotel_detail")


class StaffSerializer(serializers.ModelSerializer):
    hotel_detail = HotelMiniSerializer(source="hotel", read_only=True)
    department_detail = DepartmentMiniSerializer(source="department", read_only=True)
    password = serializers.CharField(write_only=True, required=False, allow_blank=False)

    class Meta:
        model = Staff
        fields = (
            "id",
            "username",
            "password",
            "first_name",
            "last_name",
            "email",
            "staff_name",
            "staff_phone",
            "role",
            "hotel",
            "department",
            "hotel_detail",
            "department_detail",
            "is_active",
            "is_staff",
            "is_superuser",
            "date_joined",
            "hired_at",
        )
        read_only_fields = ("date_joined", "hired_at")

    def create(self, validated_data):
        password = validated_data.pop("password", None)
        staff = Staff(**validated_data)
        if password:
            staff.set_password(password)
        staff.save()
        return staff

    def update(self, instance, validated_data):
        password = validated_data.pop("password", None)
        instance = super().update(instance, validated_data)
        if password:
            instance.set_password(password)
            instance.save()
        return instance