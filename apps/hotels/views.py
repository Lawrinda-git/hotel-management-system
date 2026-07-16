from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.viewsets import ModelViewSet

from .models import Department, Hotel
from .serializers import DepartmentSerializer, HotelSerializer


class HotelViewSet(ModelViewSet):
	queryset = Hotel.objects.all()
	serializer_class = HotelSerializer
	filter_backends = [DjangoFilterBackend]
	filterset_fields = ["hotel_name", "hotel_email", "hotel_phone"]


class DepartmentViewSet(ModelViewSet):
	queryset = Department.objects.select_related("hotel").all()
	serializer_class = DepartmentSerializer
	filter_backends = [DjangoFilterBackend]
	filterset_fields = ["hotel", "dept_name"]
