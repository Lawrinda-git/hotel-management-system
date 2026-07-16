from rest_framework.routers import DefaultRouter

from .views import ServiceRequestViewSet, ServiceViewSet


router = DefaultRouter()
router.register(r"services", ServiceViewSet, basename="service")
router.register(r"service-requests", ServiceRequestViewSet, basename="service-request")

urlpatterns = router.urls