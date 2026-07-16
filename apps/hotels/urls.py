from rest_framework.routers import DefaultRouter

from .views import DepartmentViewSet, HotelViewSet


router = DefaultRouter()
router.register(r"hotels", HotelViewSet, basename="hotel")
router.register(r"departments", DepartmentViewSet, basename="department")

urlpatterns = router.urls