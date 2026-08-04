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
from django.views.decorators.csrf import ensure_csrf_cookie
from django.views.decorators.http import require_http_methods

from apps.guests.models import Guest
from apps.billing.models import Invoice
from apps.reservations.models import Reservation, RoomReservation
from apps.rooms.models import Room, RoomType
from apps.hotels.models import Hotel


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
    """Log the user in, or start 2FA when they enabled it in profile settings."""
    if getattr(user, "two_factor_enabled", False):
        request.session["pending_login_user_id"] = user.id
        request.session["pending_login_channel"] = "email"
        return JsonResponse({
            "detail": "Two-factor verification required.",
            "verification_method_required": True,
            "redirect_url": "/verification-method/",
        }, status=202)
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


@require_http_methods(["GET", "POST"])
def password_reset(request):
    """Step 1: ask for email, send a 6-digit verification code."""
    if request.method == "POST":
        email = (request.POST.get("email") or "").strip().lower()
        if not email:
            return render(request, "frontend/password_reset.html", {"error": "Enter your email address.", "email": email})

        user = None
        if "@" in email:
            user = Staff.objects.filter(email__iexact=email).first()
            if user is None:
                user = Guest.objects.filter(guest_email__iexact=email).first()
        if user is None:
            return render(request, "frontend/password_reset.html", {"error": "No account found with that email.", "email": email})

        code = f"{secrets.randbelow(1_000_000):06d}"
        request.session["reset_email"] = email
        request.session["reset_code"] = make_password(code)
        request.session["reset_expires_at"] = time.time() + 600
        request.session["reset_user_type"] = "staff" if isinstance(user, Staff) else "guest"
        try:
            send_mail(
                "Your StayHub password reset code",
                f"Your verification code is {code}. It expires in 10 minutes.",
                settings.DEFAULT_FROM_EMAIL,
                [email],
                fail_silently=False,
            )
            return render(request, "frontend/password_reset.html", {"sent": True, "email": email})
        except Exception:
            logger.exception("Failed to send password reset code to %s", email)
            return render(request, "frontend/password_reset.html", {"error": "We could not send the email. Try again later.", "email": email})

    return render(request, "frontend/password_reset.html")


@require_http_methods(["POST"])
def password_reset_verify(request):
    """Step 2: verify code and set a new password."""
    email = (request.POST.get("email") or "").strip().lower()
    code = (request.POST.get("code") or "").strip()
    new_password1 = (request.POST.get("new_password1") or "").strip()
    new_password2 = (request.POST.get("new_password2") or "").strip()

    if not email or not code or not new_password1 or not new_password2:
        return render(request, "frontend/password_reset.html", {
            "error": "All fields are required.", "sent": True, "email": email, "code": code,
        })
    if new_password1 != new_password2:
        return render(request, "frontend/password_reset.html", {
            "error": "Passwords do not match.", "sent": True, "email": email, "code": code,
        })
    if len(new_password1) < 8:
        return render(request, "frontend/password_reset.html", {
            "error": "Password must be at least 8 characters.", "sent": True, "email": email, "code": code,
        })

    expected_code = request.session.get("reset_code", "")
    expires_at = request.session.get("reset_expires_at", 0)
    session_email = request.session.get("reset_email", "")
    if not expected_code or time.time() > expires_at or session_email != email:
        return render(request, "frontend/password_reset.html", {
            "error": "This code has expired. Please request a new one.", "email": email,
        })
    if not check_password(code, expected_code):
        return render(request, "frontend/password_reset.html", {
            "error": "Invalid verification code.", "sent": True, "email": email, "code": code,
        })

    user_type = request.session.get("reset_user_type", "guest")
    user = None
    if user_type == "staff":
        user = Staff.objects.filter(email__iexact=email).first()
    else:
        user = Guest.objects.filter(guest_email__iexact=email).first()

    if user is None:
        return render(request, "frontend/password_reset.html", {
            "error": "Account not found.", "email": email,
        })

    if user_type == "staff":
        user.set_password(new_password1)
        user.save(update_fields=["password"])
    else:
        if isinstance(user, Guest):
            user.set_password(new_password1)
            user.save(update_fields=["password"])

    for key in ("reset_email", "reset_code", "reset_expires_at", "reset_user_type"):
        request.session.pop(key, None)

    return redirect("signin")


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
    """Show and update the signed-in user's profile (staff or guest)."""
    user = request.user
    # Detect whether the signed-in user is a guest (GuestUser adapter) or staff.
    is_staff = (getattr(user, "role", "") or "").lower() in ("admin", "manager", "receptionist", "accountant", "housekeeping")
    guest = None
    if not is_staff:
        # The session user is a GuestUser adapter pointing to a Guest row.
        from apps.guests.auth import GuestUser
        if isinstance(user, GuestUser):
            guest = user._guest
        else:
            # Fallback: look up the guest by email (for safety).
            guest = Guest.objects.filter(guest_email__iexact=user.email).first()

    phone = getattr(user, "staff_phone", "") or (guest.guest_phone if guest else "")
    phone_country_code = "+233"
    phone_number = phone
    for code in ("+233", "+234", "+254", "+27", "+44", "+1"):
        if phone.startswith(code):
            phone_country_code, phone_number = code, phone[len(code):]
            break

    template = "frontend/staff_profile.html" if is_staff else "frontend/profile.html"

    def render_profile(**extra):
        context = {
            "phone_country_code": phone_country_code,
            "phone_number": phone_number,
            "two_factor_enabled": getattr(user, "two_factor_enabled", False),
        }
        context.update(extra)
        return render(request, template, context)

    if request.method == "POST":
        full_name = (request.POST.get("full_name") or "").strip()
        email = (request.POST.get("email") or "").strip().lower()
        staff_phone = _phone_value(request.POST.get("country_code"), request.POST.get("staff_phone"))
        upload = request.FILES.get("profile_picture")
        if not full_name or not email or not staff_phone:
            return render_profile(profile_error="Name, email, and a valid phone number are required.")
        # Prevent email collisions across the two entity kinds.
        if Staff.objects.filter(email__iexact=email).exists() and is_staff:
            if Staff.objects.filter(email__iexact=email).exclude(pk=user.pk).exists():
                return render_profile(profile_error="That email is already in use.")
        if guest is not None and Guest.objects.filter(guest_email__iexact=email).exclude(pk=guest.pk).exists():
            return render_profile(profile_error="That email is already in use.")

        if guest is not None:
            # Guest profile: persist changes to the guest table.
            guest.guest_name = full_name
            guest.guest_email = email
            guest.guest_phone = staff_phone
            guest.save(update_fields=["guest_name", "guest_email", "guest_phone"])
            return redirect("profile")

        parts = full_name.split(maxsplit=1)
        user.staff_name = full_name
        user.first_name = parts[0]
        user.last_name = parts[1] if len(parts) > 1 else ""
        user.email = email
        user.username = email
        user.staff_phone = staff_phone
        user.two_factor_enabled = request.POST.get("two_factor_enabled") == "1"
        if request.POST.get("clear_picture") == "1" and user.profile_picture:
            user.profile_picture.delete(save=False)
            user.profile_picture = None
        if upload:
            if upload.size > 5 * 1024 * 1024 or not (upload.content_type or "").startswith("image/"):
                return render_profile(profile_error="Use an image file smaller than 5 MB.")
            user.profile_picture = upload
        user.save()
        return redirect("staff_profile" if is_staff else "profile")
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

    # If no staff account exists, try to authenticate a registered guest.
    if user is None:
        guest = Guest.objects.filter(guest_email__iexact=identifier).first()
        if guest is not None:
            if staff_only:
                return JsonResponse({"detail": "This account is not a staff account."}, status=403)
            if not guest.password:
                return JsonResponse({"detail": "This guest has no password set (they may have booked as a walk-in). Please create an account first."}, status=400)
            if not guest.check_password(password):
                return JsonResponse({"detail": "Invalid credentials."}, status=400)
            # Build a GuestUser adapter and log in via Django's session auth.
            from apps.guests.auth import GuestUser
            authenticated_guest = GuestUser(guest)
            login(request, authenticated_guest)
            return JsonResponse({
                "detail": "Signed in successfully.",
                "redirect_url": "/home/",
            })
        return JsonResponse({"detail": "Invalid credentials."}, status=400)

    if staff_only and (user.role or "").lower() == "guest":
        return JsonResponse({"detail": "This account is not a staff account."}, status=403)

    authenticated_user = authenticate(request, username=user.username, password=password)
    if authenticated_user is None:
        # If authentication failed, provide clearer reasons when possible.
        if not user.is_active:
            return JsonResponse({"detail": "This account has been disabled. Contact support or an administrator."}, status=403)
        if not user.has_usable_password():
            return JsonResponse({"detail": "This account does not have a usable password (created via social login). Use the social sign-in method or reset your password."}, status=400)
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
    """Log out and redirect staff to staff_login, guests to signin."""
    if not request.user.is_authenticated:
        return redirect("signin")
    # Capture role BEFORE logout clears the session
    role = (request.user.role or "").lower()
    user_id = request.user.pk
    logout(request)
    # Verify the user was a staff member
    if role in ("admin", "manager", "receptionist", "accountant", "housekeeping"):
        return redirect("staff_login")
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
    if getattr(user, "two_factor_enabled", False):
        request.session["pending_login_user_id"] = user.id
        request.session["pending_login_channel"] = "email"
        return redirect("verification_method")
    login(request, user)
    return redirect(_redirect_for_role(user.role))


