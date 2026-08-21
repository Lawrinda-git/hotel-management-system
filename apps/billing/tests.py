import hashlib
import hmac
import json
from decimal import Decimal
from datetime import datetime, timezone
from unittest.mock import Mock, patch

from django.test import TestCase, override_settings
from django.urls import reverse

from apps.guests.models import Guest
from apps.hotels.models import Hotel
from apps.reservations.models import Reservation
from apps.rooms.models import Room, RoomType

from .models import Invoice, Payment

# Create your tests here.


class PaystackBillingTests(TestCase):
	def setUp(self):
		hotel = Hotel.objects.create(
			hotel_name="Paystack Hotel",
			hotel_email="paystack@example.com",
			hotel_address="1 Billing Street",
			hotel_phone="+233200000000",
		)
		room_type = RoomType.objects.create(
			type_name="Suite",
			price_per_night=Decimal("200.00"),
			description="A suite",
		)
		room = Room.objects.create(hotel=hotel, room_type=room_type, room_number="201", floor=2)
		guest = Guest.objects.create(
			guest_name="Paystack Guest",
			guest_phone="+233201234567",
			guest_email="paystack-guest@example.com",
			id_number="P1234567",
			nationality="Ghanaian",
		)
		reservation = Reservation.objects.create(
			guest=guest,
			check_in=datetime(2027, 6, 1, 14, 0, tzinfo=timezone.utc),
			check_out=datetime(2027, 6, 4, 11, 0, tzinfo=timezone.utc),
			status=Reservation.ReservationStatus.CONFIRMED,
		)
		self.invoice = Invoice.objects.create(reservation=reservation, total_amount=Decimal("500.00"))
		self.room = room

	@override_settings(PAYSTACK_SECRET_KEY="test-secret", PAYSTACK_RETURN_URL="http://testserver/booking/")
	def test_paystack_checkout_initializes(self):
		mock_response = Mock()
		mock_response.ok = True
		mock_response.json.return_value = {
			"status": True,
			"data": {
				"authorization_url": "https://paystack.example/checkout",
				"reference": "ref-123",
			},
		}

		with patch("apps.billing.views.requests.post", return_value=mock_response) as mock_post:
			response = self.client.post(
				reverse("paystack_checkout"),
				data=json.dumps({"invoice_id": self.invoice.id}),
				content_type="application/json",
			)

		self.assertEqual(response.status_code, 201)
		self.assertEqual(response.json()["reference"], "ref-123")
		self.assertEqual(response.json()["authorization_url"], "https://paystack.example/checkout")
		# The standard checkout stays on the booking callback, uses GHS, and does
		# not force a payment channel (card / mobile money choice is left to Paystack).
		sent_payload = mock_post.call_args.kwargs["json"]
		self.assertEqual(sent_payload["currency"], "GHS")
		self.assertNotIn("channels", sent_payload)
		self.assertIn("/booking/", sent_payload["callback_url"])

	@override_settings(PAYSTACK_SECRET_KEY="test-secret")
	def test_paystack_webhook_records_successful_payment(self):
		payload = {
			"event": "charge.success",
			"data": {
				"reference": "ref-456",
				"amount": 50000,
				"metadata": {"invoice_id": self.invoice.id},
			},
		}
		body = json.dumps(payload).encode("utf-8")
		signature = hmac.new(b"test-secret", msg=body, digestmod=hashlib.sha512).hexdigest()

		response = self.client.post(
			reverse("paystack_webhook"),
			data=body,
			content_type="application/json",
			**{"HTTP_X_PAYSTACK_SIGNATURE": signature},
		)

		self.assertEqual(response.status_code, 200)
		payment = Payment.objects.get(provider_reference="ref-456")
		self.assertEqual(payment.method, Payment.PaymentMethod.PAYSTACK)
		self.assertEqual(payment.status, Payment.PaymentStatus.SUCCESS)
		self.invoice.refresh_from_db()
		self.assertEqual(self.invoice.status, Invoice.InvoiceStatus.PAID)

	def _paystack_verify_response(self, reference, amount_pesewas):
		mock_response = Mock()
		mock_response.ok = True
		mock_response.json.return_value = {
			"status": True,
			"data": {
				"status": "success",
				"reference": reference,
				"amount": amount_pesewas,
				"paid_at": "2027-06-01T00:00:00.000Z",
			},
		}
		return mock_response

	@override_settings(PAYSTACK_SECRET_KEY="test-secret")
	def test_paystack_verify_records_full_payment_and_confirms_reservation(self):
		self.invoice.reservation.status = Reservation.ReservationStatus.PENDING
		self.invoice.reservation.save(update_fields=["status"])
		reference = f"inv-{self.invoice.id}-{self.invoice.reservation_id}"

		with patch("apps.billing.views.requests.get", return_value=self._paystack_verify_response(reference, 50000)):
			response = self.client.get(reverse("paystack_verify", args=[reference]))

		self.assertEqual(response.status_code, 200)
		self.assertEqual(response.json()["status"], "success")
		payment = Payment.objects.get(provider_reference=reference)
		self.assertEqual(payment.amount, Decimal("500.00"))
		self.assertEqual(payment.method, Payment.PaymentMethod.PAYSTACK)
		self.invoice.refresh_from_db()
		self.assertEqual(self.invoice.status, Invoice.InvoiceStatus.PAID)
		self.invoice.reservation.refresh_from_db()
		self.assertEqual(self.invoice.reservation.status, Reservation.ReservationStatus.CONFIRMED)

	@override_settings(PAYSTACK_SECRET_KEY="test-secret")
	def test_paystack_verify_records_balance_due_after_partial_payment(self):
		# The guest already paid GH₵200 by cash, so the Paystack charge is only
		# for the GH₵300 balance. The callback must record it even though the
		# charged amount is below the invoice total.
		Payment.objects.create(
			invoice=self.invoice,
			hotel=self.invoice.hotel,
			amount=Decimal("200.00"),
			method=Payment.PaymentMethod.CASH,
			status=Payment.PaymentStatus.SUCCESS,
		)
		self.invoice.reservation.status = Reservation.ReservationStatus.PENDING
		self.invoice.reservation.save(update_fields=["status"])
		reference = f"inv-{self.invoice.id}-{self.invoice.reservation_id}"

		with patch("apps.billing.views.requests.get", return_value=self._paystack_verify_response(reference, 30000)):
			response = self.client.get(reverse("paystack_verify", args=[reference]))

		self.assertEqual(response.status_code, 200)
		self.assertEqual(response.json()["status"], "success")
		self.invoice.refresh_from_db()
		self.assertEqual(self.invoice.status, Invoice.InvoiceStatus.PAID)
		self.assertEqual(Payment.objects.filter(invoice=self.invoice).count(), 2)
		self.invoice.reservation.refresh_from_db()
		self.assertEqual(self.invoice.reservation.status, Reservation.ReservationStatus.CONFIRMED)

	@override_settings(PAYSTACK_SECRET_KEY="test-secret")
	def test_paystack_verify_is_idempotent_after_webhook(self):
		# Webhook already recorded the charge and marked the invoice paid; the
		# browser callback must not create a duplicate payment.
		reference = f"inv-{self.invoice.id}-{self.invoice.reservation_id}"
		Payment.objects.create(
			invoice=self.invoice,
			hotel=self.invoice.hotel,
			amount=Decimal("500.00"),
			method=Payment.PaymentMethod.PAYSTACK,
			status=Payment.PaymentStatus.SUCCESS,
			provider_reference=reference,
		)
		self.invoice.status = Invoice.InvoiceStatus.PAID
		self.invoice.save(update_fields=["status"])

		with patch("apps.billing.views.requests.get", return_value=self._paystack_verify_response(reference, 50000)):
			response = self.client.get(reverse("paystack_verify", args=[reference]))

		self.assertEqual(response.status_code, 200)
		self.assertEqual(Payment.objects.filter(provider_reference=reference).count(), 1)
