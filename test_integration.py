import urllib.request
import json

BASE = "http://localhost:8000"

def test(name, url, method="GET", data=None, expected_status=None):
    try:
        if method == "POST" and data:
            payload = json.dumps(data).encode()
            req = urllib.request.Request(f"{BASE}{url}", data=payload,
                                         headers={"Content-Type": "application/json"})
        else:
            req = urllib.request.Request(f"{BASE}{url}")
        r = urllib.request.urlopen(req, timeout=10)
        body = r.read()
        result = f"[PASS] {name} - Status: {r.status}, Length: {len(body)}"
        if expected_status:
            result += f" (expected {expected_status})" if r.status != expected_status else ""
        print(result)
        return True, r.status, body
    except urllib.error.HTTPError as e:
        code = e.code
        body = e.read()
        try:
            detail = json.loads(body).get("detail", body[:100])
        except:
            detail = body[:100]
        result = f"[FAIL] {name} - Status: {code}, Detail: {detail}"
        if expected_status and code == expected_status:
            result = f"[PASS] {name} - Status: {code} (expected {expected_status}), Detail: {detail}"
        print(result)
        return False, code, body
    except Exception as e:
        print(f"[ERROR] {name} - {e}")
        return False, None, None

print("=" * 60)
print(" INTEGRATION TESTS - Frontend <-> Backend")
print("=" * 60)

# 1. Frontend pages load
test("Splash page", "/splash/")
test("Sign-in page", "/signin/")
test("Staff login page", "/staff-login/")
test("Create account page", "/create-account/")
test("Guest home page", "/home/")
test("Explore stays page", "/explore/")
test("Booking page", "/booking/")
test("Manager dashboard", "/manager/")
test("Receptionist dashboard", "/receptionist/")
test("Accountant dashboard", "/accountant/")
test("Housekeeping dashboard", "/housekeeping/")
test("Design system", "/design-system/")

# 2. Booking API
test("Booking options API", "/api/booking/options/")

# 3. Registration
test("Register user", "/api/auth/register/", "POST",
     {"full_name": "Test User", "email": "inttest@example.com", "password": "TestPass123"},
     expected_status=201)

# 4. Login
test("Login registered user", "/api/auth/login/", "POST",
     {"email": "inttest@example.com", "password": "TestPass123"})

# 5. Duplicate registration (should 409)
test("Duplicate registration", "/api/auth/register/", "POST",
     {"full_name": "Test User", "email": "inttest@example.com", "password": "TestPass123"},
     expected_status=409)

# 6. Login bad password
test("Login wrong password", "/api/auth/login/", "POST",
     {"email": "inttest@example.com", "password": "WrongPass123"},
     expected_status=400)

print("=" * 60)
print(" TESTS COMPLETE")
print("=" * 60)