@require_http_methods(["POST"])
def api_register(request):
    """Create a public guest account from the registration form.

    Guests are stored in the ``guest`` table (not ``staff``) so the staff
    roster stays clean and admins never confuse guests with employees.
    """
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

    # Guests live in the guest table, staff in the staff table.
    if Guest.objects.filter(guest_email__iexact=email).exists() or Staff.objects.filter(email__iexact=email).exists():
        return JsonResponse({"detail": "An account with that email already exists."}, status=409)

    guest = Guest.objects.create(
        guest_name=full_name,
        guest_phone=staff_phone,
        guest_email=email,
    )
    guest.set_password(password)
    guest.save(update_fields=["password"])

    # If a walk-in guest already exists for this email (from a booking),
    # link them by setting the password rather than duplicating.
    # (We check uniqueness first above, so this is the fresh-registration path.)

    return JsonResponse(
        {
            "detail": "Account created successfully.",
            "user": {
                "id": guest.id,
                "email": guest.guest_email,
                "role": "guest",
            },
        },
        status=201,
    )


def guest_home(request):
    """Main customer home/explore page after login. Redirect staff to their dashboards."""
    if request.user.is_authenticated:
        role = (request.user.role or "").lower()
        if role in ("admin", "manager", "receptionist", "accountant", "housekeeping"):
            return redirect("manager_dashboard" if role in ("admin", "manager") else f"{role}_dashboard")
    name = request.user.get_full_name().strip() if request.user.is_authenticated else "Guest"
    name = name or (request.user.staff_name if request.user.is_authenticated else "Guest")
    return render(request, "frontend/guest_home.html", {"display_name": name})


def explore_stays(request):
    """Room booking / explore stays page."""
    if request.user.is_authenticated and (request.user.role or "").lower() in ("admin", "manager", "receptionist", "accountant", "housekeeping"):
        return redirect("manager_dashboard" if (request.user.role or "").lower() in ("admin", "manager") else f"{(request.user.role or '').lower()}_dashboard")
    name = request.user.get_full_name().strip() if request.user.is_authenticated else "Guest"
    name = name or (request.user.staff_name if request.user.is_authenticated else "Guest")
    category = request.GET.get("category", "")
    search_query = request.GET.get("q", "")
    hotel_categories = Hotel.Category.choices
    return render(request, "frontend/explore_stays.html", {
        "display_name": name,
        "category": category,
        "search_query": search_query,
        "hotel_categories": hotel_categories,
    })


def hotel_details(request):
    """Detailed view of a single hotel."""
    if request.user.is_authenticated and (request.user.role or "").lower() in ("admin", "manager", "receptionist", "accountant", "housekeeping"):
        return redirect("manager_dashboard" if (request.user.role or "").lower() in ("admin", "manager") else f"{(request.user.role or '').lower()}_dashboard")
    name = request.user.get_full_name().strip() if request.user.is_authenticated else "Guest"
    name = name or (request.user.staff_name if request.user.is_authenticated else "Guest")
    hotel_id = request.GET.get("hotel", "1")
    hotels = {
        "1": {"name": "La Palm Royal Beach Hotel", "location": "Liberation Road, Accra", "rating": "5.0", "price": "GH₵250", "image": "frontend/img/008833018260f8f9343a80c63b5be476.jpg", "category": "RESORT", "description": "Luxury beachfront resort with ocean views and premium amenities."},
        "2": {"name": "Kempinski Hotel Gold Coast City", "location": "Gamel Abdul Nasser Avenue, Accra", "rating": "4.9", "price": "GH₵400", "image": "frontend/img/d903519e676e485832027f1ced40bc7b.jpg", "category": "HOTEL", "description": "Five-star urban hotel in the heart of Accra's business district."},
        "3": {"name": "Royal Senchi Resort", "location": "Senchi, Eastern Region", "rating": "4.8", "price": "GH₵350", "image": "frontend/img/acb50fa45400182975c5ad13e56831a3.jpg", "category": "RESORT", "description": "Serene resort nestled along the Volta River with lush gardens."},
        "4": {"name": "Busua Beach Resort", "location": "Busua, Western Region", "rating": "5.0", "price": "GH₵250", "image": "frontend/img/961517923804f2e48a85a5c1ac83e837.jpg", "category": "RESORT", "description": "Beachfront resort with golden sands, surf lessons, and fresh seafood."},
    }
    hotel_info = hotels.get(hotel_id, hotels["1"])
    return render(request, "frontend/hotel_details.html", {
        "display_name": name,
        "hotel_id": hotel_id,
        "hotel_name": hotel_info["name"],
        "hotel_location": hotel_info["location"],
        "hotel_rating": hotel_info["rating"],
        "hotel_price": hotel_info["price"],
        "hotel_image": hotel_info["image"],
        "hotel_category": hotel_info.get("category", "HOTEL"),
        "hotel_description": hotel_info.get("description", ""),
    })


def booking(request):
    """Booking configuration / reservation page."""
    name = request.user.get_full_name().strip() if request.user.is_authenticated else "Guest"
    name = name or (request.user.staff_name if request.user.is_authenticated else "Guest")
    user_email = request.user.email if request.user.is_authenticated else ""
    user_phone = getattr(request.user, 'staff_phone', '') if request.user.is_authenticated else ""
    user_name = getattr(request.user, 'staff_name', name) if request.user.is_authenticated else name
    is_staff = request.user.is_authenticated and (request.user.role or "").lower() in ("admin", "manager", "receptionist", "accountant", "housekeeping")
    hotel_id = request.GET.get("hotel", "")
    return render(request, "frontend/booking.html", {
        "display_name": name,
        "user_email": user_email,
        "user_phone": user_phone,
        "user_name": user_name,
        "is_staff": is_staff,
        "hotel_id": hotel_id,
    })


