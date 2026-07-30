from django.db import models
 
 
class Hotel(models.Model):
    class Category(models.TextChoices):
        RESORT      = "RESORT",       "Resort"
        CABIN       = "CABIN",        "Cabin"
        VILLA       = "VILLA",        "Villa"
        HOTEL       = "HOTEL",        "Hotel"
        APARTMENT   = "APARTMENT",    "Apartment"
        HOMESTAY    = "HOMESTAY",     "Homestay"
        GUEST_HOUSE = "GUEST_HOUSE",  "Guest House"
        OTHER       = "OTHER",        "Other"

    hotel_email   = models.CharField(max_length=100, unique=True)
    hotel_address = models.TextField()
    hotel_name    = models.CharField(max_length=255)
    hotel_phone   = models.CharField(max_length=20)
    category      = models.CharField(max_length=20, choices=Category.choices, default=Category.HOTEL)
    hotel_image   = models.ImageField(upload_to="hotel_images/", blank=True, null=True)
    created_at    = models.DateTimeField(auto_now_add=True)
 
    class Meta:
        db_table = "hotel"
 
    def __str__(self):
        return self.hotel_name
 
 
class Department(models.Model):
    hotel     = models.ForeignKey(Hotel, on_delete=models.CASCADE,
                                  related_name="departments")
    dept_name = models.CharField(max_length=100)
 
    class Meta:
        db_table = "department"
 
    def __str__(self):
        return f"{self.dept_name} — {self.hotel.hotel_name}"
