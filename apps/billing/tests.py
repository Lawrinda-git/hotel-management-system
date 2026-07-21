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
		response_body = json.dumps({
			"status": True,
			"data": {
				"authorization_url": "https://paystack.example/checkout",
				"reference": "ref-123",
			},
		}).encode("utf-8")
		mock_response = Mock()
		mock_response.__enter__ = Mock(return_value=mock_response)
		mock_response.__exit__ = Mock(return_value=None)
		mock_response.read.return_value = response_body

		with patch("apps.billing.views.urlopen", return_value=mock_response):
			response = self.client.post(
				reverse("paystack_checkout"),
				data=json.dumps({"invoice_id": self.invoice.id}),
				content_type="application/json",
			)

		self.assertEqual(response.status_code, 201)
		self.assertEqual(response.json()["reference"], "ref-123")
		self.assertEqual(response.json()["authorization_url"], "https://paystack.example/checkout")

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
