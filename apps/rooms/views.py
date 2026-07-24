from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.viewsets import ModelViewSet

from apps.common.mixins import BranchScopedQuerysetMixin

from .models import Maintenance, Room, RoomType
from .serializers import MaintenanceSerializer, RoomSerializer, RoomTypeSerializer


class RoomTypeViewSet(BranchScopedQuerysetMixin, ModelViewSet):
	queryset = RoomType.objects.all()
	serializer_class = RoomTypeSerializer
	filter_backends = [DjangoFilterBackend]
	filterset_fields = ["type_name", "price_per_night"]


class RoomViewSet(BranchScopedQuerysetMixin, ModelViewSet):
	queryset = Room.objects.select_related("hotel", "room_type").all()
	serializer_class = RoomSerializer
	filter_backends = [DjangoFilterBackend]
	filterset_fields = ["hotel", "room_type", "status", "floor", "housekeeping_status"]


class MaintenanceViewSet(BranchScopedQuerysetMixin, ModelViewSet):
	queryset = Maintenance.objects.select_related("staff", "room", "room__hotel", "room__room_type").all()
	serializer_class = MaintenanceSerializer
	filter_backends = [DjangoFilterBackend]
	filterset_fields = ["staff", "room", "status", "report_date", "resolve_date"]
	branch_field = "room__hotel"
