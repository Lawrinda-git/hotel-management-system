from rest_framework.routers import DefaultRouter

from .views import ReservationViewSet, RoomReservationViewSet


router = DefaultRouter()
router.register(r"reservations", ReservationViewSet, basename="reservation")
router.register(r"room-reservations", RoomReservationViewSet, basename="room-reservation")

urlpatterns = router.urls