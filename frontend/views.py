import json
import logging
import re
import secrets
import smtplib
import time
from decimal import Decimal
from urllib.parse import urlencode, urlparse
from datetime import datetime

import jwt
import requests
from django.conf import settings
from django.contrib.auth import authenticate, get_user_model, login, logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import PasswordResetForm
from django.contrib.auth.hashers import check_password, make_password
from django.db import connection, transaction
from django.http import JsonResponse
from django.shortcuts import redirect, render
from django.utils import timezone
from django.views.decorators.http import require_http_methods

from apps.guests.models import Guest
from apps.billing.models import Invoice
from apps.reservations.models import Reservation, RoomReservation
from apps.rooms.models import Room


Staff = get_user_model()
logger = logging.getLogger(__name__)


def _phone_value(country_code, local_number):
    country_code = (country_code or "+233").strip()
    local_number = (local_number or "").strip()
    if local_number.startswith("+"):
        value = local_number
    else:
        value = f"{country_code}{local_number.lstrip('0')}"
    return value if re.fullmatch(r"\+[1-9]\d{7,14}", value) else ""


def _ghana_card_valid(value):
    return bool(re.fullmatch(r"GHA-\d{9}-\d", (value or "").strip().upper()))


def _google_redirect_uri(request):
    """Choose the registered callback matching the URL the user opened."""
    request_host = request.get_host().split(":", 1)[0].lower()
    for redirect_uri in settings.GOOGLE_OAUTH_REDIRECT_URIS:
        if urlparse(redirect_uri).hostname == request_host:
            return redirect_uri
    return settings.GOOGLE_OAUTH_REDIRECT_URI


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
    except (smtplib.SMTPException, OSError, requests.RequestException, ValueError):
        logger.exception("Unable to send two-factor %s to %s", channel, user.email)
        for key in ("pending_login_user_id", "pending_login_code", "pending_login_expires_at"):
            request.session.pop(key, None)
        return {"sent": False, "dev_code": None}
    request.session.pop("pending_login_dev_code", None)
    return {"sent": True, "dev_code": None}


def _send_verification_sms(phone_number, code):
    if not settings.BREVO_API_KEY:
        raise ValueError("BREVO_API_KEY is not configured")
    payload = {
        "sender": getattr(settings, "BREVO_SMS_SENDER", "StayHub"),
        "recipient": phone_number,
        "content": f"Your StayHub verification code is {code}. It expires in 10 minutes.",
        "type": "transactional",
        "unicodeEnabled": True,
    }
    response = requests.post(
        "https://api.brevo.com/v3/transactionalSMS/send",
        json=payload,
        headers={"api-key": settings.BREVO_API_KEY},
        timeout=15,
    )
    if response.status_code >= 300:
        raise ValueError(f"Brevo SMS API returned HTTP {response.status_code}: {response.text}")


def _complete_or_challenge_login(request, user):
    """Login the user directly - 2FA is optional and configured in profile."""
    login(request, user)
    return JsonResponse({
        "detail": "Signed in successfully.",
        "redirect_url": _redirect_for_role(user.role),
    })


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


def landing(request):
    """Hero landing page between splash and signin."""
    return render(request, "frontend/landing.html")


def signin(request):
    """Customer sign-in page."""
    return render(request, "frontend/signin.html")


def database_health(request):
    """Confirm the configured Django database is reachable."""
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
            cursor.fetchone()
        return JsonResponse({"status": "ok", "database": connection.vendor})
    except Exception:
        logger.exception("Database health check failed")
        return JsonResponse({"status": "error", "database": connection.vendor}, status=503)