def reservation_confirmed(request):
    """Booking confirmation screen.

    After a successful Paystack payment the user is redirected here with
    ``reservation_id`` and ``invoice_id`` query params. When the reservation
    exists in the database we render its REAL data (real reservation ID, dates,
    room, totals) instead of relying on the query string.
    """
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
            reservation = (
                Reservation.objects.select_related("hotel", "guest")
                .prefetch_related("room_reservations__room__room_type")
                .get(pk=reservation_id)
            )
            invoice = Invoice.objects.filter(reservation=reservation).first()
            if not invoice and invoice_id:
                try:
                    invoice = Invoice.objects.get(pk=invoice_id)
                except Invoice.DoesNotExist:
                    invoice = None
        except Reservation.DoesNotExist:
            reservation = None
            invoice = None

    # Prefer the real database record so the screen always shows genuine data.
    nights = None
    first_room = None
    check_in_display = None
    check_out_display = None
    if reservation:
        reservation_id = str(reservation.pk)
        room_links = list(reservation.room_reservations.select_related("room", "room__room_type").all())
        first_room = room_links[0].room if room_links else None
        if first_room:
            room_number = first_room.room_number
            room_type = first_room.room_type.type_name if first_room.room_type else room_type
        if reservation.hotel:
            hotel_name = reservation.hotel.hotel_name
        check_in = reservation.check_in.strftime("%Y-%m-%d")
        check_out = reservation.check_out.strftime("%Y-%m-%d")
        check_in_display = reservation.check_in.strftime("%b %d, %Y")
        check_out_display = reservation.check_out.strftime("%b %d, %Y")
        nights = max(1, (reservation.check_out.date() - reservation.check_in.date()).days)
        if invoice and invoice.total_amount is not None:
            total = f"{invoice.total_amount:,.2f}"
        if reservation.guest and reservation.guest.guest_email:
            guest_email = reservation.guest.guest_email

    display_name = "Guest"
    if request.user.is_authenticated:
        display_name = (
            request.user.get_full_name().strip()
            or request.user.staff_name
            or request.user.username
        )
    guest_name = reservation.guest.guest_name if reservation else (
        guest_email.split("@")[0].title() if guest_email else display_name
    )

    context = {
        "reservation": reservation,
        "invoice": invoice,
        "status_display": (reservation.status or "Confirmed").replace("_", " ") if reservation else "Confirmed",
        "reservation_id": reservation_id or "",
        "invoice_id": invoice_id or (str(invoice.pk) if invoice else ""),
        "check_in": check_in,
        "check_out": check_out,
        "check_in_display": check_in_display,
        "check_out_display": check_out_display,
        "guests": guests,
        "total": total,
        "room_number": room_number,
        "room_type": room_type,
        "hotel_name": hotel_name,
        "first_room": first_room,
        "nights": nights,
        "guest_name": guest_name,
        "guest_email": guest_email,
        "user_name": display_name,
        "user_email": getattr(request.user, "email", "") or "",
    }
    return render(request, "frontend/reservation_confirmed.html", context)


@require_http_methods(["GET"])
def reservation_status(request, reservation_id):
    """Return live status for a reservation owned by the current guest/staff user."""
    reservation = Reservation.objects.select_related("guest").filter(pk=reservation_id).first()
    if not reservation:
        return JsonResponse({"detail": "Reservation not found."}, status=404)

    guest_email = (reservation.guest.guest_email or "") if reservation.guest else ""
    if not request.user.is_authenticated:
        if not guest_email or request.GET.get("email", "").lower() != guest_email.lower():
            return JsonResponse({"detail": "Authentication required."}, status=403)
    else:
        role = (request.user.role or "").lower()
        is_staff = role in ("admin", "manager", "receptionist", "accountant", "housekeeping")
        if not is_staff and (request.user.email or "").lower() != guest_email.lower():
            return JsonResponse({"detail": "Not allowed."}, status=403)
        # Non-admin staff can only poll reservations at their own hotel,
        # mirroring the access control on reservation_detail.
        if is_staff and role not in ("admin",) and request.user.hotel_id and reservation.hotel_id != request.user.hotel_id:
            return JsonResponse({"detail": "Not allowed."}, status=403)
    return JsonResponse({"id": reservation.pk, "status": reservation.status})


@login_required(login_url="signin")
def my_bookings(request):
    """The signed-in guest's list of reservations (their "Bookings" tab).

    Reservations are matched to the account through the guest email used at
    booking time. Staff users are sent to their own dashboard instead.
    """
    role = (request.user.role or "").lower()
    if role in ("admin", "manager", "receptionist", "accountant", "housekeeping"):
        return redirect("manager_dashboard" if role in ("admin", "manager") else f"{role}_dashboard")

    guest = Guest.objects.filter(guest_email__iexact=request.user.email).first()
    reservations = Reservation.objects.none()
    if guest is not None:
        reservations = (
            Reservation.objects.filter(guest=guest)
            .select_related("hotel", "guest")
            .prefetch_related("room_reservations__room__room_type")
            .order_by("-booking_date")
        )

    display_name = (
        request.user.get_full_name().strip()
        or request.user.staff_name
        or request.user.username
    )
    return render(request, "frontend/my_bookings.html", {
        "guest": guest,
        "reservations": reservations,
        "display_name": display_name,
    })


def reservation_detail(request, reservation_id):
    """Full details for a single reservation.

    Accessible by the guest who owns the reservation (matched by email) and by
    staff. Non-admin staff are scoped to reservations at their own hotel.
    """
    reservation = (
        Reservation.objects.select_related("hotel", "guest")
        .prefetch_related("room_reservations__room__room_type")
        .filter(pk=reservation_id)
        .first()
    )
    if reservation is None:
        return render(request, "frontend/access_denied.html", {
            "required_role": "Guest or Staff",
        }, status=404)

    role = (request.user.role or "").lower() if request.user.is_authenticated else ""
    is_staff = role in ("admin", "manager", "receptionist", "accountant", "housekeeping")
    is_owner = (
        request.user.is_authenticated
        and request.user.email
        and reservation.guest
        and request.user.email.lower() == (reservation.guest.guest_email or "").lower()
    )

    if not (is_owner or (is_staff and request.user.is_authenticated)):
        return render(request, "frontend/access_denied.html", {
            "required_role": "Guest or Staff",
        })
    # Non-admin staff can only inspect reservations at their own hotel.
    if is_staff and role not in ("admin",) and request.user.hotel_id and reservation.hotel_id != request.user.hotel_id:
        return render(request, "frontend/access_denied.html", {
            "required_role": "Manager",
        })

    invoice = Invoice.objects.filter(reservation=reservation).first()
    payments = invoice.payments.order_by("-payment_date") if invoice else []
    rooms = [rr.room for rr in reservation.room_reservations.select_related("room", "room__room_type").all()]
    nights = max(1, (reservation.check_out.date() - reservation.check_in.date()).days)

    can_manage_operations = (
        is_staff
        and request.user.is_authenticated
        and role in ("admin", "manager", "receptionist")
    )
    available_assignable_rooms = []
    if can_manage_operations and request.user.hotel_id:
        assigned_room_ids = list(Room.objects.filter(room_reservations__resv=reservation).values_list("pk", flat=True))
        available_assignable_rooms = (
            Room.objects.select_related("room_type")
            .filter(hotel_id=request.user.hotel_id, status=Room.RoomStatus.AVAILABLE)
            .exclude(pk__in=assigned_room_ids)
            .order_by("room_number")[:50]
        )
    return render(request, "frontend/reservation_detail.html", {
        "reservation": reservation,
        "invoice": invoice,
        "payments": payments,
        "rooms": rooms,
        "nights": nights,
        "is_staff": is_staff and request.user.is_authenticated,
        "can_manage_operations": can_manage_operations,
        "available_assignable_rooms": available_assignable_rooms,
    })


