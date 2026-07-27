from django.contrib.auth import views as auth_views
from django.urls import path

from . import views

urlpatterns = [
    # Public / Customer Pages
    path("", views.splash, name="splash"),
    path("splash/", views.splash, name="splash_page"),
    path("landing/", views.landing, name="landing"),
    path("signin/", views.signin, name="signin"),
    path("api/health/database/", views.database_health, name="database_health"),
    path("profile/", views.profile, name="profile"),
    path("staff-login/", views.staff_login, name="staff_login"),
    path("admin-signup/", views.admin_signup, name="admin_signup"),
    path("logout/", views.logout_view, name="logout"),
    path("create-account/", views.create_account, name="create_account"),
    path("api/auth/login/", views.api_login, name="api_login"),
    path("api/auth/register/", views.api_register, name="api_register"),
    path("api/auth/google/", views.google_login, name="google_login"),
    path("api/auth/google/callback/", views.google_callback, name="google_callback"),
    path("verification/", views.two_factor, name="verification"),
    path("verification-method/", views.verification_method, name="verification_method"),
    path("two-factor/", views.two_factor, name="two_factor"),
    path("api/auth/two-factor/verify/", views.api_two_factor_verify, name="api_two_factor_verify"),
    path("password-reset/", views.password_reset, name="password_reset"),
    path("password-reset/done/", auth_views.PasswordResetDoneView.as_view(template_name="frontend/password_reset_done.html"), name="password_reset_done"),
    path("reset/<uidb64>/<token>/", auth_views.PasswordResetConfirmView.as_view(template_name="frontend/password_reset_confirm.html"), name="password_reset_confirm"),
    path("reset/done/", auth_views.PasswordResetCompleteView.as_view(template_name="frontend/password_reset_complete.html"), name="password_reset_complete"),
    path("home/", views.guest_home, name="guest_home"),
    path("explore/", views.explore_stays, name="explore_stays"),
    path("hotel-details/", views.hotel_details, name="hotel_details"),
    path("team/", views.team, name="team"),
    path("booking/", views.booking, name="booking"),
    path("api/booking/options/", views.booking_options, name="booking_options"),
    path("api/booking/create/", views.create_booking, name="create_booking"),
    # Staff Dashboard Pages
    path("manager/", views.manager_dashboard, name="manager_dashboard"),
    path("receptionist/", views.receptionist_dashboard, name="receptionist_dashboard"),
    path("accountant/", views.accountant_dashboard, name="accountant_dashboard"),
    path("housekeeping/", views.housekeeping_dashboard, name="housekeeping_dashboard"),
    path("design-system/", views.design_system, name="design_system"),
]
