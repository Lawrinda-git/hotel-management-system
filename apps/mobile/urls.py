from django.urls import path
from . import views

urlpatterns = [
    path("api/mobile/rooms/", views.mobile_rooms, name="mobile_rooms"),
    path("api/mobile/checkin/", views.mobile_checkin, name="mobile_checkin"),
    path("api/mobile/checkout/", views.mobile_checkout, name="mobile_checkout"),
    path("api/mobile/housekeeping/update/", views.mobile_housekeeping_update, name="mobile_housekeeping_update"),
]