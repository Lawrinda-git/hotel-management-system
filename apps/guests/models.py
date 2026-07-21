from django.db import models


class Guest(models.Model):
    """
    A hotel guest — someone who makes reservations and stays at the hotel.
    Guests are NOT staff and do NOT log in to the system.
    They are identified by their id_number (passport / national ID).

    unique=True on guest_email and id_number means no two guests
    can share the same email address or ID document number.
    """

    guest_name  = models.CharField(max_length=100)
    guest_phone = models.CharField(max_length=20, blank=True)
    guest_email = models.CharField(max_length=100, unique=True)
    id_number   = models.CharField(max_length=50, unique=True, blank=True, null=True)   # passport or national ID
    nationality = models.CharField(max_length=50, blank=True)
    created_at  = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "guest"

    def __str__(self):
        return f"{self.guest_name} ({self.guest_email})"