def team(request):
    """Team / About page showing the StayHub team."""
    return render(request, "frontend/team.html")


@require_http_methods(["GET"])
def booking_options(request):
    """Return rooms that can be shown on the booking page.

    Supports an optional ``hotel`` query param so staff walk-in bookings can
    be scoped to the staff member's own hotel.
    """
    rooms = Room.objects.select_related("hotel", "room_type").filter(status=Room.RoomStatus.AVAILABLE)
    hotel_id = request.GET.get("hotel")
    if hotel_id:
        rooms = rooms.filter(hotel_id=hotel_id)
    rooms = rooms.order_by("hotel__hotel_name", "price_per_night", "room_number")

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
            # Allow Django superusers to bypass role checks
            if getattr(request.user, "is_superuser", False):
                return view_func(request, *args, **kwargs)
            if not getattr(request.user, "role", None) or request.user.role.lower() not in [r.lower() for r in allowed_roles]:
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
    is_superuser = getattr(user, "is_superuser", False)
    
    # All staff are scoped to their assigned hotel, including managers.
    # Superusers bypass the hotel filter.
    staff_qs = Staff.objects.all()
    room_qs = Room.objects.all()
    reservation_qs = Reservation.objects.all()
    maintenance_qs = Maintenance.objects.select_related("room", "room__hotel")
    
    if not is_superuser and user.hotel_id:
        staff_qs = staff_qs.filter(hotel_id=user.hotel_id)
        room_qs = room_qs.filter(hotel_id=user.hotel_id)
        reservation_qs = reservation_qs.filter(hotel_id=user.hotel_id)
        maintenance_qs = maintenance_qs.filter(room__hotel_id=user.hotel_id)
    
    today = timezone.localdate()
    context = {
        "active": "dashboard",
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
        "recent_reservations": reservation_qs.select_related("guest", "hotel").order_by("-booking_date")[:10],
        "user_hotel_id": user.hotel_id,
        "is_superuser": is_superuser,
    }
    return render(request, "frontend/manager_dashboard.html", context)


@ensure_csrf_cookie
@_role_required("receptionist", "manager", "admin")
def walkin_booking(request):
    """Dedicated staff walk-in booking page.

    Uses a different structure than the public booking page: the staff member
    captures the client's details (name, phone, national ID, nationality) and
    books a room at their own hotel. Payment is mobile-money only via Paystack.
    """
    hotel_id = request.user.hotel_id or ""
    hotel_name = ""
    if request.user.hotel_id:
        hotel = Hotel.objects.filter(pk=request.user.hotel_id).first()
        hotel_name = hotel.hotel_name if hotel else ""
    return render(request, "frontend/walkin_booking.html", {
        "active": "walkin",
        "hotel_id": hotel_id,
        "hotel_name": hotel_name,
    })


@_role_required("admin", "manager", "receptionist", "accountant")
def staff_reservations(request):
    """Full reservations list for staff, with a status filter."""
    from apps.reservations.models import Reservation

    role = (request.user.role or "").lower()
    status_filter = (request.GET.get("status") or "").strip()
    reservation_qs = Reservation.objects.select_related("guest", "hotel").prefetch_related("room_reservations__room__room_type")
    if role not in ("admin",) and request.user.hotel_id:
        reservation_qs = reservation_qs.filter(hotel_id=request.user.hotel_id)
    if status_filter:
        reservation_qs = reservation_qs.filter(status__iexact=status_filter)
    reservations = reservation_qs.order_by("-booking_date")[:100]

    return render(request, "frontend/staff_reservations.html", {
        "active": "bookings",
        "reservations": reservations,
        "status_filter": status_filter,
        "status_choices": Reservation.ReservationStatus.choices,
    })


@ensure_csrf_cookie
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
        "active": "dashboard",
        "available_rooms_count": rooms.filter(status=Room.RoomStatus.AVAILABLE).count(),
        "ready_rooms_count": rooms.filter(status=Room.RoomStatus.AVAILABLE, housekeeping_status=Room.HousekeepingStatus.CLEAN).count(),
        "today_checkins": reservations.filter(check_in__date=today).select_related("guest")[:20],
        "today_checkouts": reservations.filter(check_out__date=today).select_related("guest")[:20],
        "upcoming_reservations": reservations.filter(check_in__date__gte=today).order_by("check_in")[:20],
        "all_rooms": rooms.select_related("room_type").order_by("room_number")[:30],
        "available_rooms": rooms.filter(status=Room.RoomStatus.AVAILABLE).select_related("room_type").order_by("room_number")[:30],
        "reservations_json": json.dumps([{
            "id": r.id, "guest_name": r.guest.guest_name, "status": r.status,
            "check_in": r.check_in.strftime("%b %d, %Y"), "check_out": r.check_out.strftime("%b %d, %Y"),
            "hotel_id": r.hotel_id,
        } for r in reservations.filter(check_in__date__gte=today).order_by("check_in")[:20]]),
        "rooms_json": json.dumps([{
            "id": rm.id, "room_number": rm.room_number, "status": rm.status,
            "housekeeping_status": rm.housekeeping_status, "hotel_id": rm.hotel_id,
            "room_type": rm.room_type.type_name if rm.room_type else "Standard",
        } for rm in rooms.order_by("room_number")[:30]]),
    })


@ensure_csrf_cookie
@_role_required("accountant", "manager", "admin")
def accountant_dashboard(request):
    """Accountant/financial dashboard."""
    from apps.billing.models import Payment
    invoices = Invoice.objects.select_related("reservation", "reservation__guest").order_by("-issue_date")
    payments = Payment.objects.select_related("invoice", "invoice__reservation__guest").order_by("-payment_date")
    if request.user.hotel_id:
        invoices = invoices.filter(hotel_id=request.user.hotel_id)
        payments = payments.filter(hotel_id=request.user.hotel_id)
    return render(request, "frontend/accountant_dashboard.html", {
        "active": "finance",
        "invoice_count": invoices.count(),
        "unpaid_invoice_count": invoices.filter(status=Invoice.InvoiceStatus.UNPAID).count(),
        "paid_invoice_count": invoices.filter(status=Invoice.InvoiceStatus.PAID).count(),
        "recent_invoices": invoices[:10],
        "recent_payments": payments[:10],
        "invoices_json": json.dumps([{
            "id": i.id,
            "guest_name": i.reservation.guest.guest_name if i.reservation and i.reservation.guest else "-",
            "total_amount": str(i.total_amount),
            "balance_due": str(i.balance_due),
            "status": i.status,
        } for i in invoices[:10]]),
        "payment_methods": Payment.PaymentMethod.choices,
    })


@ensure_csrf_cookie
@_role_required("housekeeping", "manager", "admin")
def housekeeping_dashboard(request):
    """Housekeeping operations dashboard."""
    from apps.rooms.models import Maintenance
    rooms = Room.objects.select_related("room_type", "hotel")
    maintenance = Maintenance.objects.select_related("room", "room__room_type", "staff").exclude(status=Maintenance.MaintenanceStatus.RESOLVED).exclude(status=Maintenance.MaintenanceStatus.CLOSED)
    if request.user.hotel_id:
        rooms = rooms.filter(hotel_id=request.user.hotel_id)
        maintenance = maintenance.filter(room__hotel_id=request.user.hotel_id)
    return render(request, "frontend/housekeeping_dashboard.html", {
        "active": "dashboard",
        "dirty_rooms": rooms.filter(housekeeping_status=Room.HousekeepingStatus.DIRTY).order_by("room_number"),
        "clean_rooms": rooms.filter(housekeeping_status=Room.HousekeepingStatus.CLEAN).order_by("room_number"),
        "inspected_rooms": rooms.filter(housekeeping_status=Room.HousekeepingStatus.INSPECTED).order_by("room_number"),
        "maintenance_tasks": maintenance.order_by("-report_date")[:20],
        "room_inventory": rooms.order_by("room_number")[:40],
        "rooms_json": json.dumps([{
            "id": rm.id, "room_number": rm.room_number, "status": rm.status,
            "housekeeping_status": rm.housekeeping_status, "hotel_id": rm.hotel_id,
        } for rm in rooms.order_by("room_number")[:40]]),
    })


