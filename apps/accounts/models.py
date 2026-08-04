from django.contrib.auth.models import AbstractUser
from django.db import models
 
 
class Staff(AbstractUser):
    hotel = models.ForeignKey(
        "hotels.Hotel",
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name="staff_members",
    )
    department = models.ForeignKey(
        "hotels.Department",
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name="staff_members",
    )
    staff_name  = models.CharField(max_length=100)
    staff_phone = models.CharField(max_length=20, blank=True)
    role        = models.CharField(max_length=50)
    hired_at    = models.DateTimeField(auto_now_add=True)
    profile_picture = models.FileField(upload_to="profile_pictures/", blank=True, null=True)
    two_factor_enabled = models.BooleanField(default=False, help_text="Require a one-time code by email/SMS when signing in.")
 
    class Meta:
        db_table = "staff"
 
    def __str__(self):
        return f"{self.staff_name} ({self.role})"
