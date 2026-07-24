from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.viewsets import ModelViewSet

from apps.common.mixins import BranchScopedQuerysetMixin, MANAGER_ROLES

from .models import Department, Hotel
from .serializers import DepartmentSerializer, HotelSerializer


class HotelViewSet(BranchScopedQuerysetMixin, ModelViewSet):
	queryset = Hotel.objects.all()
	serializer_class = HotelSerializer
	filter_backends = [DjangoFilterBackend]
	filterset_fields = ["hotel_name", "hotel_email", "hotel_phone"]

	def get_queryset(self):
		qs = super().get_queryset()
		user = self.request.user
		if not user or not user.is_authenticated:
			return qs.none()
		role = (user.role or "").lower()
		if role in MANAGER_ROLES:
			return qs
		# Branch staff can only see their own hotel
		if user.hotel_id:
			return qs.filter(pk=user.hotel_id)
		return qs.none()


class DepartmentViewSet(BranchScopedQuerysetMixin, ModelViewSet):
	queryset = Department.objects.select_related("hotel").all()
	serializer_class = DepartmentSerializer
	filter_backends = [DjangoFilterBackend]
	filterset_fields = ["hotel", "dept_name"]
