from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.viewsets import ModelViewSet

from .models import Staff
from .serializers import StaffSerializer


class StaffViewSet(ModelViewSet):
	queryset = Staff.objects.select_related("hotel", "department").all()
	serializer_class = StaffSerializer
	filter_backends = [DjangoFilterBackend]
	filterset_fields = ["role", "hotel", "department", "is_active", "is_staff", "username"]