@ensure_csrf_cookie
@_role_required("admin", "manager")
def admin_management(request):
    """Admin management page for rooms, images, and employees."""
    from apps.rooms.models import Room, Maintenance
    from apps.accounts.models import Staff
    
    user = request.user
    role = (user.role or "").lower()
    is_admin = role == "admin"
    
    staff_qs = Staff.objects.all()
    rooms_qs = Room.objects.select_related("room_type", "hotel").all()
    hotels_qs = Hotel.objects.all()
    maintenance_qs = Maintenance.objects.select_related("room", "staff").order_by("-report_date")[:20]
    
    if user.hotel_id and not is_admin:
        staff_qs = staff_qs.filter(hotel_id=user.hotel_id)
        rooms_qs = rooms_qs.filter(hotel_id=user.hotel_id)
        maintenance_qs = maintenance_qs.filter(room__hotel_id=user.hotel_id)
    
    context = {
        "active": "manage",
        "staff_members": staff_qs.order_by("role", "staff_name"),
        "rooms": rooms_qs.order_by("room_number"),
        "hotels": hotels_qs.order_by("category", "hotel_name"),
        "maintenance_tasks": maintenance_qs,
        "is_admin": is_admin,
        "user_hotel_id": user.hotel_id,
        "room_types": RoomType.objects.select_related("hotel").order_by("type_name"),
        "hotel_categories": Hotel.Category.choices,
        "rooms_json": json.dumps([{
            "id": r.id,
            "room_number": r.room_number,
            "floor": r.floor,
            "price_per_night": str(r.price_per_night or (r.room_type.price_per_night if r.room_type else 0)),
            "status": r.status,
            "housekeeping_status": r.housekeeping_status,
            "room_type_id": r.room_type_id,
            "hotel_id": r.hotel_id,
        } for r in rooms_qs]),
        "staff_json": json.dumps([{
            "id": s.id,
            "staff_name": s.staff_name,
            "email": s.email,
            "staff_phone": s.staff_phone,
            "role": s.role,
            "hotel_id": s.hotel_id,
        } for s in staff_qs]),
        "hotels_json": json.dumps([{
            "id": h.id,
            "hotel_name": h.hotel_name,
            "hotel_email": h.hotel_email,
            "hotel_phone": h.hotel_phone,
            "hotel_address": h.hotel_address,
            "category": h.category,
            "has_image": bool(h.hotel_image),
            "image_url": h.hotel_image.url if h.hotel_image else "",
        } for h in hotels_qs]),
    }
    return render(request, "frontend/admin_management.html", context)


# ─── Admin Management CRUD API (JSON, session-auth, CSRF-protected) ───

ROOM_STATUSES = Room.RoomStatus.choices
ROOM_HOUSEKEEPING = Room.HousekeepingStatus.choices
STAFF_ROLES = ("admin", "manager", "receptionist", "accountant", "housekeeping")


def _admin_manage_context(request):
    """Return (is_admin, hotel_id) for admin/manager API callers, else None."""
    if not request.user.is_authenticated:
        return None
    role = (request.user.role or "").lower()
    # Allow superusers to act as global admins
    if getattr(request.user, "is_superuser", False):
        return True, request.user.hotel_id
    if role not in ("admin", "manager"):
        return None
    return role == "admin", request.user.hotel_id


def _payload_json(request):
    try:
        return json.loads(request.body.decode("utf-8")) if request.body else {}
    except json.JSONDecodeError:
        return None


@require_http_methods(["POST"])
def admin_room_save(request):
    """Create or update a room. Managers are scoped to their own hotel."""
    ctx = _admin_manage_context(request)
    if ctx is None:
        return JsonResponse({"detail": "You do not have permission to manage rooms."}, status=403)
    is_admin, hotel_id = ctx
    payload = _payload_json(request)
    if payload is None:
        return JsonResponse({"detail": "Invalid JSON payload."}, status=400)

    room_id = payload.get("id")
    room = None
    if room_id:
        room = Room.objects.filter(pk=room_id).first()
        if room is None:
            return JsonResponse({"detail": "Room not found."}, status=404)
        if not is_admin and room.hotel_id != hotel_id:
            return JsonResponse({"detail": "You can only edit rooms at your hotel."}, status=403)

    target_hotel_id = payload.get("hotel_id")
    if not is_admin:
        target_hotel_id = hotel_id
    if not target_hotel_id:
        return JsonResponse({"detail": "You are not assigned to a hotel. Ask an admin to assign you first."}, status=400)
    hotel = Hotel.objects.filter(pk=target_hotel_id).first()
    if hotel is None:
        return JsonResponse({"detail": "Choose a valid hotel."}, status=400)

    room_number = (payload.get("room_number") or "").strip()
    floor_raw = payload.get("floor")
    price_raw = payload.get("price_per_night")
    status = (payload.get("status") or "").strip().upper()
    housekeeping = (payload.get("housekeeping_status") or "").strip().upper()
    room_type_id = payload.get("room_type_id")

    if not room_number:
        return JsonResponse({"detail": "Room number is required."}, status=400)
    if not all(c.isalnum() or c in "-/" for c in room_number):
        return JsonResponse({"detail": "Room number may only contain letters, numbers, dashes, and slashes."}, status=400)
    if Room.objects.filter(hotel=hotel, room_number__iexact=room_number).exclude(pk=room.pk if room else None).exists():
        return JsonResponse({"detail": f"A room numbered {room_number} already exists at {hotel.hotel_name}."}, status=409)

    floor = None
    if floor_raw not in (None, ""):
        try:
            floor = int(floor_raw)
        except (TypeError, ValueError):
            return JsonResponse({"detail": "Floor must be a whole number."}, status=400)
    try:
        price = Decimal(price_raw) if price_raw not in (None, "") else Decimal(0)
        if price < 0:
            raise ValueError
    except Exception:
        return JsonResponse({"detail": "Price must be a positive number."}, status=400)
    if status not in dict(ROOM_STATUSES):
        status = Room.RoomStatus.AVAILABLE
    if housekeeping not in dict(ROOM_HOUSEKEEPING):
        housekeeping = Room.HousekeepingStatus.DIRTY

    room_type = None
    if room_type_id:
        # Scoped to the target hotel so a manager cannot attach another hotel's type.
        room_type = RoomType.objects.filter(pk=room_type_id, hotel=hotel).first()
        if room_type is None:
            return JsonResponse({"detail": "Selected room type does not belong to this hotel."}, status=400)

    if room is None:
        room = Room(hotel=hotel)
    room.hotel = hotel
    room.room_type = room_type
    room.room_number = room_number.upper()
    room.floor = floor
    room.price_per_night = price
    room.status = status
    room.housekeeping_status = housekeeping
    room.save()
    return JsonResponse({"detail": f"Room {room.room_number} saved.", "id": room.pk})


