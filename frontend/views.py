import json
import logging
import secrets
import smtplib
import time
from decimal import Decimal
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen
from datetime import datetime

import jwt
from django.conf import settings
from django.contrib.auth import authenticate, get_user_model, login
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import PasswordResetForm
from django.contrib.auth.hashers import check_password, make_password
from django.db import transaction
from django.http import JsonResponse
from django.shortcuts import redirect, render
from django.views.decorators.http import require_http_methods

from apps.guests.models import Guest
from apps.billing.models import Invoice
from apps.reservations.models import Reservation, RoomReservation
from apps.rooms.models import Room


Staff = get_user_model()
logger = logging.getLogger(__name__)


def _begin_two_factor(request, user):
    """Send a short-lived email code before creating an authenticated session."""
    code = f"{secrets.randbelow(1_000_000):06d}"
    request.session["pending_login_user_id"] = user.id
    request.session["pending_login_code"] = make_password(code)
    request.session["pending_login_expires_at"] = time.time() + 600
    channel = request.session.get("pending_login_channel", "email")
    try:
        if channel == "sms":
            phone_number = (user.staff_phone or "").strip()
            if not phone_number:
                raise ValueError("SMS verification requires a phone number")
            _send_verification_sms(phone_number, code)
        else:
            from django.core.mail import send_mail

            send_mail(
                "Your StayHub verification code",
                f"Your verification code is {code}. It expires in 10 minutes.",
                settings.DEFAULT_FROM_EMAIL,
                [user.email],
                fail_silently=False,
            )
    except (smtplib.SMTPException, OSError, HTTPError, URLError, ValueError):
        logger.exception("Unable to send two-factor %s to %s", channel, user.email)
        for key in ("pending_login_user_id", "pending_login_code", "pending_login_expires_at"):
            request.session.pop(key, None)
        return {"sent": False, "dev_code": None}
    request.session.pop("pending_login_dev_code", None)
    return {"sent": True, "dev_code": None}


def _send_verification_sms(phone_number, code):
    if not settings.BREVO_API_KEY:
        raise ValueError("BREVO_API_KEY is not configured")
    payload = json.dumps({
        "sender": getattr(settings, "BREVO_SMS_SENDER", "StayHub"),
        "recipient": phone_number,
        "content": f"Your StayHub verification code is {code}. It expires in 10 minutes.",
        "type": "transactional",
        "unicodeEnabled": True,
    }).encode("utf-8")
    request = Request(
        "https://api.brevo.com/v3/transactionalSMS/send",
        data=payload,
        headers={
            "accept": "application/json",
            "api-key": settings.BREVO_API_KEY,
            "content-type": "application/json",
        },
        method="POST",
    )
    with urlopen(request, timeout=15) as response:
        if response.status >= 300:
            raise ValueError(f"Brevo SMS API returned HTTP {response.status}")


def _complete_or_challenge_login(request, user):
    challenge = _begin_two_factor(request, user)
    if not challenge["sent"]:
        return JsonResponse({
            "detail": "We couldn't send the verification code. Please try again later.",
        }, status=503)
    channel = request.session.get("pending_login_channel", "email")
    response = {
        "detail": f"We sent a verification code to your {channel}.",
        "two_factor_required": True,
        "redirect_url": "/verification/",
    }
    return JsonResponse(response, status=202)


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


