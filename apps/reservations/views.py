from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.viewsets import ModelViewSet

from .models import Reservation, RoomReservation
from .serializers import ReservationSerializer, RoomReservationSerializer


class ReservationViewSet(ModelViewSet):
	queryset = Reservation.objects.select_related("guest").prefetch_related("room_reservations__room")
	serializer_class = ReservationSerializer
	filter_backends = [DjangoFilterBackend]
	filterset_fields = ["guest", "status", "check_in", "check_out", "booking_date"]


class RoomReservationViewSet(ModelViewSet):
	queryset = RoomReservation.objects.select_related("resv", "room", "room__hotel", "room__room_type").all()
	serializer_class = RoomReservationSerializer
	filter_backends = [DjangoFilterBackend]
	filterset_fields = ["resv", "room"]
