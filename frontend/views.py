import json
from datetime import datetime

from django.contrib.auth import authenticate, get_user_model, login
from django.db import transaction
from django.http import JsonResponse
from django.shortcuts import render
from django.views.decorators.http import require_http_methods

from apps.guests.models import Guest
from apps.reservations.models import Reservation, RoomReservation
from apps.rooms.models import Room


Staff = get_user_model()


def _redirect_for_role(role):
    dashboard_routes = {
        "manager": "/manager/",
        "receptionist": "/receptionist/",
        "accountant": "/accountant/",
        "housekeeping": "/housekeeping/",
    }
    return dashboard_routes.get((role or "").lower(), "/home/")

# ─── Public / Customer Pages ────────────────────────────────────

def splash(request):
    """Landing splash screen for StayHub."""
    return render(request, "frontend/splash.html")


def signin(request):
    """Customer sign-in page."""
    return render(request, "frontend/signin.html")


@require_http_methods(["POST"])
def api_login(request):
    """Authenticate a user and establish a Django session."""
    try:
        payload = json.loads(request.body.decode("utf-8")) if request.body else {}
    except json.JSONDecodeError:
        return JsonResponse({"detail": "Invalid JSON payload."}, status=400)

    identifier = (
        payload.get("username")
        or payload.get("email")
        or payload.get("identifier")
        or ""
    ).strip()
    password = (payload.get("password") or "").strip()

    if not identifier or not password:
        return JsonResponse({"detail": "username/email and password are required."}, status=400)

    user = None
    if "@" in identifier:
        user = Staff.objects.filter(email__iexact=identifier).first()
    if user is None:
        user = Staff.objects.filter(username__iexact=identifier).first()

    if user is None:
        return JsonResponse({"detail": "Invalid credentials."}, status=400)

    authenticated_user = authenticate(request, username=user.username, password=password)
    if authenticated_user is None:
        return JsonResponse({"detail": "Invalid credentials."}, status=400)

    login(request, authenticated_user)
    return JsonResponse(
        {
            "detail": "Signed in successfully.",
            "role": authenticated_user.role,
            "redirect_url": _redirect_for_role(authenticated_user.role),
        }
    )


def staff_login(request):
    """Staff portal login page."""
    return render(request, "frontend/staff_login.html")


def create_account(request):
    """New user registration page."""
    return render(request, "frontend/create_account.html")


@require_http_methods(["POST"])
def api_register(request):
    """Create a guest account from the public registration form."""
    try:
        payload = json.loads(request.body.decode("utf-8")) if request.body else {}
    except json.JSONDecodeError:
        return JsonResponse({"detail": "Invalid JSON payload."}, status=400)

    full_name = (payload.get("full_name") or payload.get("name") or "").strip()
    email = (payload.get("email") or "").strip().lower()
    password = (payload.get("password") or "").strip()

    if not full_name or not email or not password:
        return JsonResponse({"detail": "full_name, email, and password are required."}, status=400)

    if Staff.objects.filter(username__iexact=email).exists() or Staff.objects.filter(email__iexact=email).exists():
        return JsonResponse({"detail": "An account with that email already exists."}, status=409)

    name_parts = full_name.split(maxsplit=1)
    first_name = name_parts[0]
    last_name = name_parts[1] if len(name_parts) > 1 else ""

    user = Staff.objects.create_user(
        username=email,
        email=email,
        password=password,
        staff_name=full_name,
        role="guest",
        first_name=first_name,
        last_name=last_name,
    )

    return JsonResponse(
        {
            "detail": "Account created successfully.",
            "user": {
                "id": user.id,
                "email": user.email,
                "role": user.role,
            },
        },
        status=201,
    )


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


