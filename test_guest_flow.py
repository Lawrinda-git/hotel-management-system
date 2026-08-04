"""Test the registration/login flow after moving guests to the Guest table."""
import json
import os
import sys

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
import django
django.setup()

from django.test import Client
from apps.accounts.models import Staff
from apps.guests.models import Guest

def main():
    print("=== Guest registration/login flow test ===")
    client = Client()

    # 1. Register a new guest
    print("\n[1] Register a new guest...")
    resp = client.post(
        "/api/auth/register/",
        data=json.dumps({
            "full_name": "Test Guest User",
            "email": "testguest@example.com",
            "country_code": "+233",
            "phone": "241234567",
            "password": "SecurePass123",
        }),
        content_type="application/json",
    )
    print(f"  Status: {resp.status_code}")
    print(f"  Detail: {resp.json().get('detail')}")

    # 2. Verify guest is in the Guest table, NOT in Staff
    guest = Guest.objects.filter(guest_email="testguest@example.com").first()
    in_staff = Staff.objects.filter(email="testguest@example.com").exists()
    print(f"\n[2] Guest in guest table: {bool(guest)}")
    print(f"    Guest in staff table: {in_staff}   (should be False)")
    if guest:
        print(f"    Password check: {guest.check_password('SecurePass123')}")

    # 3. Login as the guest
    print("\n[3] Login as the guest...")
    client = Client()
    resp = client.post(
        "/api/auth/login/",
        data=json.dumps({"email": "testguest@example.com", "password": "SecurePass123"}),
        content_type="application/json",
    )
    print(f"  Status: {resp.status_code}")
    print(f"  Detail: {resp.json().get('detail')}")
    print(f"  Redirect: {resp.json().get('redirect_url')}")

    # 4. Wrong password
    print("\n[4] Login with wrong password...")
    resp = client.post(
        "/api/auth/login/",
        data=json.dumps({"email": "testguest@example.com", "password": "wrongpass"}),
        content_type="application/json",
    )
    print(f"  Status: {resp.status_code}  Detail: {resp.json().get('detail')}")

    # 5. Staff login attempt should be blocked
    print("\n[5] Attempt staff_login as guest...")
    resp = client.post(
        "/api/auth/login/",
        data=json.dumps({"email": "testguest@example.com", "password": "SecurePass123", "staff_login": True}),
        content_type="application/json",
    )
    print(f"  Status: {resp.status_code}  Detail: {resp.json().get('detail')}")

    print("\n=== Test complete ===")

if __name__ == "__main__":
    main()