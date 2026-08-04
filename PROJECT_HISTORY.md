# StayHub Hotel Management System — Project History

## Project Overview

**StayHub** is a full-stack hotel management platform that allows guests to discover and book rooms online, and allows hotel staff (admin, manager, receptionist, accountant, housekeeping) to run day-to-day operations from role-based dashboards.

**Repository:** `https://github.com/Lawrinda-git/hotel-management-system.git`

---

## Timeline of Development

### Phase 1 — Core Project Scaffolding
- Created Django project structure (`config/` settings, apps directory)
- Set up custom user model (`Staff` extending `AbstractUser`) in `apps/accounts/`
- Configured PostgreSQL/SQLite database support via `DB_ENGINE` env variable
- Created all domain apps:
  - `apps/hotels/` — Hotel, Department models
  - `apps/rooms/` — RoomType, Room, Maintenance models
  - `apps/guests/` — Guest model
  - `apps/reservations/` — Reservation, RoomReservation models
  - `apps/services/` — Service, ServiceRequest models
  - `apps/billing/` — Invoice, Payment models
  - `apps/feedback/` — Feedback model
  - `apps/notifications/` — Notification model
- Defined all models with proper enumerations, constraints, and relationships

### Phase 2 — Web Frontend (Django Templates + Material Design 3)
- Built `frontend/templates/frontend/` with server-rendered templates:
  - Guest pages: splash, landing, signin, create_account, guest_home, explore_stays, hotel_details, booking, reservation_confirmed, profile, team
  - Staff pages: staff_login, admin_signup, manager_dashboard, receptionist_dashboard, accountant_dashboard, housekeeping_dashboard, admin_management, staff_profile, access_denied
  - Auth pages: password_reset (all 5), verification, verification_method
- Created Material Design 3 design system in `frontend/static/frontend/css/`
- Implemented Tailwind CSS with custom design tokens in `base.html`
- Built responsive layout with bottom navigation for guest/staff flows

### Phase 3 — Authentication & Security
- Implemented role-based authentication (admin/manager/receptionist/accountant/housekeeping/guest)
- Added Google OAuth login flow (`google_login`, `google_callback`)
- Implemented 2FA verification (email/SMS) with `_begin_two_factor`
- Added password reset using Django's built-in views
- Created admin signup flow (first admin auto-created with no key)
- Session-based login for web, SimpleJWT for API

### Phase 4 — Booking & Payments
- Built 4-step booking flow (dates → room → guest details → confirm)
- Auto-generated invoices: `(nightly rate × nights) + ₵45 service fee + 12% tax`
- Integrated Paystack payments:
  - Checkout init endpoint
  - HMAC-SHA512 webhook verification
  - Payment verification fallback
- Partial payment support (multiple Payment rows per Invoice)
- Reservation status polling endpoint

### Phase 5 — Staff Dashboards & Admin Management
- `manager_dashboard` — KPIs, today's check-ins/out, live room grid, reservations, maintenance
- `receptionist_dashboard` — arrivals/departures, room grid, Find Guest / New Walk-in
- `accountant_dashboard` — invoices, payments, financial overview
- `housekeeping_dashboard` — dirty/clean/inspected rooms, maintenance tasks
- `admin_management` — tabbed interface (Rooms, Employees, Hotels, Maintenance)
- Branch scoping: staff only see data for their assigned hotel

### Phase 6 — Mobile App
- Created `mobile-app/` Expo React Native project
- Screens: Login, Home, Search, Bookings, Profile (partial)
- Mobile API endpoints: rooms, check-in, check-out, housekeeping update

### Phase 7 — Landing Page & Guest Home Improvements
- Created `landing.html` hero page (between splash and signin)
- Updated splash to auto-redirect to landing
- Added hotel ID params to hotel detail links (3 hotels)
- Added category filter params (8 categories)
- Replaced "View all" link with dropdown menu
- Made search bar functional with query params
- Fixed bottom nav on mobile pages (explore_stays, booking, profile)

### Phase 8 — Offline-Ready Assets (Most Recent Work)
- **Tailwind CSS:** Downloaded local `tailwindcss.js` (407 KB) to `frontend/static/frontend/js/`
- **Google Fonts:** Downloaded all fonts locally via `download_fonts.py`:
  - Hanken Grotesk (4 woff2 files)
  - Noto Serif (8 woff2 files)
  - Material Symbols Outlined (1 woff2 file, 1.1 MB)