@require_http_methods(["POST"])
def admin_room_delete(request):
    """Delete a room. Occupied/reserved rooms cannot be removed."""
    ctx = _admin_manage_context(request)
    if ctx is None:
        return JsonResponse({"detail": "You do not have permission to manage rooms."}, status=403)
    is_admin, hotel_id = ctx
    payload = _payload_json(request)
    if payload is None:
        return JsonResponse({"detail": "Invalid JSON payload."}, status=400)

    room = Room.objects.filter(pk=payload.get("id")).first()
    if room is None:
        return JsonResponse({"detail": "Room not found."}, status=404)
    from apps.rooms.models import Maintenance

    if not is_admin and room.hotel_id != hotel_id:
        return JsonResponse({"detail": "You can only delete rooms at your hotel."}, status=403)
    if room.status in (Room.RoomStatus.OCCUPIED, Room.RoomStatus.RESERVED):
        return JsonResponse({"detail": f"Room {room.room_number} has an active booking and cannot be deleted."}, status=409)
    if Maintenance.objects.filter(room=room).exclude(status__in=(Maintenance.MaintenanceStatus.RESOLVED, Maintenance.MaintenanceStatus.CLOSED)).exists():
        return JsonResponse({"detail": f"Room {room.room_number} has open maintenance tasks. Resolve them first."}, status=409)
    label = room.room_number
    room.delete()
    return JsonResponse({"detail": f"Room {label} deleted."})


@require_http_methods(["POST"])
def admin_staff_save(request):
    """Create or update an employee. Managers are scoped to their own hotel."""
    ctx = _admin_manage_context(request)
    if ctx is None:
        return JsonResponse({"detail": "You do not have permission to manage employees."}, status=403)
    is_admin, hotel_id = ctx
    payload = _payload_json(request)
    if payload is None:
        return JsonResponse({"detail": "Invalid JSON payload."}, status=400)

    from apps.accounts.models import Staff

    staff_id = payload.get("id")
    staff = None
    if staff_id:
        staff = Staff.objects.filter(pk=staff_id).first()
        if staff is None:
            return JsonResponse({"detail": "Employee not found."}, status=404)
        if not is_admin and staff.hotel_id != hotel_id:
            return JsonResponse({"detail": "You can only edit employees at your hotel."}, status=403)
        if staff.role == "admin" and not is_admin:
            return JsonResponse({"detail": "Only admins can edit admin accounts."}, status=403)

    staff_name = (payload.get("staff_name") or "").strip()
    email = (payload.get("email") or "").strip().lower()
    role = (payload.get("role") or "").strip().lower()
    password = payload.get("password") or ""
    staff_phone = _phone_value(payload.get("country_code"), payload.get("staff_phone"))

    if not staff_name or not email:
        return JsonResponse({"detail": "Name and email are required."}, status=400)
    if role not in STAFF_ROLES:
        return JsonResponse({"detail": "Choose a valid role."}, status=400)
    if role == "admin" and not is_admin:
        return JsonResponse({"detail": "Only admins can create admin accounts."}, status=403)
    if Staff.objects.filter(email__iexact=email).exclude(pk=staff.pk if staff else None).exists():
        return JsonResponse({"detail": "An account with that email already exists."}, status=409)

    target_hotel_id = payload.get("hotel_id")
    if not is_admin:
        target_hotel_id = hotel_id
    hotel = Hotel.objects.filter(pk=target_hotel_id).first() if target_hotel_id else None

    if staff is None:
        if len(password) < 8:
            return JsonResponse({"detail": "New employees need a password of at least 8 characters."}, status=400)
        parts = staff_name.split(maxsplit=1)
        staff = Staff.objects.create_user(
            username=email, email=email, password=password, staff_name=staff_name,
            staff_phone=staff_phone, role=role, hotel=hotel,
            first_name=parts[0], last_name=parts[1] if len(parts) > 1 else "",
        )
    else:
        staff.staff_name = staff_name
        staff.email = email
        staff.username = email
        staff.staff_phone = staff_phone
        staff.role = role
        staff.hotel = hotel
        if password:
            if len(password) < 8:
                return JsonResponse({"detail": "Password must be at least 8 characters."}, status=400)
            staff.set_password(password)
        staff.save()
    return JsonResponse({"detail": f"{staff.staff_name} saved.", "id": staff.pk})


@require_http_methods(["POST"])
def admin_staff_delete(request):
    """Remove an employee. Admins and the current user cannot be removed."""
    ctx = _admin_manage_context(request)
    if ctx is None:
        return JsonResponse({"detail": "You do not have permission to manage employees."}, status=403)
    is_admin, hotel_id = ctx
    payload = _payload_json(request)
    if payload is None:
        return JsonResponse({"detail": "Invalid JSON payload."}, status=400)

    from apps.accounts.models import Staff

    staff = Staff.objects.filter(pk=payload.get("id")).first()
    if staff is None:
        return JsonResponse({"detail": "Employee not found."}, status=404)
    if staff.pk == request.user.pk:
        return JsonResponse({"detail": "You cannot remove your own account."}, status=400)
    if staff.role == "admin":
        return JsonResponse({"detail": "Admin accounts cannot be removed."}, status=403)
    if not is_admin and staff.hotel_id != hotel_id:
        return JsonResponse({"detail": "You can only remove employees at your hotel."}, status=403)
    name = staff.staff_name
    staff.delete()
    return JsonResponse({"detail": f"{name} removed."})


@require_http_methods(["POST"])
def admin_hotel_save(request):
    """Create or update a hotel (admins only). Accepts JSON or multipart (image)."""
    ctx = _admin_manage_context(request)
    if ctx is None:
        return JsonResponse({"detail": "You do not have permission to manage hotels."}, status=403)
    is_admin, _ = ctx
    if not is_admin:
        return JsonResponse({"detail": "Only admins can add or edit hotels."}, status=403)

    if request.content_type and request.content_type.startswith("multipart"):
        payload = request.POST
        upload = request.FILES.get("hotel_image")
    else:
        payload = _payload_json(request)
        upload = None
    if payload is None:
        return JsonResponse({"detail": "Invalid form data."}, status=400)

    hotel_id = payload.get("id")
    hotel = None
    if hotel_id:
        hotel = Hotel.objects.filter(pk=hotel_id).first()
        if hotel is None:
            return JsonResponse({"detail": "Hotel not found."}, status=404)

    hotel_name = (payload.get("hotel_name") or "").strip()
    hotel_email = (payload.get("hotel_email") or "").strip().lower()
    hotel_phone = (payload.get("hotel_phone") or "").strip()
    hotel_address = (payload.get("hotel_address") or "").strip()
    category = (payload.get("category") or "").strip().upper()

    if not all([hotel_name, hotel_email, hotel_phone, hotel_address]):
        return JsonResponse({"detail": "Name, email, phone, and address are required."}, status=400)
    if category not in dict(Hotel.Category.choices):
        return JsonResponse({"detail": "Choose a valid category."}, status=400)
    if Hotel.objects.filter(hotel_email__iexact=hotel_email).exclude(pk=hotel.pk if hotel else None).exists():
        return JsonResponse({"detail": "A hotel with that email already exists."}, status=409)

    if hotel is None:
        hotel = Hotel()
    hotel.hotel_name = hotel_name
    hotel.hotel_email = hotel_email
    hotel.hotel_phone = hotel_phone
    hotel.hotel_address = hotel_address
    hotel.category = category
    if upload:
        if upload.size > 5 * 1024 * 1024 or not (upload.content_type or "").startswith("image/"):
            return JsonResponse({"detail": "Use an image file smaller than 5 MB."}, status=400)
        hotel.hotel_image = upload
    if payload.get("clear_image") == "1" and hotel.hotel_image:
        hotel.hotel_image.delete(save=False)
        hotel.hotel_image = None
    hotel.save()
    return JsonResponse({"detail": f"{hotel.hotel_name} saved.", "id": hotel.pk})


