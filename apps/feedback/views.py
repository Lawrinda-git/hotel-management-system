from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.viewsets import ModelViewSet

from .models import Feedback
from .serializers import FeedbackSerializer


class FeedbackViewSet(ModelViewSet):
	queryset = Feedback.objects.select_related("guest", "resv", "resv__guest").all()
	serializer_class = FeedbackSerializer
	filter_backends = [DjangoFilterBackend]
	filterset_fields = ["guest", "resv", "rating", "date"]