- **Font CSS:** Created `hanken-grotesk.css`, `noto-serif.css`, `material-symbols.css` in `frontend/static/frontend/css/`
- **Updated `base.html`** to use `{% static %}` paths instead of CDN URLs
- **Verified:** All static files return HTTP 200; no internet needed for CSS/fonts

### Phase 9 — Database Structure, Permissions & Deployment Docs
- Documented full database schema (21 tables: 10 app + 11 Django framework)
- Documented PostgreSQL permissions for `hotel_user` on Debian
- Documented ngrok hosting setup for the project

---

## Current Architecture

### Tech Stack
| Layer | Technology |
|-------|------------|
| Backend | Python 3.12+, Django 6.0.6, DRF 3.17 |
| Auth | SimpleJWT, Django sessions, custom 2FA, Google OAuth |
| Database | SQLite (default) / PostgreSQL |
| Payments | Paystack |
| Email/SMS | Brevo (Gmail SMTP fallback) |
| Frontend | Django templates, Material Design 3, Tailwind CSS (local) |
| Mobile | React Native 0.73, Expo 50 |

### Directory Structure
```
project/
├── apps/                     # Domain apps
│   ├── accounts/             # Staff (custom user)
│   ├── billing/              # Invoice, Payment
│   ├── common/               # Mixins
│   ├── feedback/             # Feedback
│   ├── guests/               # Guest
│   ├── hotels/               # Hotel, Department
│   ├── mobile/               # Mobile API endpoints
│   ├── notifications/        # Notification
│   ├── reservations/         # Reservation, RoomReservation
│   ├── rooms/                # RoomType, Room, Maintenance
│   └── services/             # Service, ServiceRequest
├── config/                   # Django settings
├── frontend/
│   ├── templates/frontend/   # All HTML templates
│   ├── static/frontend/      # CSS, JS, fonts, images
│   ├── views.py              # Web + auth API views
│   └── email_backend.py      # Brevo
├── mobile-app/               # Expo React Native
├── manage.py
├── requirements.txt
└── .env                      # Real credentials (git-ignored)
```

### Database Models
| Model | Table | Key Fields |
|-------|-------|------------|
| Staff | `staff` | username, email, role, staff_name, staff_phone, hotel FK, department FK |
| Hotel | `hotel` | hotel_name, hotel_email, hotel_phone, hotel_address, category, hotel_image |
| Department | `department` | dept_name, hotel FK |
| Guest | `guest` | guest_name, guest_email (unique), guest_phone, id_number, nationality |
| RoomType | `room_type` | type_name, price_per_night, hotel FK |
| Room | `room` | room_number, floor, status, housekeeping_status, hotel FK, room_type FK, reservation FK |
| Reservation | `reservation` | check_in, check_out, actual_check_in, actual_check_out, status, guest FK, hotel FK |
| RoomReservation | `room_reservation` | resv FK, room FK (junction table) |
| Invoice | `invoice` | total_amount, status, reservation 1:1 FK, hotel FK |
| Payment | `payment` | amount, method, status, provider_reference, invoice FK, hotel FK |
| Service | `service` | service_name, price, category, hotel FK |
| ServiceRequest | `service_request` | request_time, status, service FK, resv FK, staff FK |
| Feedback | `feedback` | rating (1-5), comments, guest FK, resv FK, hotel FK |
| Maintenance | `maintenance` | issue, report_date, resolve_date, status, staff FK, room FK, hotel FK |
| Notification | `notification` | notification_type, message, is_read, user FK |

### Key Integration Points
- **Paystack:** `/api/billing/paystack/checkout/`, `/api/billing/paystack/webhook/`, `/api/billing/paystack/verify/<ref>/`
- **Google OAuth:** `/api/auth/google/`, `/api/auth/google/callback/`
- **Brevo:** `frontend/email_backend.py`, `_send_verification_sms`
- **Mobile:** `/api/mobile/rooms/`, `/api/mobile/checkin/`, `/api/mobile/checkout/`, `/api/mobile/housekeeping/update/`

---

## Current Deployment Configuration (`.env`)

The `.env` file contains **real credentials** appropriate for development:

