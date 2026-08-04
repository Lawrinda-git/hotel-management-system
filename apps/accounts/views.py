from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.viewsets import ModelViewSet

from apps.common.mixins import BranchScopedQuerysetMixin, MANAGER_ROLES

from .models import Staff
from .serializers import StaffSerializer


class StaffViewSet(BranchScopedQuerysetMixin, ModelViewSet):
	queryset = Staff.objects.select_related("hotel", "department").all()
	serializer_class = StaffSerializer
	filter_backends = [DjangoFilterBackend]
	filterset_fields = ["role", "hotel", "department", "is_active", "is_staff", "username"]
	# Managers are scoped to their hotel just like receptionists/accountants.
	branch_field = "hotel"
