import hashlib
import hmac
import json
import logging
from decimal import Decimal
from urllib.parse import quote

import requests
from django.conf import settings
from django.db import transaction
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404
from django.urls import reverse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.viewsets import ModelViewSet

from apps.common.mixins import BranchScopedQuerysetMixin
from apps.reservations.models import Reservation
from .models import Invoice, Payment
from .serializers import InvoiceSerializer, PaymentSerializer


logger = logging.getLogger(__name__)


def _local_ghana_phone(value):
	"""Convert +233241234567 / 241234567 to Paystack's local format 0241234567."""
	phone = (value or "").strip()
	if phone.startswith("+"):
		phone = phone[1:]
	if phone.startswith("233"):
		phone = phone[3:]
	if phone and not phone.startswith("0"):
		phone = f"0{phone}"
	return phone


MOBILE_MONEY_PROVIDERS = {"mtn": "MTN Mobile Money", "vodafone": "Vodafone Cash", "atl": "AirtelTigo Money"}


def _initialize_paystack_transaction(invoice, request, callback_url_name="booking", channels=None, mobile_money=None):
	if not settings.PAYSTACK_SECRET_KEY:
		raise ValueError("PAYSTACK_SECRET_KEY is not configured")

	guest = invoice.reservation.guest
	amount_kobo = int(Decimal(invoice.balance_due) * 100)
	payload = {
		"email": guest.guest_email,
		"amount": str(amount_kobo),
		"currency": "GHS",
		"reference": f"inv-{invoice.id}-{invoice.reservation_id}",
		# Build this from the incoming request so localhost, ngrok, staging,
		# and the eventual production domain all return to the correct host.
		"callback_url": request.build_absolute_uri(reverse(callback_url_name)),
		"metadata": {
			"invoice_id": invoice.id,
			"reservation_id": invoice.reservation_id,
			"guest_name": guest.guest_name,
			"guest_phone": guest.guest_phone,
		},
	}
	if channels:
		payload["channels"] = channels
	if mobile_money:
		payload["mobile_money"] = mobile_money
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


@require_http_methods(["GET"])
def verify_paystack_payment(request, reference):
    """Verify a Paystack payment by reference."""
    if not settings.PAYSTACK_SECRET_KEY:
        return JsonResponse({"detail": "Paystack is not configured."}, status=503)
    
    try:
        response = requests.get(
            f"https://api.paystack.co/transaction/verify/{quote(reference, safe='')}",
            headers={
                "Authorization": f"Bearer {settings.PAYSTACK_SECRET_KEY}",
            },
            timeout=20,
        )
        if not response.ok:
            return JsonResponse({"detail": f"Paystack API returned {response.status_code}"}, status=502)
        
        data = response.json()
        if not data.get("status"):
            return JsonResponse({"detail": data.get("message") or "Verification failed"}, status=400)
        
        payment_data = data.get("data", {})
        status = payment_data.get("status")
        paid_at = payment_data.get("paid_at")

        # Paystack reports the amount in the smallest currency unit
        # (pesewas for GHS), so divide by 100. Defensively default to 0 so a
        # malformed payload can never crash the callback page.
        try:
            amount = Decimal(str(payment_data.get("amount", 0))) / Decimal("100")
        except (TypeError, ValueError, ArithmeticError):
            amount = Decimal("0")

        # Complete the matching invoice/reservation only after Paystack has
        # verified a successful transaction. References are generated as
        # inv-{invoice_id}-{reservation_id} during checkout initialization.
        #
        # The checkout is initialized for invoice.balance_due (not
        # total_amount), so a successful charge may settle the whole invoice OR
        # just the remaining balance after earlier partial payments. Record
        # whatever was charged and recompute the invoice status from the total
        # amount paid, exactly like the webhook does.
        payment_recorded = False
        if status == "success":
            reference_parts = reference.split("-")
            if len(reference_parts) == 3 and reference_parts[0] == "inv":
                invoice = Invoice.objects.select_related("reservation").filter(
                    pk=reference_parts[1], reservation_id=reference_parts[2]
                ).first()
                if invoice and amount > 0:
                    with transaction.atomic():
                        # Lock the invoice so a simultaneous webhook delivery
                        # cannot double-apply the same charge.
                        invoice = (
                            Invoice.objects.select_for_update()
                            .select_related("reservation")
                            .get(pk=invoice.pk)
                        )
                        Payment.objects.update_or_create(
                            provider_reference=reference,
                            defaults={
                                "invoice": invoice,
                                "hotel": invoice.hotel,
                                "amount": amount,
                                "method": Payment.PaymentMethod.PAYSTACK,
                                "status": Payment.PaymentStatus.SUCCESS,
                                "provider_response": data,
                            },
                        )
                        paid_total = invoice.amount_paid
                        if paid_total >= invoice.total_amount:
                            invoice.status = Invoice.InvoiceStatus.PAID
                        elif paid_total > 0:
                            invoice.status = Invoice.InvoiceStatus.PARTIAL
                        invoice.save(update_fields=["status"])
                        # Confirm the reservation once the invoice is fully
                        # paid (PENDING -> CONFIRMED only, so a cancelled or
                        # checked-in reservation is never resurrected).
                        if (
                            invoice.status == Invoice.InvoiceStatus.PAID
                            and invoice.reservation
                            and invoice.reservation.status == Reservation.ReservationStatus.PENDING
                        ):
                            invoice.reservation.status = Reservation.ReservationStatus.CONFIRMED
                            invoice.reservation.save(update_fields=["status"])
                        payment_recorded = True

        if status == "success" and not payment_recorded:
            return JsonResponse({"detail": "Payment could not be matched to an invoice."}, status=400)
        
        return JsonResponse({
            "detail": "Payment verified.",
            "reference": reference,
            "status": status,
            "amount": str(amount),
            "paid_at": paid_at,
            "gateway_response": payment_data.get("gateway_response"),
        })
    except requests.RequestException as exc:
        return JsonResponse({"detail": f"Unable to verify payment: {exc}"}, status=503)


