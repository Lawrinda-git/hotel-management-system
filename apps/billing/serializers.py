from rest_framework import serializers

from apps.reservations.models import Reservation

from .models import Invoice, Payment


class ReservationMiniSerializer(serializers.ModelSerializer):
    class Meta:
        model = Reservation
        fields = ("id", "guest", "status", "check_in", "check_out")


class InvoiceSerializer(serializers.ModelSerializer):
    reservation_detail = ReservationMiniSerializer(source="reservation", read_only=True)

    class Meta:
        model = Invoice
        fields = ("id", "reservation", "reservation_detail", "total_amount", "issue_date", "status")
        read_only_fields = ("issue_date",)


class InvoiceMiniSerializer(serializers.ModelSerializer):
    class Meta:
        model = Invoice
        fields = ("id", "reservation", "total_amount", "status")


class PaymentSerializer(serializers.ModelSerializer):
    invoice_detail = InvoiceMiniSerializer(source="invoice", read_only=True)

    class Meta:
        model = Payment
        fields = ("id", "invoice", "invoice_detail", "amount", "method", "payment_date")
        read_only_fields = ("payment_date",)