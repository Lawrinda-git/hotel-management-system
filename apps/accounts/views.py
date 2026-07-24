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

	def get_queryset(self):
		qs = super().get_queryset()
		user = self.request.user
		if not user or not user.is_authenticated:
			return qs.none()
		role = (user.role or "").lower()
		if role in MANAGER_ROLES:
			return qs
		# Branch staff can only see other staff at their own hotel
		if user.hotel_id:
			return qs.filter(hotel_id=user.hotel_id)
		return qs.none()
