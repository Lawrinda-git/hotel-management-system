from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models


class Feedback(models.Model):
    """
    A guest's review of their stay, tied to one specific reservation.

    Two ForeignKeys link it to both the Guest (who wrote it)
    and the Reservation (which stay it is about).

    unique_together on (guest, resv) means one guest can only
    leave one review per reservation — no duplicate submissions.

    rating uses Django validators to enforce the 1–6 range at the
    application level. The DB engineer's CHECK(1-6) constraint
    from the physical schema is replicated here as MinValueValidator
    and MaxValueValidator.
    """

    hotel = models.ForeignKey("hotels.Hotel", on_delete=models.CASCADE, null=True, blank=True, related_name="feedbacks")
    guest = models.ForeignKey(
        "guests.Guest",
        on_delete=models.CASCADE,
        related_name="feedbacks",
    )
    resv = models.ForeignKey(
        "reservations.Reservation",
        on_delete=models.CASCADE,
        related_name="feedbacks",
    )
    rating = models.SmallIntegerField(
        validators=[
            MinValueValidator(1),   # minimum rating: 1
            MaxValueValidator(5),   # matches the database schema CHECK(rating BETWEEN 1 AND 5)
        ]
    )
    comments = models.TextField(blank=True)
    date     = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table       = "feedback"
        unique_together = ("guest", "resv")  # one review per stay per guest

    def __str__(self):
        return (
            f"Feedback #{self.pk} — {self.guest.guest_name} "
            f"★{self.rating}/5 (Resv #{self.resv_id})"
        )
