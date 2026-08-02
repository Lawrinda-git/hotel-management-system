from django.urls import path
from . import views

# Mounted under /api/mobile/ in config/urls.py — do NOT repeat the prefix here.
urlpatterns = [
    path("rooms/", views.mobile_rooms, name="mobile_rooms"),
    path("checkin/", views.mobile_checkin, name="mobile_checkin"),
    path("checkout/", views.mobile_checkout, name="mobile_checkout"),
    path("housekeeping/update/", views.mobile_housekeeping_update, name="mobile_housekeeping_update"),
]