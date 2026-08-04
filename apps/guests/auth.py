"""
Custom authentication backend that authenticates against the Guest model
instead of the staff (accounts.Staff) model.

Public users who register on the web app are stored in the ``guest`` table
(see apps/guests/models.py). They carry a hashed ``password`` so they can
sign in to view their bookings — but they are never placed in the ``staff``
table, keeping the staff roster clean and preventing admins from mistaking
guests for employees.

This backend returns a thin ``GuestUser`` adapter so the existing web views
and templates that reference ``request.user.email``, ``request.user.role``,
``request.user.is_authenticated``, etc. keep working unchanged.
"""

from django.contrib.auth.backends import BaseBackend

from .models import Guest


class _GuestUserPkField:
    """Fake PK field that mimics Django's AutoField for session serialization."""
    def value_to_string(self, obj):
        return str(obj.pk)


class _GuestUserMeta:
    """Minimal stand-in for Django's Model._meta so login() can serialize the user id."""
    def __init__(self, pk):
        self.pk = _GuestUserPkField()


class GuestUser:
    """Adapter that lets a Guest be used as Django's request.user."""

    is_authenticated = True
    is_anonymous = False
    is_active = True
    is_staff = False
    is_superuser = False
    role = "guest"
    # Required by django.contrib.auth.login when multiple backends are configured.
    backend = "apps.guests.auth.GuestBackend"

    def __init__(self, guest):
        self._guest = guest
        self.pk = guest.pk
        self.id = guest.pk
        self._meta = _GuestUserMeta(guest.pk)
        self.email = guest.guest_email
        self.username = guest.guest_email
        self.staff_name = guest.guest_name
        self.staff_phone = guest.guest_phone
        self.first_name = ""
        self.last_name = ""
        # Guests have no dashboard/hotel/department scoping.
        self.hotel = None
        self.hotel_id = None
        self.department = None
        self.department_id = None
        self.profile_picture = None
        self.two_factor_enabled = False

    def get_full_name(self):
        return self._guest.guest_name or self._guest.guest_email

    def get_short_name(self):
        return self._guest.guest_name.split()[0] if self._guest.guest_name else ""

    def get_username(self):
        return self._guest.guest_email

    def has_usable_password(self):
        return bool(self._guest.password)

    def has_perm(self, perm, obj=None):
        return False

    def has_module_perms(self, app_label):
        return False

    # login() fires user_logged_in -> update_last_login -> user.save().
    # Guests don't track last_login, so make save() a no-op here.
    def save(self, *args, **kwargs):
        pass

    def __str__(self):
        return self._guest.guest_email

    def __eq__(self, other):
        if not isinstance(other, GuestUser):
            return False
        return self.pk == other.pk


class GuestBackend(BaseBackend):
    """
    Authenticate a guest by email + password.

    Used by Django's authentication framework when ``login(request, user)``
    is called with a GuestUser adapter. The adapter's ``pk`` is the Guest's
    primary key; because this backend is stored alongside the id in the
    session, it never collides with the staff (ModelBackend) ids.
    """

    def authenticate(self, request, username=None, password=None, **kwargs):
        identifier = (
            kwargs.get("email")
            or kwargs.get("identifier")
            or username
            or ""
        ).strip().lower()
        if not identifier or not password:
            return None

        guest = Guest.objects.filter(guest_email__iexact=identifier).first()
        if guest is None or not guest.is_active:
            return None
        if not guest.password or not guest.check_password(password):
            return None
        return GuestUser(guest)

    def get_user(self, user_id):
        try:
            guest = Guest.objects.get(pk=user_id, is_active=True)
        except Guest.DoesNotExist:
            return None
        return GuestUser(guest)