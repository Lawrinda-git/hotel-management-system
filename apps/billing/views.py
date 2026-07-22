import hashlib
import hmac
import json
import logging
from decimal import Decimal

import requests
from django.conf import settings
from django.db import transaction
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.viewsets import ModelViewSet

from .models import Invoice, Payment
from .serializers import InvoiceSerializer, PaymentSerializer


logger = logging.getLogger(__name__)


def _initialize_paystack_transaction(invoice, request):
	if not settings.PAYSTACK_SECRET_KEY:
		raise ValueError("PAYSTACK_SECRET_KEY is not configured")

	guest = invoice.reservation.guest
	amount_kobo = int(Decimal(invoice.balance_due) * 100)
	payload = {
		"email": guest.guest_email,
		"amount": str(amount_kobo),
		"reference": f"inv-{invoice.id}-{invoice.reservation_id}",
		"callback_url": settings.PAYSTACK_RETURN_URL,
		"metadata": {
			"invoice_id": invoice.id,
			"reservation_id": invoice.reservation_id,
			"guest_name": guest.guest_name,
			"guest_phone": guest.guest_phone,
		},
	}
	response = requests.post(
		"https://api.paystack.co/transaction/initialize",
		json=payload,
		headers={
			"Authorization": f"Bearer {settings.PAYSTACK_SECRET_KEY}",
		},
		timeout=20,
	)
	if not response.ok:
		raise ValueError(
			f"Paystack API returned {response.status_code}: {response.text}"
		)
	data = response.json()
	if not data.get("status"):
		raise ValueError(data.get("message") or "Paystack initialization failed")
	return data["data"]


@require_http_methods(["POST"])
def create_paystack_checkout(request):
	try:
		payload = json.loads(request.body.decode("utf-8")) if request.body else {}
	except json.JSONDecodeError:
		return JsonResponse({"detail": "Invalid JSON payload."}, status=400)

	invoice_id = payload.get("invoice_id")
	if not invoice_id:
		return JsonResponse({"detail": "invoice_id is required."}, status=400)

	invoice = get_object_or_404(Invoice.objects.select_related("reservation", "reservation__guest"), pk=invoice_id)
	try:
		data = _initialize_paystack_transaction(invoice, request)
	except (ValueError, requests.RequestException, OSError) as exc:
		logger.exception("Unable to initialize Paystack payment for invoice %s", invoice.id)
		return JsonResponse({"detail": f"Paystack checkout failed: {exc}"}, status=503)

	return JsonResponse({
		"detail": "Paystack checkout initialized.",
		"authorization_url": data.get("authorization_url"),
		"reference": data.get("reference"),
	}, status=201)


@csrf_exempt
@require_http_methods(["POST"])
def paystack_webhook(request):
	signature = request.headers.get("x-paystack-signature", "")
	if not settings.PAYSTACK_SECRET_KEY:
		return HttpResponse(status=503)
	expected = hmac.new(
		settings.PAYSTACK_SECRET_KEY.encode("utf-8"),
		msg=request.body,
		digestmod=hashlib.sha512,
	).hexdigest()
	if not hmac.compare_digest(signature, expected):
		return HttpResponse(status=401)

	try:
		payload = json.loads(request.body.decode("utf-8"))
	except json.JSONDecodeError:
		return HttpResponse(status=400)

	event = payload.get("event")
	data = payload.get("data", {})
	reference = data.get("reference")
	if event != "charge.success" or not reference:
		return HttpResponse(status=200)

	payment_data = data.get("metadata", {}) if isinstance(data.get("metadata", {}), dict) else {}
	invoice_id = payment_data.get("invoice_id")
	amount = Decimal(str(data.get("amount", 0))) / Decimal("100")

	with transaction.atomic():
		invoice = Invoice.objects.select_for_update().filter(pk=invoice_id).first()
		if invoice is None:
			return HttpResponse(status=200)
		payment, created = Payment.objects.get_or_create(
			provider_reference=reference,
			defaults={
				"invoice": invoice,
				"amount": amount,
				"method": Payment.PaymentMethod.PAYSTACK,
				"status": Payment.PaymentStatus.SUCCESS,
				"provider_response": data,
			},
		)
		if not created:
			payment.invoice = invoice
			payment.amount = amount
			payment.method = Payment.PaymentMethod.PAYSTACK
			payment.status = Payment.PaymentStatus.SUCCESS
			payment.provider_response = data
			payment.save(update_fields=["invoice", "amount", "method", "status", "provider_response"])

		paid_total = invoice.amount_paid
		if paid_total >= invoice.total_amount:
			invoice.status = Invoice.InvoiceStatus.PAID
		elif paid_total > 0:
			invoice.status = Invoice.InvoiceStatus.PARTIAL
		invoice.save(update_fields=["status"])

	return HttpResponse(status=200)


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
