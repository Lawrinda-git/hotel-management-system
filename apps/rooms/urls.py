from rest_framework.routers import DefaultRouter

from .views import MaintenanceViewSet, RoomTypeViewSet, RoomViewSet


router = DefaultRouter()
router.register(r"room-types", RoomTypeViewSet, basename="room-type")
router.register(r"rooms", RoomViewSet, basename="room")
router.register(r"maintenance", MaintenanceViewSet, basename="maintenance")

urlpatterns = router.urls