| Variable | Value | Status |
|----------|-------|--------|
| DB_ENGINE | `postgresql` | PostgreSQL |
| DB_NAME | `hotel_db` | |
| DB_USER | `hotel_user` | Needs full permissions |
| DB_PASSWORD | `myhotel123` | Development only |
| GOOGLE_OAUTH_CLIENT_ID | `805617532369-...` | Real |
| GOOGLE_OAUTH_CLIENT_SECRET | `GOCSPX-...` | Real |
| PAYSTACK_SECRET_KEY | `sk_test_...` | Test keys |
| PAYSTACK_PUBLIC_KEY | `pk_test_...` | Test keys |
| BREVO_API_KEY | `xkeysib-...` | Real |
| SMTP_* | Gmail creds | Real |
| CSRF_TRUSTED_ORIGINS | `http://localhost:8000,https://*.devtunnels.ms` | dev-tunnel-ready |

> ⚠️ **WARNING:** Never commit `.env` — it's git-ignored. Contains real API keys/secrets.

---

## Pending / Known Issues

### 1. Staff Login Not Working (⚠️ Reported by user)
The staff login flow submits to `/api/auth/login/` with `staff_login: true`. The issue is in the frontend JavaScript/handler — needs debugging:
- Staff login template at `frontend/templates/frontend/staff_login.html`
- The `api_login` view in `frontend/views.py` (lines 210-244)
- Verify CSRF token passing, form field names (`username` vs `email`), and role-based redirect

### 2. Images Need Local Downloading (⚠️ Reported by user)
All images in HTML templates should be downloaded to local storage:
- `frontend/static/frontend/img/` already has 25 images
- Some images may still reference external URLs in templates
- Need to scan all templates for `http://` or `https://` image references

### 3. Mobile App — SignUpScreen Missing
- `mobile-app/App.js` imports `./src/screens/SignUpScreen` but file doesn't exist
- Need to create the screen or remove the import

### 4. Admin Management — CRUD Actions "Coming Soon"
- Rooms tab: Add/Edit/Delete buttons are placeholders
- Employees tab: Add/Edit/Remove buttons are placeholders
- Hotels tab: Add Property button is a placeholder
- Maintenance tab: Only display, no actions

### 5. Landing Page / Design System Page
- `design_system` view (line 886) exists but template may need review

---

## Setup Instructions (Quick Start)

```bash
# 1. Clone & venv
git clone <repo-url> && cd project
python -m venv venv
source venv/Scripts/activate   # Windows
# source venv/bin/activate     # Linux/Mac

# 2. Install deps
pip install -r requirements.txt

# 3. Configure .env (copy .env.example and fill in)
cp .env.example .env

# 4. Postgres on Debian (if using PostgreSQL)
sudo apt install postgresql
sudo -u postgres psql
#   CREATE USER hotel_user WITH PASSWORD 'myhotel123';
#   CREATE DATABASE hotel_db OWNER hotel_user;
#   GRANT ALL ON SCHEMA public TO hotel_user;
#   ... etc

# 5. Migrate & seed
python manage.py migrate
python manage.py seed_demo_data
python manage.py seed_operations_data
python manage.py create_sample_accounts

# 6. Run
python manage.py runserver 0.0.0.0:8000
```

### Sample Staff Accounts
| Role | Email | Password |
|------|-------|----------|
| Admin | `admin@stayhub.com` | `admin123456` |
| Manager | `manager@stayhub.com` | `manager123` |
| Receptionist | `reception@stayhub.com` | `reception123` |
| Accountant | `accountant@stayhub.com` | `accountant123` |
| Housekeeping | `housekeeping@stayhub.com` | `housekeeping123` |

---

## ngrok Hosting (Current Setup)

```bash
# 1. Install ngrok
curl -s https://ngrok-agent.s3.amazonaws.com/ngrok.asc | sudo tee /etc/apt/trusted.gpg.d/ngrok.asc >/dev/null
echo "deb https://ngrok-agent.s3.amazonaws.com buster main" | sudo tee /etc/apt/sources.list.d/ngrok.list
sudo apt update && sudo apt install -y ngrok
ngrok config add-authtoken YOUR_TOKEN

# 2. Run Django (0.0.0.0 required for ngrok)
python manage.py runserver 0.0.0.0:8000

# 3. Start ngrok in a separate terminal
ngrok http 8000

# 4. Update .env + Google Cloud Console with the new ngrok URL