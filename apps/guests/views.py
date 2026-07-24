from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.viewsets import ModelViewSet

from apps.common.mixins import BranchScopedQuerysetMixin, MANAGER_ROLES

from .models import Guest
from .serializers import GuestSerializer


class GuestViewSet(BranchScopedQuerysetMixin, ModelViewSet):
	queryset = Guest.objects.all()
	serializer_class = GuestSerializer
	filter_backends = [DjangoFilterBackend]
	filterset_fields = ["guest_name", "guest_email", "id_number", "nationality"]
	branch_field = None  # handled via get_queryset override below

	def get_queryset(self):
		qs = super().get_queryset()
		user = self.request.user
		if not user or not user.is_authenticated:
			return qs.none()
		role = (user.role or "").lower()
		if role in MANAGER_ROLES:
			return qs
		hotel_id = user.hotel_id
		if hotel_id is None:
			return qs.none()
		# Guest has no direct hotel FK; scope via reservations
		return qs.filter(reservations__hotel_id=hotel_id).distinct()
