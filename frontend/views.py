from django.shortcuts import render

# ─── Public / Customer Pages ────────────────────────────────────

def splash(request):
    """Landing splash screen for StayHub."""
    return render(request, "frontend/splash.html")


def signin(request):
    """Customer sign-in page."""
    return render(request, "frontend/signin.html")


def staff_login(request):
    """Staff portal login page."""
    return render(request, "frontend/staff_login.html")


def create_account(request):
    """New user registration page."""
    return render(request, "frontend/create_account.html")


def guest_home(request):
    """Main customer home/explore page after login."""
    return render(request, "frontend/guest_home.html")


def explore_stays(request):
    """Room booking / explore stays page."""
    return render(request, "frontend/explore_stays.html")


def hotel_details(request):
    """Detailed view of a single hotel."""
    return render(request, "frontend/hotel_details.html")


def booking(request):
    """Booking configuration / reservation page."""
    return render(request, "frontend/booking.html")


# ─── Staff Dashboard Pages ──────────────────────────────────────

def manager_dashboard(request):
    """Manager/Admin dashboard view."""
    return render(request, "frontend/manager_dashboard.html")


def receptionist_dashboard(request):
    """Receptionist operations dashboard."""
    return render(request, "frontend/receptionist_dashboard.html")


def accountant_dashboard(request):
    """Accountant/financial dashboard."""
    return render(request, "frontend/accountant_dashboard.html")


def housekeeping_dashboard(request):
    """Housekeeping operations dashboard."""
    return render(request, "frontend/housekeeping_dashboard.html")


def design_system(request):
    """Design system / hero welcome page."""
    return render(request, "frontend/design_system.html")