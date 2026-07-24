from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.viewsets import ModelViewSet

from apps.common.mixins import BranchScopedQuerysetMixin

from .models import Feedback
from .serializers import FeedbackSerializer


class FeedbackViewSet(BranchScopedQuerysetMixin, ModelViewSet):
	queryset = Feedback.objects.select_related("guest", "resv", "resv__guest").all()
	serializer_class = FeedbackSerializer
	filter_backends = [DjangoFilterBackend]
	filterset_fields = ["guest", "resv", "rating", "date"]
	branch_field = "resv__hotel"
