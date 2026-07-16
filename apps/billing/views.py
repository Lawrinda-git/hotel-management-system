from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.viewsets import ModelViewSet

from .models import Invoice, Payment
from .serializers import InvoiceSerializer, PaymentSerializer


class InvoiceViewSet(ModelViewSet):
	queryset = Invoice.objects.select_related("reservation", "reservation__guest").all()
	serializer_class = InvoiceSerializer
	filter_backends = [DjangoFilterBackend]
	filterset_fields = ["reservation", "status", "issue_date", "total_amount"]


class PaymentViewSet(ModelViewSet):
	queryset = Payment.objects.select_related("invoice", "invoice__reservation", "invoice__reservation__guest").all()
	serializer_class = PaymentSerializer
	filter_backends = [DjangoFilterBackend]
	filterset_fields = ["invoice", "method", "payment_date", "amount"]
