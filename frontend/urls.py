from django.contrib.auth import views as auth_views
from django.urls import path, reverse_lazy

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

    # Password Reset – simple verification code flow
    path("password-reset/", views.password_reset, name="password_reset"),
    path(
        "password-reset/verify/",
        views.password_reset_verify,
        name="password_reset_verify",
    ),

    path("home/", views.guest_home, name="guest_home"),
    path("explore/", views.explore_stays, name="explore_stays"),
    path("hotel-details/", views.hotel_details, name="hotel_details"),
    path("team/", views.team, name="team"),
    path("booking/", views.booking, name="booking"),
    path("api/booking/options/", views.booking_options, name="booking_options"),
    path("api/booking/create/", views.create_booking, name="create_booking"),
    path("reservation-confirmed/", views.reservation_confirmed, name="reservation_confirmed"),
    path("api/reservations/<int:reservation_id>/status/", views.reservation_status, name="reservation_status"),
    path("bookings/", views.my_bookings, name="my_bookings"),
    path("reservations/<int:reservation_id>/", views.reservation_detail, name="reservation_detail"),
    # Staff Dashboard Pages
    path("manager/", views.manager_dashboard, name="manager_dashboard"),
    path("staff/walkin/", views.walkin_booking, name="walkin_booking"),
    path("staff/reservations/", views.staff_reservations, name="staff_reservations"),
    path("receptionist/", views.receptionist_dashboard, name="receptionist_dashboard"),
    path("accountant/", views.accountant_dashboard, name="accountant_dashboard"),
    path("housekeeping/", views.housekeeping_dashboard, name="housekeeping_dashboard"),
    path("design-system/", views.design_system, name="design_system"),
    path("admin-management/", views.admin_management, name="admin_management"),
    # Admin management CRUD API (JSON, session-auth, CSRF-protected)
    path("admin-api/rooms/save/", views.admin_room_save, name="admin_room_save"),
    path("admin-api/rooms/delete/", views.admin_room_delete, name="admin_room_delete"),
    path("admin-api/staff/save/", views.admin_staff_save, name="admin_staff_save"),
    path("admin-api/staff/delete/", views.admin_staff_delete, name="admin_staff_delete"),
    path("admin-api/hotels/save/", views.admin_hotel_save, name="admin_hotel_save"),
    path("admin-api/hotels/delete/", views.admin_hotel_delete, name="admin_hotel_delete"),
    # Staff dashboard operations API (JSON, session-auth, CSRF-protected)
    path("staff-api/checkin/", views.staff_checkin, name="staff_checkin"),
    path("staff-api/checkout/", views.staff_checkout, name="staff_checkout"),
    path("staff-api/housekeeping/update/", views.staff_housekeeping_update, name="staff_housekeeping_update"),
    path("staff-api/maintenance/update/", views.staff_maintenance_update, name="staff_maintenance_update"),
    path("staff-api/assign-room/", views.staff_assign_room, name="staff_assign_room"),
    path("staff-api/guests/search/", views.staff_guest_search, name="staff_guest_search"),
    path("staff-api/payments/record/", views.staff_record_payment, name="staff_record_payment"),
    path("staff-api/export/csv/", views.accountant_export, name="accountant_export"),
    path("staff-profile/", views.profile, name="staff_profile"),
]
