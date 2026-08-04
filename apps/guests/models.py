from django.contrib.auth.hashers import check_password, make_password
from django.db import models


class Guest(models.Model):
    """
    A hotel guest — someone who makes reservations and stays at the hotel.
    Guests are NOT staff and do NOT log in to the staff system.
    They are identified by their id_number (passport / national ID).

    unique=True on guest_email and id_number means no two guests
    can share the same email address or ID document number.

    Guests who register on the public web app get a hashed ``password``
    so they can sign in to view their bookings — but they remain in the
    ``guest`` table, never in the ``staff`` table.
    """

    guest_name  = models.CharField(max_length=100)
    guest_phone = models.CharField(max_length=20, blank=True)
    guest_email = models.CharField(max_length=100, unique=True)
    id_number   = models.CharField(max_length=50, unique=True, blank=True, null=True)   # passport or national ID
    nationality = models.CharField(max_length=50, blank=True)
    password    = models.CharField(max_length=128, blank=True, default="")  # hashed; blank = walk-in guest
    is_active   = models.BooleanField(default=True)
    created_at  = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "guest"

    def __str__(self):
        return f"{self.guest_name} ({self.guest_email})"

    # ── Password helpers (mirror Django's AbstractBaseUser API) ──
    def set_password(self, raw_password):
        self.password = make_password(raw_password)

    def check_password(self, raw_password):
        if not self.password:
            return False
        return check_password(raw_password, self.password)

    def get_full_name(self):
        return self.guest_name

    def get_short_name(self):
        return self.guest_name.split()[0] if self.guest_name else ""