@require_http_methods(["POST"])
def admin_hotel_delete(request):
    """Delete a hotel (admins only)."""
    ctx = _admin_manage_context(request)
    if ctx is None:
        return JsonResponse({"detail": "You do not have permission to manage hotels."}, status=403)
    is_admin, _ = ctx
    if not is_admin:
        return JsonResponse({"detail": "Only admins can delete hotels."}, status=403)
    payload = _payload_json(request)
    if payload is None:
        return JsonResponse({"detail": "Invalid JSON payload."}, status=400)

    hotel = Hotel.objects.filter(pk=payload.get("id")).first()
    if hotel is None:
        return JsonResponse({"detail": "Hotel not found."}, status=404)
    if hotel.rooms.exists() or hotel.staff_members.exists():
        return JsonResponse({"detail": "Move or remove this hotel's rooms and staff before deleting it."}, status=409)
    name = hotel.hotel_name
    hotel.delete()
    return JsonResponse({"detail": f"{name} removed."})


def design_system(request):
    """Design system / hero welcome page."""
    return render(request, "frontend/design_system.html")


# ─── Staff Dashboard Operations API (JSON, session-auth, CSRF-protected) ───

def _dashboard_context(request, *allowed_roles):
    """Return (is_manager, hotel_id) for staff API callers, else None."""
    if not request.user.is_authenticated:
        return None
    # Allow superusers to act as managers/admins
    if getattr(request.user, "is_superuser", False):
        return True, request.user.hotel_id
    role = (request.user.role or "").lower()
    if role not in allowed_roles:
        return None
    return role in ("admin", "manager"), request.user.hotel_id


NO_HOTEL_MESSAGE = "You are not assigned to a hotel. Ask an admin to assign you first."


@require_http_methods(["POST"])
def staff_checkin(request):
    """Check a reservation into its room (receptionist / manager / admin)."""
    ctx = _dashboard_context(request, "receptionist", "manager", "admin")
    if ctx is None:
        return JsonResponse({"detail": "You do not have permission to check in guests."}, status=403)
    is_manager, hotel_id = ctx
    if not is_manager and not hotel_id:
        return JsonResponse({"detail": NO_HOTEL_MESSAGE}, status=400)
    payload = _payload_json(request)
    if payload is None:
        return JsonResponse({"detail": "Invalid JSON payload."}, status=400)

    reservation = Reservation.objects.select_related("guest", "hotel").filter(pk=payload.get("reservation_id")).first()
    if reservation is None:
        return JsonResponse({"detail": "Reservation not found."}, status=404)
    if not is_manager and reservation.hotel_id != hotel_id:
        return JsonResponse({"detail": "You can only check in reservations at your hotel."}, status=403)
    if reservation.status == Reservation.ReservationStatus.CHECKED_IN:
        return JsonResponse({"detail": "Guest is already checked in."}, status=409)
    if reservation.status in (Reservation.ReservationStatus.CHECKED_OUT, Reservation.ReservationStatus.CANCELLED, Reservation.ReservationStatus.NO_SHOW):
        return JsonResponse({"detail": f"This reservation is {reservation.status} and cannot be checked in."}, status=409)

    room = Room.objects.filter(reservation=reservation).first()
    if room is None:
        room = Room.objects.filter(room_reservations__resv=reservation).first()
    if room is None:
        return JsonResponse({"detail": "No room is assigned to this reservation."}, status=409)

    reservation.status = Reservation.ReservationStatus.CHECKED_IN
    reservation.actual_check_in = timezone.now()
    reservation.save(update_fields=["status", "actual_check_in"])
    room.status = Room.RoomStatus.OCCUPIED
    room.housekeeping_status = Room.HousekeepingStatus.OUT_OF_SERVICE
    room.save(update_fields=["status", "housekeeping_status"])
    return JsonResponse({"detail": f"{reservation.guest.guest_name} checked in to Room {room.room_number}."})


@require_http_methods(["POST"])
def staff_checkout(request):
    """Check a guest out and mark the room dirty for housekeeping."""
    ctx = _dashboard_context(request, "receptionist", "manager", "admin")
    if ctx is None:
        return JsonResponse({"detail": "You do not have permission to check out guests."}, status=403)
    is_manager, hotel_id = ctx
    if not is_manager and not hotel_id:
        return JsonResponse({"detail": NO_HOTEL_MESSAGE}, status=400)
    payload = _payload_json(request)
    if payload is None:
        return JsonResponse({"detail": "Invalid JSON payload."}, status=400)

    reservation = Reservation.objects.select_related("guest", "hotel").filter(pk=payload.get("reservation_id")).first()
    if reservation is None:
        return JsonResponse({"detail": "Reservation not found."}, status=404)
    if not is_manager and reservation.hotel_id != hotel_id:
        return JsonResponse({"detail": "You can only check out reservations at your hotel."}, status=403)
    if reservation.status != Reservation.ReservationStatus.CHECKED_IN:
        return JsonResponse({"detail": "Guest must be checked in before checking out."}, status=409)

    rooms = list(Room.objects.filter(reservation=reservation)) or list(Room.objects.filter(room_reservations__resv=reservation))
    reservation.status = Reservation.ReservationStatus.CHECKED_OUT
    reservation.actual_check_out = timezone.now()
    reservation.save(update_fields=["status", "actual_check_out"])
    for room in rooms:
        room.status = Room.RoomStatus.AVAILABLE
        room.reservation = None
        room.housekeeping_status = Room.HousekeepingStatus.DIRTY
        room.save(update_fields=["status", "reservation", "housekeeping_status"])
    return JsonResponse({"detail": f"{reservation.guest.guest_name} checked out."})


@require_http_methods(["POST"])
def staff_housekeeping_update(request):
    """Update a room's housekeeping status (housekeeping / receptionist / manager / admin)."""
    ctx = _dashboard_context(request, "housekeeping", "receptionist", "manager", "admin")
    if ctx is None:
        return JsonResponse({"detail": "You do not have permission to update room status."}, status=403)
    is_manager, hotel_id = ctx
    if not is_manager and not hotel_id:
        return JsonResponse({"detail": NO_HOTEL_MESSAGE}, status=400)
    payload = _payload_json(request)
    if payload is None:
        return JsonResponse({"detail": "Invalid JSON payload."}, status=400)

    room = Room.objects.select_related("hotel").filter(pk=payload.get("room_id")).first()
    if room is None:
        return JsonResponse({"detail": "Room not found."}, status=404)
    if not is_manager and room.hotel_id != hotel_id:
        return JsonResponse({"detail": "You can only update rooms at your hotel."}, status=403)

    status = (payload.get("status") or "").strip().upper()
    if status not in dict(Room.HousekeepingStatus.choices):
        return JsonResponse({"detail": "Invalid housekeeping status."}, status=400)
    room.housekeeping_status = status
    room.save(update_fields=["housekeeping_status"])
    return JsonResponse({"detail": f"Room {room.room_number} marked {status.replace('_', ' ').title()}."})


