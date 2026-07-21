from django.db import models


class Service(models.Model):
    """
    A hotel service available to guests — e.g. Room Service,
    Laundry, Airport Transfer, Spa, Extra Towels.

    This is the SERVICE CATALOGUE — it defines what can be ordered.
    Actual orders by guests are tracked in ServiceRequest below.
    """

    hotel = models.ForeignKey("hotels.Hotel", on_delete=models.CASCADE, null=True, blank=True, related_name="services")
    service_name = models.CharField(max_length=100)
    price        = models.DecimalField(max_digits=10, decimal_places=2)
    category     = models.CharField(max_length=50, blank=True)  # e.g. "Food", "Transport"

    class Meta:
        db_table = "service"

    def __str__(self):
        return f"{self.service_name} (GH₵{self.price})"


class ServiceRequest(models.Model):
    """
    A guest's request for a specific service during their stay.

    Links three things together:
    - service  : what was ordered (from the catalogue above)
    - resv     : which reservation / stay it belongs to
    - staff    : which staff member is handling it (can be unassigned initially)

    status tracks the request from creation → completion.
    """

    class RequestStatus(models.TextChoices):
        PENDING     = "Pending",     "Pending"
        IN_PROGRESS = "In_Progress", "In Progress"
        COMPLETED   = "Completed",   "Completed"
        CANCELLED   = "Cancelled",   "Cancelled"

    service = models.ForeignKey(
        Service,
        on_delete=models.CASCADE,
        related_name="requests",
    )
    staff = models.ForeignKey(
        "accounts.Staff",
        on_delete=models.SET_NULL,      # request stays even if staff member is removed
        null=True,
        blank=True,                     # blank=True allows the field to be empty in forms
        related_name="service_requests",
    )
    resv = models.ForeignKey(
        "reservations.Reservation",
        on_delete=models.CASCADE,       # reservation deleted → its service requests deleted
        related_name="service_requests",
    )
    request_time = models.DateTimeField(auto_now_add=True)
    status       = models.CharField(
        max_length=20,
        choices=RequestStatus.choices,
        default=RequestStatus.PENDING,
    )

    class Meta:
        db_table = "service_request"

    def __str__(self):
        return (
            f"ServiceRequest #{self.pk} — {self.service.service_name} "
            f"[{self.status}]"
        )