@require_http_methods(["POST"])
def create_paystack_checkout(request):
	try:
		payload = json.loads(request.body.decode("utf-8")) if request.body else {}
	except json.JSONDecodeError:
		return JsonResponse({"detail": "Invalid JSON payload."}, status=400)

	invoice_id = payload.get("invoice_id")
	if not invoice_id:
		return JsonResponse({"detail": "invoice_id is required."}, status=400)

	# Walk-in bookings pay by mobile money only — the staff member collects
	# the client's number and provider, then the client confirms the charge.
	callback_url_name = payload.get("callback_url_name") or "booking"
	if callback_url_name not in ("booking", "walkin_booking"):
		callback_url_name = "booking"
	payment_method = (payload.get("payment_method") or "").lower()
	channels = None
	mobile_money = None
	if payment_method == "mobile_money":
		channels = ["mobile_money"]
		provider = (payload.get("mobile_money_provider") or "").strip().lower()
		phone = _local_ghana_phone(payload.get("mobile_money_phone"))
		# Ghana mobile money requires a 10-digit local number (e.g. 0241234567).
		import re
		if not re.fullmatch(r"0\d{9}", phone) or provider not in MOBILE_MONEY_PROVIDERS:
			return JsonResponse({
				"detail": "Mobile money requires a valid Ghana phone number (e.g. 024 123 4567) and a provider (MTN, Vodafone, or AirtelTigo).",
			}, status=400)
		mobile_money = {"phone": phone, "provider": provider}

	invoice = get_object_or_404(Invoice.objects.select_related("reservation", "reservation__guest"), pk=invoice_id)

	# Walk-in mobile money bookings must stay within the staff member's own hotel.
	role = (request.user.role or "").lower() if request.user.is_authenticated else ""
	if (
		payment_method == "mobile_money"
		and role in ("admin", "manager", "receptionist", "accountant", "housekeeping")
		and request.user.hotel_id
		and invoice.hotel_id != request.user.hotel_id
	):
		return JsonResponse({
			"detail": "You can only take walk-in bookings at your own hotel.",
		}, status=403)

	try:
		data = _initialize_paystack_transaction(
			invoice, request,
			callback_url_name=callback_url_name,
			channels=channels,
			mobile_money=mobile_money,
		)
	except (ValueError, requests.RequestException, OSError) as exc:
		logger.exception("Unable to initialize Paystack payment for invoice %s", invoice.id)
		error_message = "Payment gateway is currently unavailable. Please check your internet connection and try again."
		return JsonResponse({"detail": error_message}, status=503)

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
		invoice = Invoice.objects.select_for_update().select_related("reservation").filter(pk=invoice_id).first()
		if invoice is None:
			return HttpResponse(status=200)
		payment, created = Payment.objects.get_or_create(
			provider_reference=reference,
			defaults={
				"invoice": invoice,
				"hotel": invoice.hotel,
				"amount": amount,
				"method": Payment.PaymentMethod.PAYSTACK,
				"status": Payment.PaymentStatus.SUCCESS,
				"provider_response": data,
			},
		)
		if not created:
			payment.invoice = invoice
			payment.hotel = invoice.hotel
			payment.amount = amount
			payment.method = Payment.PaymentMethod.PAYSTACK
			payment.status = Payment.PaymentStatus.SUCCESS
			payment.provider_response = data
			payment.save(update_fields=["invoice", "hotel", "amount", "method", "status", "provider_response"])

		paid_total = invoice.amount_paid
		if paid_total >= invoice.total_amount:
			invoice.status = Invoice.InvoiceStatus.PAID
		elif paid_total > 0:
			invoice.status = Invoice.InvoiceStatus.PARTIAL
		invoice.save(update_fields=["status"])

		# Confirm the reservation once the invoice is fully paid.
		if invoice.status == Invoice.InvoiceStatus.PAID and invoice.reservation:
			reservation = invoice.reservation
			if reservation.status == Reservation.ReservationStatus.PENDING:
				reservation.status = Reservation.ReservationStatus.CONFIRMED
				reservation.save(update_fields=["status"])

	return HttpResponse(status=200)


class InvoiceViewSet(BranchScopedQuerysetMixin, ModelViewSet):
	queryset = Invoice.objects.select_related("reservation", "reservation__guest").all()
	serializer_class = InvoiceSerializer
	filter_backends = [DjangoFilterBackend]
	filterset_fields = ["reservation", "status", "issue_date", "total_amount"]


class PaymentViewSet(BranchScopedQuerysetMixin, ModelViewSet):
	queryset = Payment.objects.select_related("invoice", "invoice__reservation", "invoice__reservation__guest").all()
	serializer_class = PaymentSerializer
	filter_backends = [DjangoFilterBackend]
	filterset_fields = ["invoice", "method", "payment_date", "amount"]