@login_required(login_url="signin")
def profile(request):
    """Show and update the signed-in user's profile."""
    user = request.user
    if request.method == "POST":
        full_name = (request.POST.get("full_name") or "").strip()
        email = (request.POST.get("email") or "").strip().lower()
        staff_phone = (request.POST.get("staff_phone") or "").strip()
        upload = request.FILES.get("profile_picture")
        if not full_name or not email:
            return render(request, "frontend/profile.html", {"profile_error": "Name and email are required."})
        if Staff.objects.filter(email__iexact=email).exclude(pk=user.pk).exists():
            return render(request, "frontend/profile.html", {"profile_error": "That email is already in use."})
        parts = full_name.split(maxsplit=1)
        user.staff_name = full_name
        user.first_name = parts[0]
        user.last_name = parts[1] if len(parts) > 1 else ""
        user.email = email
        user.username = email
        user.staff_phone = staff_phone
        if request.POST.get("clear_picture") == "1" and user.profile_picture:
            user.profile_picture.delete(save=False)
            user.profile_picture = None
        if upload:
            if upload.size > 5 * 1024 * 1024 or not (upload.content_type or "").startswith("image/"):
                return render(request, "frontend/profile.html", {"profile_error": "Use an image file smaller than 5 MB."})
            user.profile_picture = upload
        user.save()
        return redirect("profile")
    return render(request, "frontend/profile.html")


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
    verification_channel = str(payload.get("verification_channel") or "email").strip().lower()

    if not identifier or not password:
        return JsonResponse({"detail": "username/email and password are required."}, status=400)
    if verification_channel not in {"email", "sms"}:
        return JsonResponse({"detail": "verification_channel must be email or sms."}, status=400)

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

    if verification_channel == "sms" and not (authenticated_user.staff_phone or "").strip():
        return JsonResponse({"detail": "Add a phone number to use SMS verification."}, status=400)

    request.session["pending_login_channel"] = verification_channel

    return _complete_or_challenge_login(request, authenticated_user)


def staff_login(request):
    """Staff portal login page."""
    return render(request, "frontend/staff_login.html")


def create_account(request):
    """New user registration page."""
    return render(request, "frontend/create_account.html")


def password_reset(request):
    """Email a safe reset link without revealing whether an address exists."""
    if request.method == "POST":
        form = PasswordResetForm(request.POST)
        if form.is_valid():
            try:
                form.save(
                    request=request,
                    use_https=request.is_secure(),
                    from_email=settings.DEFAULT_FROM_EMAIL,
                    email_template_name="frontend/password_reset_email.html",
                    subject_template_name="frontend/password_reset_subject.txt",
                )
            except (smtplib.SMTPException, OSError):
                # Do not reveal account existence or turn a mail outage into a 500.
                logger.exception("Unable to send password-reset email")
        return redirect("password_reset_done")
    return render(request, "frontend/password_reset.html")


def two_factor(request):
    if not request.session.get("pending_login_user_id"):
        return redirect("signin")
    return render(request, "frontend/verification.html", {
        "verification_channel": request.session.get("pending_login_channel", "email"),
    })


@require_http_methods(["POST"])
def api_two_factor_verify(request):
    try:
        payload = json.loads(request.body.decode("utf-8")) if request.body else {}
    except json.JSONDecodeError:
        return JsonResponse({"detail": "Invalid JSON payload."}, status=400)
    user_id = request.session.get("pending_login_user_id")
    expires_at = request.session.get("pending_login_expires_at", 0)
    expected_code = request.session.get("pending_login_code", "")
    code = str(payload.get("code", "")).strip()
    if not user_id or time.time() > expires_at:
        request.session.flush()
        return JsonResponse({"detail": "This code has expired. Sign in again."}, status=400)
    if not code or not check_password(code, expected_code):
        return JsonResponse({"detail": "That verification code is not valid."}, status=400)
    user = Staff.objects.filter(pk=user_id, is_active=True).first()
    if user is None:
        return JsonResponse({"detail": "Account unavailable."}, status=400)
    login(request, user)
    for key in ("pending_login_user_id", "pending_login_code", "pending_login_expires_at"):
        request.session.pop(key, None)
    return JsonResponse({"detail": "Signed in successfully.", "redirect_url": _redirect_for_role(user.role)})


def google_login(request):
    if not settings.GOOGLE_OAUTH_CLIENT_ID or not settings.GOOGLE_OAUTH_CLIENT_SECRET:
        return redirect("signin")
    state = secrets.token_urlsafe(32)
    request.session["google_oauth_state"] = state
    query = urlencode({
        "client_id": settings.GOOGLE_OAUTH_CLIENT_ID,
        "redirect_uri": settings.GOOGLE_OAUTH_REDIRECT_URI,
        "response_type": "code",
        "scope": "openid email profile",
        "state": state,
        "prompt": "select_account",
    })
    return redirect(f"https://accounts.google.com/o/oauth2/v2/auth?{query}")


