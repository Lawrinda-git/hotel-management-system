from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.viewsets import ModelViewSet

from .models import Service, ServiceRequest
from .serializers import ServiceRequestSerializer, ServiceSerializer


class ServiceViewSet(ModelViewSet):
	queryset = Service.objects.all()
	serializer_class = ServiceSerializer
	filter_backends = [DjangoFilterBackend]
	filterset_fields = ["service_name", "category", "price"]


class ServiceRequestViewSet(ModelViewSet):
	queryset = ServiceRequest.objects.select_related("service", "staff", "resv", "resv__guest").all()
	serializer_class = ServiceRequestSerializer
	filter_backends = [DjangoFilterBackend]
	filterset_fields = ["service", "staff", "resv", "status", "request_time"]
