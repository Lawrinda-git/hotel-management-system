from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.viewsets import ModelViewSet

from .models import Guest
from .serializers import GuestSerializer


class GuestViewSet(ModelViewSet):
	queryset = Guest.objects.all()
	serializer_class = GuestSerializer
	filter_backends = [DjangoFilterBackend]
	filterset_fields = ["guest_name", "guest_email", "id_number", "nationality"]
