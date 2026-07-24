from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.viewsets import ModelViewSet

from apps.common.mixins import BranchScopedQuerysetMixin

from .models import Service, ServiceRequest
from .serializers import ServiceRequestSerializer, ServiceSerializer


class ServiceViewSet(BranchScopedQuerysetMixin, ModelViewSet):
	queryset = Service.objects.all()
	serializer_class = ServiceSerializer
	filter_backends = [DjangoFilterBackend]
	filterset_fields = ["service_name", "category", "price"]


class ServiceRequestViewSet(BranchScopedQuerysetMixin, ModelViewSet):
	queryset = ServiceRequest.objects.select_related("service", "staff", "resv", "resv__guest").all()
	serializer_class = ServiceRequestSerializer
	filter_backends = [DjangoFilterBackend]
	filterset_fields = ["service", "staff", "resv", "status", "request_time"]
	branch_field = "resv__hotel"
