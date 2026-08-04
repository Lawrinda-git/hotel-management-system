from django.core.management.base import BaseCommand
from apps.accounts.models import Staff
from apps.hotels.models import Hotel, Department


class Command(BaseCommand):
    help = "Create sample staff accounts for testing"

    def handle(self, *args, **options):
        # Remove all non-admin staff accounts but preserve superusers and the admin email
        preserved_emails = ["admin@stayhub.com"]
        preserved_qs = Staff.objects.filter(email__in=preserved_emails) | Staff.objects.filter(is_superuser=True)
        to_delete_qs = Staff.objects.exclude(pk__in=preserved_qs.values_list("pk", flat=True))
        deleted_count = to_delete_qs.count()
        if deleted_count:
            to_delete_qs.delete()
            self.stdout.write(self.style.SUCCESS(f"Removed {deleted_count} non-admin staff accounts"))
        else:
            self.stdout.write(self.style.NOTICE("No non-admin staff accounts to remove"))

        # Create per-hotel staff accounts (manager, receptionist, accountant, housekeeping, labourer)
        hotels = list(Hotel.objects.all())
        if not hotels:
            # Fallback: create a single global set (useful before seeding hotels)
            staff_accounts = [
                {"staff_name": "Admin User", "email": "admin@stayhub.com", "password": "admin123456", "role": "admin"},
                {"staff_name": "John Manager", "email": "manager@stayhub.com", "password": "manager123", "role": "manager"},
                {"staff_name": "Sarah Receptionist", "email": "reception@stayhub.com", "password": "reception123", "role": "receptionist"},
                {"staff_name": "Mike Accountant", "email": "accountant@stayhub.com", "password": "accountant123", "role": "accountant"},
                {"staff_name": "Lisa Housekeeping", "email": "housekeeping@stayhub.com", "password": "housekeeping123", "role": "housekeeping"},
            ]
            for account in staff_accounts:
                user, created = Staff.objects.update_or_create(
                    email=account["email"],
                    defaults={
                        "username": account["email"],
                        "staff_name": account["staff_name"],
                        "staff_phone": "+233241234567",
                        "role": account["role"],
                    },
                )
                if created:
                    user.set_password(account["password"])
                    user.save()
                    self.stdout.write(self.style.SUCCESS(f"Created: {account['staff_name']} ({account['role']})"))
                else:
                    if account["email"] != "admin@stayhub.com":
                        user.set_password(account["password"])
                        user.save()
                        self.stdout.write(self.style.SUCCESS(f"Updated password: {account['email']}"))
                    else:
                        self.stdout.write(self.style.WARNING(f"Preserved admin account: {account['email']}"))
            self.stdout.write(self.style.WARNING("No hotels found — created global fallback staff accounts."))
        else:
            role_passwords = {
                "manager": "manager123",
                "receptionist": "reception123",
                "accountant": "accountant123",
                "housekeeping": "housekeeping123",
                "labourer": "labourer123",
            }
            for hotel in hotels:
                safe_name = hotel.slug if hasattr(hotel, "slug") and hotel.slug else hotel.name.replace(" ", "_").lower()
                # create manager, receptionist, accountant, housekeeping
                for role in ["manager", "receptionist", "accountant", "housekeeping"]:
                    email = f"{role}+{safe_name}@stayhub.com"
                    display_name = f"{role.title()} ({hotel.name})"
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
                    # set demo password for non-admin roles
                    user.set_password(role_passwords.get(role, "password123"))
                    user.save()
                    if created:
                        self.stdout.write(self.style.SUCCESS(f"Created {role} for hotel: {hotel.name} ({email})"))
                    else:
                        self.stdout.write(self.style.SUCCESS(f"Updated {role} for hotel: {hotel.name} ({email})"))

                # create a labourer for the hotel
                labour_email = f"labourer+{safe_name}@stayhub.com"
                labour_name = f"Labourer ({hotel.name})"
                labour, created = Staff.objects.update_or_create(
                    email=labour_email,
                    defaults={
                        "username": labour_email,
                        "staff_name": labour_name,
                        "staff_phone": "+233241200000",
                        "role": "labourer",
                        "hotel_id": hotel.id,
                    },
                )
                labour.set_password(role_passwords.get("labourer", "labourer123"))
                labour.save()
                if created:
                    self.stdout.write(self.style.SUCCESS(f"Created labourer for hotel: {hotel.name} ({labour_email})"))
                else:
                    self.stdout.write(self.style.SUCCESS(f"Updated labourer password for: {labour_email}"))

        # Create departments if they don't exist (informational)
        if not Department.objects.exists():
            self.stdout.write(self.style.SUCCESS("Departments ready for assignment in admin panel"))