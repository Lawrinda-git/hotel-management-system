from django.db import models


class RoomType(models.Model):
    """
    Defines the category of a room — e.g. Standard, Deluxe, Suite.
    Price is set here at the type level so all rooms of the same
    type automatically share the same nightly rate.
    """

    hotel           = models.ForeignKey("hotels.Hotel", on_delete=models.CASCADE, null=True, blank=True, related_name="room_types")
    type_name       = models.CharField(max_length=100)
    price_per_night = models.DecimalField(max_digits=10, decimal_places=2)
    description     = models.TextField(blank=True)

    class Meta:
        db_table = "room_type"
        constraints = [models.UniqueConstraint(fields=("hotel", "type_name"), name="room_type_hotel_name_unique")]

    def __str__(self):
        return f"{self.type_name} (GH₵{self.price_per_night}/night)"


class Room(models.Model):
    """
    A single physical room in the hotel.
    - hotel      : which hotel this room belongs to
    - room_type  : determines the price and category
    - status     : current booking state
    - housekeeping_status : current cleanliness state
    """

    # ── Status choices ──────────────────────────────────────
    # TextChoices stores a human-readable string in the DB
    # ("AVAILABLE") instead of a raw integer.
    # This makes the database readable without needing a lookup table.

    class RoomStatus(models.TextChoices):
        AVAILABLE   = "AVAILABLE",    "Available"
        OCCUPIED    = "OCCUPIED",     "Occupied"
        RESERVED    = "RESERVED",     "Reserved"
        MAINTENANCE = "MAINTENANCE",  "Under Maintenance"

    class HousekeepingStatus(models.TextChoices):
        DIRTY         = "DIRTY",          "Dirty"
        CLEAN         = "CLEAN",          "Clean"
        INSPECTED     = "INSPECTED",      "Inspected"
        OUT_OF_SERVICE = "OUT_OF_SERVICE", "Out of Service"

    # ── Fields ──────────────────────────────────────────────
    hotel = models.ForeignKey(
        "hotels.Hotel",
        on_delete=models.CASCADE,       # delete hotel → delete all its rooms
        related_name="rooms",
    )
    room_type = models.ForeignKey(
        RoomType,
        on_delete=models.SET_NULL,      # deleting a type doesn't delete rooms
        null=True,
        related_name="rooms",
    )
    reservation = models.ForeignKey(
        "reservations.Reservation", on_delete=models.SET_NULL, null=True, blank=True,
        related_name="assigned_rooms",
    )
    room_number         = models.CharField(max_length=10)
    image               = models.CharField(max_length=255, blank=True, default="", help_text="Static image path, e.g. frontend/img/xxx.jpg")
    price_per_night     = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    status              = models.CharField(
        max_length=20,
        choices=RoomStatus.choices,
        default=RoomStatus.AVAILABLE,
    )
    floor               = models.SmallIntegerField(null=True, blank=True)
    housekeeping_status = models.CharField(
        max_length=20,
        choices=HousekeepingStatus.choices,
        default=HousekeepingStatus.DIRTY,   # always dirty until cleaned after checkout
    )

    class Meta:
        db_table       = "room"
        unique_together = ("hotel", "room_number")  # no two rooms share the same number per hotel

    def __str__(self):
        return f"Room {self.room_number} — {self.room_type} [{self.status}]"


class Maintenance(models.Model):
    """
    A maintenance issue reported for a specific room.
    - staff  : the staff member assigned to handle it
    - room   : which room has the problem
    - status : tracks progress from OPEN to RESOLVED
    """

    class MaintenanceStatus(models.TextChoices):
        OPEN        = "OPEN",        "Open"
        IN_PROGRESS = "IN_PROGRESS", "In Progress"
        RESOLVED    = "RESOLVED",    "Resolved"
        CLOSED      = "CLOSED",      "Closed"

    staff = models.ForeignKey(
        "accounts.Staff",
        on_delete=models.SET_NULL,      # keep record even if staff member is removed
        null=True,
        related_name="maintenance_tasks",
    )
    hotel = models.ForeignKey(
        "hotels.Hotel", on_delete=models.CASCADE, null=True, blank=True, related_name="maintenance_records",
    )
    room = models.ForeignKey(
        Room,
        on_delete=models.CASCADE,       # room deleted → maintenance records gone too
        related_name="maintenance_records",
    )
    issue        = models.TextField()
    report_date  = models.DateField(auto_now_add=True)  # set automatically on creation
    resolve_date = models.DateField(null=True, blank=True)  # filled when resolved
    status       = models.CharField(
        max_length=20,
        choices=MaintenanceStatus.choices,
        default=MaintenanceStatus.OPEN,
    )

    class Meta:
        db_table = "maintenance"

    def __str__(self):
        return f"Maintenance #{self.pk} — Room {self.room.room_number} [{self.status}]"