@require_http_methods(["GET"])
def booking_options(request):
    """Return rooms that can be shown on the booking page."""
    rooms = (
        Room.objects.select_related("hotel", "room_type")
        .filter(status=Room.RoomStatus.AVAILABLE)
        .order_by("hotel__hotel_name", "room_type__price_per_night", "room_number")
    )

    payload = [
        {
            "id": room.id,
            "room_number": room.room_number,
            "status": room.status,
            "floor": room.floor,
            "hotel": {
                "id": room.hotel_id,
                "hotel_name": room.hotel.hotel_name,
            },
            "room_type": {
                "id": room.room_type_id,
                "type_name": room.room_type.type_name if room.room_type else None,
                "price_per_night": str(room.room_type.price_per_night) if room.room_type else None,
                "description": room.room_type.description if room.room_type else "",
            },
        }
        for room in rooms
    ]
    return JsonResponse({"results": payload})


@require_http_methods(["POST"])
def create_booking(request):
    """Create a guest, reservation, and room link in one request."""
    try:
        payload = json.loads(request.body.decode("utf-8")) if request.body else {}
    except json.JSONDecodeError:
        return JsonResponse({"detail": "Invalid JSON payload."}, status=400)

    guest_name = (payload.get("guest_name") or "").strip()
    guest_email = (payload.get("guest_email") or "").strip().lower()
    guest_phone = (payload.get("guest_phone") or "").strip()
    id_number = (payload.get("id_number") or "").strip()
    nationality = (payload.get("nationality") or "").strip()
    check_in_raw = (payload.get("check_in") or "").strip()
    check_out_raw = (payload.get("check_out") or "").strip()
    room_id = payload.get("room_id")

    if not all([guest_name, guest_email, id_number, check_in_raw, check_out_raw, room_id]):
        return JsonResponse(
            {"detail": "guest_name, guest_email, id_number, room_id, check_in, and check_out are required."},
            status=400,
        )

    try:
        check_in = datetime.fromisoformat(check_in_raw)
        check_out = datetime.fromisoformat(check_out_raw)
    except ValueError:
        return JsonResponse({"detail": "check_in and check_out must be ISO 8601 datetimes."}, status=400)

    if check_out <= check_in:
        return JsonResponse({"detail": "check_out must be after check_in."}, status=400)

    try:
        room = Room.objects.select_related("hotel", "room_type").get(pk=room_id)
    except Room.DoesNotExist:
        return JsonResponse({"detail": "Selected room does not exist."}, status=404)

    if room.status != Room.RoomStatus.AVAILABLE:
        return JsonResponse({"detail": "Selected room is not available."}, status=409)

    with transaction.atomic():
        guest, _ = Guest.objects.get_or_create(
            guest_email=guest_email,
            defaults={
                "guest_name": guest_name,
                "guest_phone": guest_phone,
                "id_number": id_number,
                "nationality": nationality,
            },
        )

        changed_fields = []
        if guest.guest_name != guest_name:
            guest.guest_name = guest_name
            changed_fields.append("guest_name")
        if guest.guest_phone != guest_phone:
            guest.guest_phone = guest_phone
            changed_fields.append("guest_phone")
        if guest.id_number != id_number:
            guest.id_number = id_number
            changed_fields.append("id_number")
        if guest.nationality != nationality:
            guest.nationality = nationality
            changed_fields.append("nationality")
        if changed_fields:
            guest.save(update_fields=changed_fields)

        reservation = Reservation.objects.create(
            guest=guest,
            check_in=check_in,
            check_out=check_out,
            status=Reservation.ReservationStatus.CONFIRMED,
        )
        RoomReservation.objects.create(resv=reservation, room=room)
        room.status = Room.RoomStatus.RESERVED
        room.save(update_fields=["status"])

    return JsonResponse(
        {
            "detail": "Booking created successfully.",
            "reservation": {
                "id": reservation.id,
                "status": reservation.status,
                "check_in": reservation.check_in.isoformat(),
                "check_out": reservation.check_out.isoformat(),
            },
        },
        status=201,
    )


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