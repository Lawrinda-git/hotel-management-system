from rest_framework.routers import DefaultRouter

from django.urls import path

from .views import InvoiceViewSet, PaymentViewSet, create_paystack_checkout, paystack_webhook, verify_paystack_payment


router = DefaultRouter()
router.register(r"invoices", InvoiceViewSet, basename="invoice")
router.register(r"payments", PaymentViewSet, basename="payment")

urlpatterns = router.urls
urlpatterns += [
	path("paystack/checkout/", create_paystack_checkout, name="paystack_checkout"),
	path("paystack/webhook/", paystack_webhook, name="paystack_webhook"),
	path("paystack/verify/<str:reference>/", verify_paystack_payment, name="paystack_verify"),
]