def google_callback(request):
    if request.GET.get("state") != request.session.pop("google_oauth_state", None):
        return redirect("signin")
    if request.GET.get("error") or not request.GET.get("code"):
        return redirect("signin")
    try:
        data = urlencode({
            "code": request.GET["code"], "client_id": settings.GOOGLE_OAUTH_CLIENT_ID,
            "client_secret": settings.GOOGLE_OAUTH_CLIENT_SECRET,
            "redirect_uri": settings.GOOGLE_OAUTH_REDIRECT_URI, "grant_type": "authorization_code",
        }).encode()
        token_request = Request("https://oauth2.googleapis.com/token", data=data, method="POST")
        token_data = json.loads(urlopen(token_request, timeout=10).read().decode())
        claims = jwt.decode(token_data["id_token"], options={"verify_signature": False})
        if claims.get("aud") != settings.GOOGLE_OAUTH_CLIENT_ID or claims.get("iss") not in {"accounts.google.com", "https://accounts.google.com"} or not claims.get("email_verified"):
            raise ValueError("Invalid Google identity token")
        email = claims["email"].lower()
        full_name = claims.get("name") or email.split("@", 1)[0]
        user, created = Staff.objects.get_or_create(email=email, defaults={
            "username": email, "staff_name": full_name, "role": "guest",
            "first_name": claims.get("given_name", ""), "last_name": claims.get("family_name", ""),
        })
        if created:
            user.set_unusable_password()
            user.save(update_fields=["password"])
    except Exception:
        return redirect("signin")
    challenge = _begin_two_factor(request, user)
    if not challenge["sent"]:
        return redirect("signin")
    return redirect("verification")


@require_http_methods(["POST"])
def api_register(request):
    """Create a guest account from the public registration form."""
    try:
        payload = json.loads(request.body.decode("utf-8")) if request.body else {}
    except json.JSONDecodeError:
        return JsonResponse({"detail": "Invalid JSON payload."}, status=400)

    full_name = (payload.get("full_name") or payload.get("name") or "").strip()
    email = (payload.get("email") or "").strip().lower()
    staff_phone = (payload.get("staff_phone") or payload.get("phone") or "").strip()
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
        staff_phone=staff_phone,
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
    name = request.user.get_full_name().strip() if request.user.is_authenticated else "Guest"
    name = name or (request.user.staff_name if request.user.is_authenticated else "Guest")
    return render(request, "frontend/guest_home.html", {"display_name": name})


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
        .order_by("hotel__hotel_name", "price_per_night", "room_number")
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
                "price_per_night": str(room.price_per_night or (room.room_type.price_per_night if room.room_type else 0)) if room.room_type or room.price_per_night else None,
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
            hotel=room.hotel,
            check_in=check_in,
            check_out=check_out,
            status=Reservation.ReservationStatus.CONFIRMED,
        )
        RoomReservation.objects.create(resv=reservation, room=room)
        room.status = Room.RoomStatus.RESERVED
        room.reservation = reservation
        room.save(update_fields=["status", "reservation"])

        nightly_rate = room.price_per_night or (room.room_type.price_per_night if room.room_type else 0)
        nights = max(1, (check_out.date() - check_in.date()).days)
        service_fee = 45
        tax = round((nightly_rate * nights + service_fee) * Decimal("0.12"), 2)
        total_amount = (nightly_rate * nights) + service_fee + tax
        invoice = Invoice.objects.create(hotel=room.hotel, reservation=reservation, total_amount=total_amount)

    return JsonResponse(
        {
            "detail": "Booking created successfully.",
            "reservation": {
                "id": reservation.id,
                "status": reservation.status,
                "check_in": reservation.check_in.isoformat(),
                "check_out": reservation.check_out.isoformat(),
            },
            "invoice": {
                "id": invoice.id,
                "total_amount": str(invoice.total_amount),
                "status": invoice.status,
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
