from django.db import models


class Invoice(models.Model):
    """
    The financial bill for a reservation.

    OneToOneField means one reservation gets exactly one invoice —
    not zero, not two. It is a stricter version of ForeignKey.

    total_amount is the full bill (room nights + services).
    status tracks whether it has been paid.

    Individual payment transactions are in the Payment model below,
    which allows a guest to pay in instalments (partial payments).
    """

    class InvoiceStatus(models.TextChoices):
        UNPAID  = "unpaid",  "Unpaid"
        PARTIAL = "partial", "Partially Paid"
        PAID    = "paid",    "Paid"
        VOID    = "void",    "Void"

    # OneToOneField = a ForeignKey with unique=True
    # Each reservation can only have ONE invoice
    reservation  = models.OneToOneField(
        "reservations.Reservation",
        on_delete=models.CASCADE,
        related_name="invoice",
    )
    total_amount = models.DecimalField(max_digits=10, decimal_places=2)
    issue_date   = models.DateTimeField(auto_now_add=True)
    status       = models.CharField(
        max_length=20,
        choices=InvoiceStatus.choices,
        default=InvoiceStatus.UNPAID,
    )

    class Meta:
        db_table = "invoice"

    def __str__(self):
        return f"Invoice #{self.pk} — Resv #{self.reservation_id} [{self.status}]"

    # ── Computed helpers (no extra DB column needed) ─────────
    @property
    def amount_paid(self):
        """Sum of all payments made against this invoice."""
        return (
            self.payments.aggregate(total=models.Sum("amount"))["total"] or 0
        )

    @property
    def balance_due(self):
        """How much the guest still owes."""
        return self.total_amount - self.amount_paid


class Payment(models.Model):
    """
    A single payment transaction against an invoice.

    WHY separate from Invoice:
    A guest might pay GH₵500 now and GH₵300 later (partial payment).
    Each transaction is one row here — the Invoice's status is
    updated separately once the full amount is covered.

    Multiple Payment rows can point to the same Invoice (many-to-one).
    """

    class PaymentMethod(models.TextChoices):
        CASH          = "Cash",          "Cash"
        CARD          = "Card",          "Card"
        MOBILE_MONEY  = "Mobile_Money",  "Mobile Money"
        BANK_TRANSFER = "Bank_Transfer", "Bank Transfer"

    invoice      = models.ForeignKey(
        Invoice,
        on_delete=models.CASCADE,
        related_name="payments",       # invoice.payments.all() gives all payments for it
    )
    amount       = models.DecimalField(max_digits=10, decimal_places=2)
    method       = models.CharField(
        max_length=30,
        choices=PaymentMethod.choices,
    )
    payment_date = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "payment"

    def __str__(self):
        return (
            f"Payment #{self.pk} — GH₵{self.amount} via {self.method} "
            f"(Invoice #{self.invoice_id})"
        )