@login_required(login_url="signin")
def profile(request):
    """Show and update the signed-in user's profile."""
    user = request.user
    phone = user.staff_phone or ""
    phone_country_code = "+233"
    phone_number = phone
    for code in ("+233", "+234", "+254", "+27", "+44", "+1"):
        if phone.startswith(code):
            phone_country_code, phone_number = code, phone[len(code):]
            break

    def render_profile(**extra):
        context = {
            "phone_country_code": phone_country_code,
            "phone_number": phone_number,
        }
        context.update(extra)
        return render(request, "frontend/profile.html", context)

    if request.method == "POST":
        full_name = (request.POST.get("full_name") or "").strip()
        email = (request.POST.get("email") or "").strip().lower()
        staff_phone = _phone_value(request.POST.get("country_code"), request.POST.get("staff_phone"))
        upload = request.FILES.get("profile_picture")
        if not full_name or not email or not staff_phone:
            return render_profile(profile_error="Name, email, and a valid phone number are required.")
        if Staff.objects.filter(email__iexact=email).exclude(pk=user.pk).exists():
            return render_profile(profile_error="That email is already in use.")
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
                return render_profile(profile_error="Use an image file smaller than 5 MB.")
            user.profile_picture = upload
        user.save()
        return redirect("profile")
    return render_profile()


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
    staff_only = bool(payload.get("staff_login"))

    if not identifier or not password:
        return JsonResponse({"detail": "username/email and password are required."}, status=400)

    user = None
    if "@" in identifier:
        user = Staff.objects.filter(email__iexact=identifier).first()
    if user is None:
        user = Staff.objects.filter(username__iexact=identifier).first()

    if user is None:
        return JsonResponse({"detail": "Invalid credentials."}, status=400)
    if staff_only and (user.role or "").lower() == "guest":
        return JsonResponse({"detail": "This account is not a staff account."}, status=403)

    authenticated_user = authenticate(request, username=user.username, password=password)
    if authenticated_user is None:
        return JsonResponse({"detail": "Invalid credentials."}, status=400)

    return _complete_or_challenge_login(request, authenticated_user)


def staff_login(request):
    """Staff portal login page."""
    if not Staff.objects.exists():
        return redirect("admin_signup")
    return render(request, "frontend/staff_login.html")


def admin_signup(request):
    """Create the first admin account or additional admins with signup key."""
    first_admin = not Staff.objects.exists()
    if request.method == "POST":
        # For first admin, skip signup key validation
        if not first_admin:
            signup_key = request.POST.get("signup_key") or ""
            if settings.ADMIN_SIGNUP_KEY and signup_key != settings.ADMIN_SIGNUP_KEY:
                return render(request, "frontend/admin_signup.html", {"error": "The admin signup key is invalid.", "first_admin": first_admin})
            if not settings.ADMIN_SIGNUP_KEY and not settings.DEBUG:
                return render(request, "frontend/admin_signup.html", {"error": "Admin signup is disabled until ADMIN_SIGNUP_KEY is configured.", "first_admin": first_admin})
        
        full_name = (request.POST.get("full_name") or "").strip()
        email = (request.POST.get("email") or "").strip().lower()
        password = request.POST.get("password") or ""
        staff_phone = _phone_value(request.POST.get("country_code"), request.POST.get("staff_phone"))
        if not full_name or not email or len(password) < 8 or not staff_phone:
            return render(request, "frontend/admin_signup.html", {"error": "Enter a name, valid email, password, and phone number.", "first_admin": first_admin})
        if Staff.objects.filter(email__iexact=email).exists() or Staff.objects.filter(username__iexact=email).exists():
            return render(request, "frontend/admin_signup.html", {"error": "An account with that email already exists.", "first_admin": first_admin})
        parts = full_name.split(maxsplit=1)
        Staff.objects.create_superuser(
            username=email, email=email, password=password, first_name=parts[0],
            last_name=parts[1] if len(parts) > 1 else "", staff_name=full_name, staff_phone=staff_phone, role="admin",
        )
        return redirect("staff_login")
    return render(request, "frontend/admin_signup.html", {"first_admin": first_admin})


def logout_view(request):
    logout(request)
    return redirect("signin")


def create_account(request):
    """New user registration page."""
    if request.user.is_authenticated:
        return redirect("guest_home")
    return render(request, "frontend/create_account.html")




def two_factor(request):
    if not request.session.get("pending_login_user_id"):
        return redirect("signin")
    return render(request, "frontend/verification.html", {
        "verification_channel": request.session.get("pending_login_channel", "email"),
    })