@require_http_methods(["POST"])
def staff_maintenance_update(request):
    """Advance a maintenance task's status (housekeeping / manager / admin)."""
    ctx = _dashboard_context(request, "housekeeping", "manager", "admin")
    if ctx is None:
        return JsonResponse({"detail": "You do not have permission to update maintenance."}, status=403)
    is_manager, hotel_id = ctx
    if not is_manager and not hotel_id:
        return JsonResponse({"detail": NO_HOTEL_MESSAGE}, status=400)
    payload = _payload_json(request)
    if payload is None:
        return JsonResponse({"detail": "Invalid JSON payload."}, status=400)

    from apps.rooms.models import Maintenance

    task = Maintenance.objects.select_related("room", "room__hotel").filter(pk=payload.get("task_id")).first()
    if task is None:
        return JsonResponse({"detail": "Maintenance task not found."}, status=404)
    if not is_manager and task.room.hotel_id != hotel_id:
        return JsonResponse({"detail": "You can only update tasks at your hotel."}, status=403)

    status = (payload.get("status") or "").strip().upper()
    if status not in dict(Maintenance.MaintenanceStatus.choices):
        return JsonResponse({"detail": "Invalid maintenance status."}, status=400)
    task.status = status
    if status in (Maintenance.MaintenanceStatus.RESOLVED, Maintenance.MaintenanceStatus.CLOSED):
        task.resolve_date = timezone.localdate()
    task.save(update_fields=["status", "resolve_date"])
    return JsonResponse({"detail": f"Task for Room {task.room.room_number} marked {status.replace('_', ' ').title()}."})


@require_http_methods(["POST"])
def staff_assign_room(request):
    """Assign an available room to a reservation (receptionist / manager / admin)."""
    ctx = _dashboard_context(request, "receptionist", "manager", "admin")
    if ctx is None:
        return JsonResponse({"detail": "You do not have permission to assign rooms."}, status=403)
    is_manager, hotel_id = ctx
    if not is_manager and not hotel_id:
        return JsonResponse({"detail": NO_HOTEL_MESSAGE}, status=400)
    payload = _payload_json(request)
    if payload is None:
        return JsonResponse({"detail": "Invalid JSON payload."}, status=400)

    reservation = Reservation.objects.filter(pk=payload.get("reservation_id")).first()
    room = Room.objects.select_related("hotel").filter(pk=payload.get("room_id")).first()
    if reservation is None:
        return JsonResponse({"detail": "Reservation not found."}, status=404)
    if room is None:
        return JsonResponse({"detail": "Room not found."}, status=404)
    if not is_manager and (reservation.hotel_id != hotel_id or room.hotel_id != hotel_id):
        return JsonResponse({"detail": "You can only assign rooms at your hotel."}, status=403)
    if room.status != Room.RoomStatus.AVAILABLE:
        return JsonResponse({"detail": f"Room {room.room_number} is not available."}, status=409)
    if reservation.status in (Reservation.ReservationStatus.CHECKED_IN, Reservation.ReservationStatus.CHECKED_OUT):
        return JsonResponse({"detail": "Reservation is already checked in or out."}, status=409)

    RoomReservation.objects.get_or_create(resv=reservation, room=room)
    room.status = Room.RoomStatus.RESERVED
    room.reservation = reservation
    room.save(update_fields=["status", "reservation"])
    return JsonResponse({"detail": f"Room {room.room_number} assigned to reservation #{reservation.id}."})


@require_http_methods(["GET"])
def accountant_export(request):
    """Download invoices + payments as a CSV report (accountant / manager / admin)."""
    ctx = _dashboard_context(request, "accountant", "manager", "admin")
    if ctx is None:
        return JsonResponse({"detail": "You do not have permission to export reports."}, status=403)
    is_manager, hotel_id = ctx
    if not is_manager and not hotel_id:
        return JsonResponse({"detail": NO_HOTEL_MESSAGE}, status=400)

    import csv
    from django.http import HttpResponse

    invoices = Invoice.objects.select_related("reservation", "reservation__guest").order_by("-issue_date")
    if not is_manager and hotel_id:
        invoices = invoices.filter(hotel_id=hotel_id)

    response = HttpResponse(content_type="text/csv; charset=utf-8")
    response["Content-Disposition"] = 'attachment; filename="stayhub-invoices.csv"'
    writer = csv.writer(response)
    writer.writerow(["Invoice #", "Guest", "Hotel", "Amount (GHS)", "Status", "Issued"])
    for invoice in invoices:
        writer.writerow([
            invoice.id,
            invoice.reservation.guest.guest_name if invoice.reservation and invoice.reservation.guest else "-",
            invoice.hotel.hotel_name if invoice.hotel else "-",
            invoice.total_amount,
            invoice.status,
            invoice.issue_date.strftime("%Y-%m-%d %H:%M"),
        ])
    return response


@require_http_methods(["GET"])
def staff_guest_search(request):
    """Search guests by name/email/phone so reception can prefill a walk-in booking."""
    ctx = _dashboard_context(request, "receptionist", "manager", "admin")
    if ctx is None:
        return JsonResponse({"detail": "You do not have permission to search guests."}, status=403)
    query = (request.GET.get("q") or "").strip()
    if not query:
        return JsonResponse({"results": []})
    from django.db.models import Q

    guests = Guest.objects.filter(
        Q(guest_name__icontains=query) | Q(guest_email__icontains=query) | Q(guest_phone__icontains=query)
    )[:10]
    return JsonResponse({"results": [{
        "id": g.id,
        "guest_name": g.guest_name,
        "guest_email": g.guest_email,
        "guest_phone": g.guest_phone,
        "id_number": g.id_number,
        "nationality": g.nationality,
    } for g in guests]})


@require_http_methods(["POST"])
def staff_record_payment(request):
    """Record a payment against an invoice and update its status (accountant / manager / admin)."""
    ctx = _dashboard_context(request, "accountant", "manager", "admin")
    if ctx is None:
        return JsonResponse({"detail": "You do not have permission to record payments."}, status=403)
    is_manager, hotel_id = ctx
    if not is_manager and not hotel_id:
        return JsonResponse({"detail": NO_HOTEL_MESSAGE}, status=400)
    payload = _payload_json(request)
    if payload is None:
        return JsonResponse({"detail": "Invalid JSON payload."}, status=400)

    from apps.billing.models import Payment

    invoice = (
        Invoice.objects.select_related("reservation", "reservation__guest", "hotel")
        .filter(pk=payload.get("invoice_id"))
        .first()
    )
    if invoice is None:
        return JsonResponse({"detail": "Invoice not found."}, status=404)
    if not is_manager and invoice.hotel_id != hotel_id:
        return JsonResponse({"detail": "You can only record payments at your hotel."}, status=403)

    amount_raw = payload.get("amount")
    try:
        amount = Decimal(amount_raw) if amount_raw not in (None, "") else Decimal(0)
        if amount <= 0:
            raise ValueError
    except Exception:
        return JsonResponse({"detail": "Amount must be a positive number."}, status=400)

    method = (payload.get("method") or "").strip()
    if method not in dict(Payment.PaymentMethod.choices):
        return JsonResponse({"detail": "Choose a valid payment method."}, status=400)

    if invoice.status == Invoice.InvoiceStatus.VOID:
        return JsonResponse({"detail": "Voided invoices cannot receive payments."}, status=409)
    if invoice.status == Invoice.InvoiceStatus.PAID:
        return JsonResponse({"detail": f"Invoice #{invoice.pk} is already fully paid."}, status=409)

    balance = invoice.balance_due
    if amount > balance:
        return JsonResponse({"detail": f"Amount exceeds the balance of GH₵{balance}."}, status=400)

    Payment.objects.create(
        hotel=invoice.hotel,
        invoice=invoice,
        amount=amount,
        method=method,
        status=Payment.PaymentStatus.SUCCESS,
    )
    paid = invoice.amount_paid
    if paid >= invoice.total_amount:
        invoice.status = Invoice.InvoiceStatus.PAID
    elif paid > 0:
        invoice.status = Invoice.InvoiceStatus.PARTIAL
    invoice.save(update_fields=["status"])
    return JsonResponse({"detail": f"GH₵{amount} recorded for Invoice #{invoice.pk}."})