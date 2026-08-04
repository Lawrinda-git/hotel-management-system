import re

from django.core.management.base import BaseCommand
from apps.accounts.models import Staff
from apps.hotels.models import Hotel, Department


# Map hotel names to short identifiers for email generation.
# e.g. "Elmina Beach Resort" → "elmina" → managerelmina@stayhub.com
HOTEL_SHORT_NAMES = {
    "la palm royal beach hotel": "lapalm",
    "royal senchi resort": "senchi",
    "kempinski hotel gold coast city": "kempinski",
    "labadi beach hotel": "labadi",
    "elmina beach resort": "elmina",
    "mövenpick ambassador hotel accra": "movenpick",
    "cape coast castle hotel": "capecoast",
    "busua beach resort": "busua",
}


def _short_hotel_name(hotel_name):
    """Return a short identifier for a hotel name, falling back to a slug."""
    key = hotel_name.strip().lower()
    if key in HOTEL_SHORT_NAMES:
        return HOTEL_SHORT_NAMES[key]
    # Fallback: first word of the hotel name, lowercased
    first_word = re.sub(r"[^a-z0-9]+", "", key.split()[0]) if key.split() else "hotel"
    return first_word or "hotel"


class Command(BaseCommand):
    help = "Create sample staff accounts for testing"

    def handle(self, *args, **options):
        # ── 1. Preserve the global admin, remove all other non-admin staff ──
        preserved_emails = ["admin@stayhub.com"]
        preserved_qs = Staff.objects.filter(email__in=preserved_emails) | Staff.objects.filter(is_superuser=True)
        to_delete_qs = Staff.objects.exclude(pk__in=preserved_qs.values_list("pk", flat=True))
        deleted_count = to_delete_qs.count()
        if deleted_count:
            to_delete_qs.delete()
            self.stdout.write(self.style.SUCCESS(f"Removed {deleted_count} non-admin staff accounts"))
        else:
            self.stdout.write(self.style.NOTICE("No non-admin staff accounts to remove"))

        # ── 2. Ensure the global admin exists ──
        admin, created = Staff.objects.update_or_create(
            email="admin@stayhub.com",
            defaults={
                "username": "admin@stayhub.com",
                "staff_name": "Admin User",
                "staff_phone": "+233241234567",
                "role": "admin",
                "is_superuser": True,
                "is_staff": True,
            },
        )
        if created:
            admin.set_password("admin123456")
            admin.save()
            self.stdout.write(self.style.SUCCESS("Created global admin: admin@stayhub.com / admin123456"))
        else:
            self.stdout.write(self.style.SUCCESS("Preserved global admin: admin@stayhub.com"))

        # ── 3. Create per-hotel staff (manager, receptionist, accountant, housekeeping, labourer) ──
        hotels = list(Hotel.objects.all())
        if not hotels:
            self.stdout.write(self.style.WARNING("No hotels found — only the global admin was created. Run seed_demo_data or seed_full_demo first."))
            return

        role_passwords = {
            "manager": "manager123",
            "receptionist": "reception123",
            "accountant": "accountant123",
            "housekeeping": "housekeeping123",
            "labourer": "labourer123",
        }

        for hotel in hotels:
            short_name = _short_hotel_name(hotel.hotel_name)

            for role in ["manager", "receptionist", "accountant", "housekeeping", "labourer"]:
                email = f"{role}{short_name}@stayhub.com"
                display_name = f"{role.title()} ({hotel.hotel_name})"
                user, created = Staff.objects.update_or_create(
                    email=email,
                    defaults={
                        "username": email,
                        "staff_name": display_name,
                        "staff_phone": "+233241234567",
                        "role": role,
                        "hotel_id": hotel.id,
                    },
                )
                user.set_password(role_passwords.get(role, "password123"))
                user.save()
                action = "Created" if created else "Updated"
                self.stdout.write(self.style.SUCCESS(f"{action} {role} for hotel: {hotel.hotel_name} ({email})"))

        # ── 4. Create departments if they don't exist (informational) ──
        if not Department.objects.exists():
            self.stdout.write(self.style.SUCCESS("Departments ready for assignment in admin panel"))