def verification_method(request):
    user_id = request.session.get("pending_login_user_id")
    user = Staff.objects.filter(pk=user_id, is_active=True).first() if user_id else None
    if user is None:
        return redirect("signin")
    if request.method == "POST":
        channel = (request.POST.get("verification_channel") or "").strip().lower()
        if channel not in {"email", "sms"}:
            return render(request, "frontend/verification_method.html", {"user": user, "error": "Choose email or SMS."})
        if channel == "sms" and not (user.staff_phone or "").strip():
            return render(request, "frontend/verification_method.html", {"user": user, "error": "Add a phone number to your profile before using SMS."})
        request.session["pending_login_channel"] = channel
        challenge = _begin_two_factor(request, user)
        if not challenge["sent"]:
            return render(request, "frontend/verification_method.html", {"user": user, "error": "We could not send the verification code. Try again."})
        return redirect("verification")
    return render(request, "frontend/verification_method.html", {"user": user})


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
    request.session["google_oauth_staff"] = request.GET.get("staff") == "1"
    redirect_uri = _google_redirect_uri(request)
    request.session["google_oauth_redirect_uri"] = redirect_uri
    query = urlencode({
        "client_id": settings.GOOGLE_OAUTH_CLIENT_ID,
        "redirect_uri": redirect_uri,
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
    redirect_uri = request.session.pop("google_oauth_redirect_uri", None) or _google_redirect_uri(request)
    staff_login_flow = request.session.pop("google_oauth_staff", False)
    try:
        token_response = requests.post(
            "https://oauth2.googleapis.com/token",
            data={
                "code": request.GET["code"],
                "client_id": settings.GOOGLE_OAUTH_CLIENT_ID,
                "client_secret": settings.GOOGLE_OAUTH_CLIENT_SECRET,
                "redirect_uri": redirect_uri,
                "grant_type": "authorization_code",
            },
            timeout=10,
        )
        token_response.raise_for_status()
        token_data = token_response.json()
        claims = jwt.decode(token_data["id_token"], options={"verify_signature": False})
        if claims.get("aud") != settings.GOOGLE_OAUTH_CLIENT_ID or claims.get("iss") not in {"accounts.google.com", "https://accounts.google.com"} or not claims.get("email_verified"):
            raise ValueError("Invalid Google identity token")
        email = claims["email"].lower()
        full_name = claims.get("name") or email.split("@", 1)[0]
        if staff_login_flow:
            user = Staff.objects.filter(email__iexact=email).exclude(role__iexact="guest").first()
            if user is None:
                return redirect("staff_login")
        else:
            user, created = Staff.objects.get_or_create(email=email, defaults={
                "username": email, "staff_name": full_name, "role": "guest",
                "first_name": claims.get("given_name", ""), "last_name": claims.get("family_name", ""),
            })
            if created:
                user.set_unusable_password()
                user.save(update_fields=["password"])
    except Exception:
        return redirect("staff_login" if staff_login_flow else "signin")
    login(request, user)
    return redirect(_redirect_for_role(user.role))


@require_http_methods(["POST"])
def api_register(request):
    """Create a guest account from the public registration form."""
    try:
        payload = json.loads(request.body.decode("utf-8")) if request.body else {}
    except json.JSONDecodeError:
        return JsonResponse({"detail": "Invalid JSON payload."}, status=400)

    full_name = (payload.get("full_name") or payload.get("name") or "").strip()
    email = (payload.get("email") or "").strip().lower()
    staff_phone = _phone_value(payload.get("country_code"), payload.get("staff_phone") or payload.get("phone"))
    password = (payload.get("password") or "").strip()

    if not full_name or not email or not password or not staff_phone:
        return JsonResponse({"detail": "full_name, email, phone, and password are required."}, status=400)

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
    """Main customer home/explore page after login. Redirect staff to their dashboards."""
    if request.user.is_authenticated:
        role = (request.user.role or "").lower()
        if role == "admin":
            return redirect("manager_dashboard")
        elif role == "manager":
            return redirect("manager_dashboard")
        elif role == "receptionist":
            return redirect("receptionist_dashboard")
        elif role == "accountant":
            return redirect("accountant_dashboard")
        elif role == "housekeeping":
            return redirect("housekeeping_dashboard")
    name = request.user.get_full_name().strip() if request.user.is_authenticated else "Guest"
    name = name or (request.user.staff_name if request.user.is_authenticated else "Guest")
    return render(request, "frontend/guest_home.html", {"display_name": name})


def explore_stays(request):
    """Room booking / explore stays page."""
    name = request.user.get_full_name().strip() if request.user.is_authenticated else "Guest"
    name = name or (request.user.staff_name if request.user.is_authenticated else "Guest")
    category = request.GET.get("category", "")
    search_query = request.GET.get("q", "")
    return render(request, "frontend/explore_stays.html", {
        "display_name": name,
        "category": category,
        "search_query": search_query,
    })


def hotel_details(request):
    """Detailed view of a single hotel."""
    name = request.user.get_full_name().strip() if request.user.is_authenticated else "Guest"
    name = name or (request.user.staff_name if request.user.is_authenticated else "Guest")
    hotel_id = request.GET.get("hotel", "1")
    # Map hotel IDs to names
    hotels = {
        "1": {"name": "La Palm Royal Beach Hotel", "location": "Liberation Road, Accra", "rating": "5.0", "price": "GH₵250"},
        "2": {"name": "Kempinski Hotel Gold Coast City", "location": "Gamel Abdul Nasser Avenue, Accra", "rating": "4.9", "price": "GH₵400"},
        "3": {"name": "Royal Senchi Resort", "location": "Senchi, Eastern Region", "rating": "4.8", "price": "GH₵350"},
    }
    hotel_info = hotels.get(hotel_id, hotels["1"])
    return render(request, "frontend/hotel_details.html", {
        "display_name": name,
        "hotel_id": hotel_id,
        "hotel_name": hotel_info["name"],
        "hotel_location": hotel_info["location"],
        "hotel_rating": hotel_info["rating"],
        "hotel_price": hotel_info["price"],
    })


def booking(request):
    """Booking configuration / reservation page."""
    name = request.user.get_full_name().strip() if request.user.is_authenticated else "Guest"
    name = name or (request.user.staff_name if request.user.is_authenticated else "Guest")
    user_email = request.user.email if request.user.is_authenticated else ""
    user_phone = request.user.staff_phone if request.user.is_authenticated and hasattr(request.user, 'staff_phone') else ""
    user_name = request.user.staff_name if request.user.is_authenticated and hasattr(request.user, 'staff_name') else name
    return render(request, "frontend/booking.html", {
        "display_name": name,
        "user_email": user_email,
        "user_phone": user_phone,
        "user_name": user_name,
    })


def reservation_confirmed(request):
    reservation_id = request.GET.get("reservation_id")
    invoice_id = request.GET.get("invoice_id")
    check_in = request.GET.get("check_in")
    check_out = request.GET.get("check_out")
    guests = request.GET.get("guests", "1")
    total = request.GET.get("total", "0")
    room_number = request.GET.get("room_number", "")
    room_type = request.GET.get("room_type", "")
    hotel_name = request.GET.get("hotel_name", "")
    guest_email = request.GET.get("guest_email", "")

    reservation = None
    invoice = None
    if reservation_id:
        try:
            reservation = Reservation.objects.select_related("hotel").get(pk=reservation_id)
            invoice = Invoice.objects.filter(reservation=reservation).first()
            if not invoice and invoice_id:
                try:
                    invoice = Invoice.objects.get(pk=invoice_id)
                except Invoice.DoesNotExist:
                    invoice = None
        except Reservation.DoesNotExist:
            reservation = None
            invoice = None

    user_name = ""
    user_email = ""
    if request.user.is_authenticated:
        user_name = request.user.get_full_name() or request.user.username
        user_email = getattr(request.user, "email", "") or ""

    context = {
        "reservation": reservation,
        "invoice": invoice,
        "check_in": check_in,
        "check_out": check_out,
        "guests": guests,
        "total": total,
        "room_number": room_number,
        "room_type": room_type,
        "hotel_name": hotel_name,
        "user_name": user_name,
        "user_email": user_email,
        "guest_email": guest_email,
    }
    return render(request, "frontend/reservation_confirmed.html", context)


@require_http_methods(["GET"])
def reservation_status(request, reservation_id):
    """Return live status for a reservation owned by the current guest/staff user."""
    reservation = Reservation.objects.select_related("guest").filter(pk=reservation_id).first()
    if not reservation:
        return JsonResponse({"detail": "Reservation not found."}, status=404)
    if not request.user.is_authenticated and request.GET.get("email", "").lower() != reservation.guest.guest_email.lower():
        return JsonResponse({"detail": "Authentication required."}, status=403)
    if request.user.is_authenticated and request.user.email.lower() != reservation.guest.guest_email.lower() and not request.user.is_staff:
        return JsonResponse({"detail": "Not allowed."}, status=403)
    return JsonResponse({"id": reservation.pk, "status": reservation.status})


def team(request):
    """Team / About page showing the StayHub team."""
    return render(request, "frontend/team.html")


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

    if not all([guest_name, guest_email, guest_phone, id_number, nationality, check_in_raw, check_out_raw, room_id]):
        return JsonResponse(
            {"detail": "guest_name, guest_email, phone, nationality, ID number, room_id, check_in, and check_out are required."},
            status=400,
        )

    try:
        check_in = datetime.fromisoformat(check_in_raw)
        check_out = datetime.fromisoformat(check_out_raw)
    except ValueError:
        return JsonResponse({"detail": "check_in and check_out must be ISO 8601 datetimes."}, status=400)

    if check_out <= check_in:
        return JsonResponse({"detail": "check_out must be after check_in."}, status=400)
    if nationality.lower() == "ghana" and not _ghana_card_valid(id_number):
        return JsonResponse({"detail": "Ghana Card PIN must use the format GHA-123456789-0."}, status=400)

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
            status=Reservation.ReservationStatus.PENDING,
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

def _role_required(*allowed_roles):
    """Decorator to restrict access based on user role."""
    def decorator(view_func):
        @login_required(login_url="staff_login")
        def _wrapped_view(request, *args, **kwargs):
            if request.user.role and request.user.role.lower() not in [r.lower() for r in allowed_roles]:
                return render(request, "frontend/access_denied.html", {
                    "required_role": allowed_roles[0].title() if len(allowed_roles) == 1 else "Admin/Manager",
                })
            return view_func(request, *args, **kwargs)
        return _wrapped_view
    return decorator


@_role_required("admin", "manager")
def manager_dashboard(request):
    """Manager/Admin dashboard view."""
    from apps.rooms.models import Room, Maintenance
    from apps.reservations.models import Reservation
    from apps.accounts.models import Staff
    from apps.common.mixins import MANAGER_ROLES
    
    user = request.user
    role = (user.role or "").lower()
    is_manager_admin = role in MANAGER_ROLES
    
    # Branch scoping for dashboard counts
    staff_qs = Staff.objects.all()
    room_qs = Room.objects.all()
    reservation_qs = Reservation.objects.all()
    maintenance_qs = Maintenance.objects.select_related("room", "room__hotel")
    
    if not is_manager_admin and user.hotel_id:
        staff_qs = staff_qs.filter(hotel_id=user.hotel_id)
        room_qs = room_qs.filter(hotel_id=user.hotel_id)
        reservation_qs = reservation_qs.filter(hotel_id=user.hotel_id)
        maintenance_qs = maintenance_qs.filter(room__hotel_id=user.hotel_id)
    
    # For managers/admins, optionally scope to a specific branch if they have one
    if is_manager_admin and user.hotel_id:
        # Even managers might be assigned to a specific branch; show them
        # their branch data, plus an option to see all via a query param
        if request.GET.get("scope") != "all":
            staff_qs = staff_qs.filter(hotel_id=user.hotel_id)
            room_qs = room_qs.filter(hotel_id=user.hotel_id)
            reservation_qs = reservation_qs.filter(hotel_id=user.hotel_id)
            maintenance_qs = maintenance_qs.filter(room__hotel_id=user.hotel_id)
    
    today = timezone.localdate()
    context = {
        "total_staff": staff_qs.count(),
        "total_rooms": room_qs.count(),
        "available_rooms": room_qs.filter(status=Room.RoomStatus.AVAILABLE).count(),
        "occupied_rooms": room_qs.filter(status=Room.RoomStatus.OCCUPIED).count(),
        "maintenance_rooms": room_qs.filter(status=Room.RoomStatus.MAINTENANCE).count(),
        "total_reservations": reservation_qs.count(),
        "recent_maintenance": maintenance_qs.order_by("-report_date")[:5],
        "today_checkins": reservation_qs.filter(check_in__date=today).select_related("guest", "hotel").order_by("check_in")[:10],
        "today_checkouts": reservation_qs.filter(check_out__date=today).select_related("guest", "hotel").order_by("check_out")[:10],
        "live_rooms": room_qs.select_related("room_type").order_by("room_number")[:24],
    }
    return render(request, "frontend/manager_dashboard.html", context)


@_role_required("receptionist")
def receptionist_dashboard(request):
    """Receptionist operations dashboard."""
    from apps.rooms.models import Room
    today = timezone.localdate()
    reservations = Reservation.objects.select_related("guest", "hotel").order_by("check_in")
    rooms = Room.objects.all()
    if request.user.hotel_id:
        reservations = reservations.filter(hotel_id=request.user.hotel_id)
        rooms = rooms.filter(hotel_id=request.user.hotel_id)
    return render(request, "frontend/receptionist_dashboard.html", {
        "available_rooms_count": rooms.filter(status=Room.RoomStatus.AVAILABLE).count(),
        "ready_rooms_count": rooms.filter(status=Room.RoomStatus.AVAILABLE, housekeeping_status=Room.HousekeepingStatus.CLEAN).count(),
        "today_checkins": reservations.filter(check_in__date=today).select_related("guest")[:20],
        "today_checkouts": reservations.filter(check_out__date=today).select_related("guest")[:20],
        "upcoming_reservations": reservations.filter(check_in__date__gte=today).order_by("check_in")[:20],
    })


@_role_required("accountant")
def accountant_dashboard(request):
    """Accountant/financial dashboard."""
    from apps.billing.models import Payment
    invoices = Invoice.objects.select_related("reservation", "reservation__guest").order_by("-issue_date")
    payments = Payment.objects.select_related("invoice", "invoice__reservation__guest").order_by("-payment_date")
    if request.user.hotel_id:
        invoices = invoices.filter(hotel_id=request.user.hotel_id)
        payments = payments.filter(hotel_id=request.user.hotel_id)
    return render(request, "frontend/accountant_dashboard.html", {
        "invoice_count": invoices.count(),
        "unpaid_invoice_count": invoices.filter(status=Invoice.InvoiceStatus.UNPAID).count(),
        "paid_invoice_count": invoices.filter(status=Invoice.InvoiceStatus.PAID).count(),
        "recent_invoices": invoices[:10],
        "recent_payments": payments[:10],
    })


@_role_required("housekeeping")
def housekeeping_dashboard(request):
    """Housekeeping operations dashboard."""
    from apps.rooms.models import Maintenance
    from apps.common.mixins import MANAGER_ROLES
    rooms = Room.objects.select_related("room_type", "hotel")
    maintenance = Maintenance.objects.select_related("room", "room__room_type", "staff").exclude(status=Maintenance.MaintenanceStatus.RESOLVED).exclude(status=Maintenance.MaintenanceStatus.CLOSED)
    if request.user.hotel_id:
        rooms = rooms.filter(hotel_id=request.user.hotel_id)
        maintenance = maintenance.filter(room__hotel_id=request.user.hotel_id)
    return render(request, "frontend/housekeeping_dashboard.html", {
        "dirty_rooms": rooms.filter(housekeeping_status=Room.HousekeepingStatus.DIRTY).order_by("room_number"),
        "clean_rooms": rooms.filter(housekeeping_status=Room.HousekeepingStatus.CLEAN).order_by("room_number"),
        "maintenance_tasks": maintenance.order_by("-report_date")[:20],
        "room_inventory": rooms.order_by("room_number")[:40],
    })


def design_system(request):
    """Design system / hero welcome page."""
    return render(request, "frontend/design_system.html")
