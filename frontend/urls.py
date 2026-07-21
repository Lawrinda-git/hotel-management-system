from django.urls import path

from . import views

urlpatterns = [
    # Public / Customer Pages
    path("", views.splash, name="splash"),
    path("signin/", views.signin, name="signin"),
    path("staff-login/", views.staff_login, name="staff_login"),
    path("create-account/", views.create_account, name="create_account"),
    path("home/", views.guest_home, name="guest_home"),
    path("explore/", views.explore_stays, name="explore_stays"),
    path("hotel-details/", views.hotel_details, name="hotel_details"),
    path("booking/", views.booking, name="booking"),
    # Staff Dashboard Pages
    path("manager/", views.manager_dashboard, name="manager_dashboard"),
    path("receptionist/", views.receptionist_dashboard, name="receptionist_dashboard"),
    path("accountant/", views.accountant_dashboard, name="accountant_dashboard"),
    path("housekeeping/", views.housekeeping_dashboard, name="housekeeping_dashboard"),
    path("design-system/", views.design_system, name="design_system"),
]