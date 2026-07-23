from django.core.management.base import BaseCommand
from apps.accounts.models import Staff
from apps.hotels.models import Hotel, Department


class Command(BaseCommand):
    help = "Create sample staff accounts for testing"

    def handle(self, *args, **options):
        # Create sample staff accounts
        staff_accounts = [
            {"staff_name": "Admin User", "email": "admin@stayhub.com", "password": "admin123456", "role": "admin"},
            {"staff_name": "John Manager", "email": "manager@stayhub.com", "password": "manager123", "role": "manager"},
            {"staff_name": "Sarah Receptionist", "email": "reception@stayhub.com", "password": "reception123", "role": "receptionist"},
            {"staff_name": "Mike Accountant", "email": "accountant@stayhub.com", "password": "accountant123", "role": "accountant"},
            {"staff_name": "Lisa Housekeeping", "email": "housekeeping@stayhub.com", "password": "housekeeping123", "role": "housekeeping"},
        ]
        
        for account in staff_accounts:
            if not Staff.objects.filter(email=account["email"]).exists():
                user = Staff.objects.create_user(
                    username=account["email"],
                    email=account["email"],
                    password=account["password"],
                    staff_name=account["staff_name"],
                    staff_phone="+233241234567",
                    role=account["role"],
                )
                self.stdout.write(self.style.SUCCESS(f"Created: {account['staff_name']} ({account['role']})"))
            else:
                self.stdout.write(self.style.WARNING(f"Skipped: {account['email']} already exists"))
        
        # Create departments if they don't exist
        if not Department.objects.exists():
            Hotel.objects.all().first()
            # Departments would be created here if hotel exists
            self.stdout.write(self.style.SUCCESS("Departments ready for assignment in admin panel"))