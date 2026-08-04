# StayHub — Hotel Management System

A full-stack hotel management platform that lets guests discover and book rooms online and lets hotel staff (admin, manager, receptionist, accountant, housekeeping) run day-to-day operations from role-based dashboards.

- **Backend & Web UI:** Django 6 + Django REST Framework (server-rendered templates, Material Design 3)
- **Mobile App:** React Native / Expo (guest booking on the go)
- **Payments:** Paystack (server-side checkout, signed webhook, partial payments)
- **Auth:** Role-based accounts, 2FA (email/SMS), Google OAuth, password reset

---

## Table of Contents

- [Features](#features)
- [Tech Stack](#tech-stack)
- [Project Structure](#project-structure)
- [Prerequisites](#prerequisites)
- [Quick Start](#quick-start)
- [Configuration (Environment Variables)](#configuration-environment-variables)
- [Seed Data](#seed-data)
- [Staff Roles](#staff-roles)
- [Web Pages & Flow](#web-pages--flow)
- [REST API](#rest-api)
- [Payments (Paystack)](#payments-paystack)
- [Mobile App](#mobile-app)
- [Running Tests](#running-tests)
- [Deployment Notes](#deployment-notes)
- [Documentation](#documentation)

---

## Features

### Guest (Public Web)
- Splash → landing → sign-in / account creation
- Browse hotels with **category filters** (Resort, Hotel, Cabin, Villa, Apartment, Homestay, Guest House) and search
- Hotel details pages with ratings, pricing, and category badges
- **4-step booking flow** (dates → room → guest details → confirm) with auto-generated invoice
- **Paystack** payment from the reservation confirmation page
- Reservation status polling and guest profile management
- Google OAuth sign-in, password reset, 2FA verification

### Staff (Role-Based Dashboards)
- **Admin / Manager:** KPIs, today's check-ins/check-outs, live room grid, recent reservations & maintenance, tabbed admin management (Rooms, Employees, Hotels, Maintenance)
- **Receptionist:** arrivals/departures, room grid, Find Guest / New Walk-in booking actions
- **Accountant:** invoices, payments, paid/unpaid financial overview
- **Housekeeping:** dirty/clean/inspected room buckets, open maintenance tasks
- Staff profiles with picture upload and change password

### Platform
- **Branch scoping:** branch staff only see data for their assigned hotel; managers/admins see everything
- **Notifications** model for system events (bookings, payments, logins, …)
- Health-check endpoint for the database
- Mobile API endpoints for check-in/check-out and housekeeping updates

---

## Tech Stack

| Layer | Technology |
|-------|------------|
| Backend | Python 3.12+, Django 6.0.6, Django REST Framework 3.17 |
| Auth | SimpleJWT (API), Django sessions (web), custom 2FA |
| Database | SQLite (default) / PostgreSQL (via `DB_ENGINE`) |
| API tooling | django-filter, drf-spectacular (OpenAPI), django-cors-headers |
| Payments | Paystack (requests-based) |
| Email/SMS | Brevo (custom Django email backend + transactional SMS) |
| Web frontend | Django templates, custom CSS design system, vanilla JS |
| Mobile | React Native 0.73, Expo 50, React Navigation |

---

## Project Structure

```
project/
├── apps/                        # Django apps (one per domain)
│   ├── accounts/                # Custom user model (Staff), roles, profile pictures
│   ├── billing/                 # Invoices, Payments, Paystack checkout/webhook
│   ├── common/                  # BranchScopedQuerysetMixin, MANAGER_ROLES
│   ├── feedback/                # Guest reviews (1–5 stars, one per stay)
│   ├── guests/                  # Walk-in guest records
│   ├── hotels/                  # Hotel properties (categories) + departments
│   ├── mobile/                  # API endpoints for the React Native app
│   ├── notifications/           # System notifications
│   ├── reservations/            # Reservations + RoomReservation (multi-room M2M)
│   ├── rooms/                   # RoomType, Room, Maintenance
│   └── services/                # Service catalogue + service requests
├── config/                      # Django project settings, URL routing, WSGI/ASGI
├── frontend/
│   ├── templates/frontend/      # All web pages (guest + staff)
│   ├── static/frontend/         # CSS design system, JS, fonts
│   ├── views.py                 # Web pages + booking/auth API handlers
│   └── email_backend.py         # Brevo transactional email backend
├── mobile-app/                  # React Native / Expo guest app
│   └── src/screens/             # Login, Home, Search, Bookings, Profile
├── manage.py
└── requirements.txt
```

---

## Prerequisites

- Python **3.12+**
- pip / virtualenv (or uv / poetry)
- Node.js + npm (only for the mobile app)
- Optional: Expo Go app or Android/iOS emulator for the mobile app

---

## Quick Start

### 1. Clone & set up the environment

```bash
git clone <repo-url>
cd project

# Create and activate a virtual environment
python -m venv venv
source venv/bin/activate        # Windows (Git Bash): source venv/Scripts/activate

# Install dependencies
pip install -r requirements.txt
```

### 2. Configure environment variables

Copy the values below into a `.env` file in the project root (see [Configuration](#configuration-environment-variables)). Nothing is required to get a basic local run going — sensible defaults are in place.

### 3. Migrate & seed

```bash
python manage.py migrate

# Optional: full demo dataset — 3 hotels, 18 staff, 15 guests, 42 rooms,
# 20 reservations, invoices, payments, services, feedback, maintenance, notifications
# (merge-safe: re-running updates existing rows and never deletes other data)
python manage.py seed_full_demo

# Legacy smaller seeds (optional, superseded by seed_full_demo)
# python manage.py seed_demo_data
# python manage.py seed_operations_data
# python manage.py create_sample_accounts
```

### 4. Create an admin (if you didn't use the sample accounts)

Visit `http://localhost:8000/admin-signup/` while no staff account exists — the **first account is automatically an admin**. If you already ran `create_sample_accounts`, sign in with `admin@stayhub.com` instead.

### 5. Run the server

```bash
python manage.py runserver
```

Open **http://localhost:8000/** — you'll be redirected through the splash → landing flow.

#### Sample staff accounts (`create_sample_accounts`)

| Role | Email | Password |
|------|-------|----------|
| Admin | `admin@stayhub.com` | `admin123456` |
| Manager | `manager@stayhub.com` | `manager123` |
| Receptionist | `reception@stayhub.com` | `reception123` |
| Accountant | `accountant@stayhub.com` | `accountant123` |
| Housekeeping | `housekeeping@stayhub.com` | `housekeeping123` |

> Change these passwords before any non-local deployment.

---

## Configuration (Environment Variables)

All settings are read from environment variables via `python-decouple` (put them in a `.env` file in the project root, which is git-ignored).

| Variable | Default | Purpose |
|----------|---------|---------|
| `DB_ENGINE` | `sqlite` | `postgres` (or `postgresql`) switches to PostgreSQL |
| `DB_NAME` / `DB_USER` / `DB_PASSWORD` / `DB_HOST` / `DB_PORT` | — | PostgreSQL connection (used when `DB_ENGINE=postgres`) |
| `PAYSTACK_PUBLIC_KEY` | `` | Paystack public key (frontend popup) |
| `PAYSTACK_SECRET_KEY` | `` | Paystack secret key (checkout init, webhook verification) |
| `PAYSTACK_RETURN_URL` | `http://localhost:8000/booking/` | Where Paystack sends the guest after payment |
| `BREVO_API_KEY` | `` | Brevo API key (transactional SMS + optional email) |
| `BREVO_SMS_SENDER` | `StayHub` | SMS sender name |
| `GOOGLE_OAUTH_CLIENT_ID` / `GOOGLE_OAUTH_CLIENT_SECRET` | `` | Google OAuth web-client credentials |
| `GOOGLE_OAUTH_REDIRECT_URI` | `http://localhost:8000/api/auth/google/callback/` | Must match Google Cloud exactly |
| `GOOGLE_OAUTH_REDIRECT_URIS` | same as above | Comma-separated list (multi-host support) |
| `ADMIN_SIGNUP_KEY` | `` | Required key to create additional admins (first admin is always allowed) |
| `EMAIL_BACKEND` | `console` (prints to terminal) | Set to `django.core.mail.backends.smtp.EmailBackend` to send real mail |
| `SMTP_HOST` / `SMTP_PORT` / `SMTP_USERNAME` / `SMTP_PASSWORD` / `SMTP_USE_TLS` | — | SMTP server settings |
| `DEFAULT_FROM_EMAIL` | `StayHub <no-reply@stayhub.local>` | From address for emails |
| `CSRF_TRUSTED_ORIGINS` | `http://localhost:8000,https://*.ngrok-free.dev` | Comma-separated trusted origins |

> ⚠️ **Never commit real keys.** A full integration walkthrough (Brevo, Google OAuth, Paystack) is in [`AUTH_AND_PAYMENTS_SETUP.md`](AUTH_AND_PAYMENTS_SETUP.md).

---

## Seed Data

| Command | What it creates |
|---------|-----------------|
| `python manage.py seed_full_demo` | **Full dataset (recommended):** 3 real Ghanaian hotels (Kempinski, Labadi Beach, Elmina Beach), 5 departments each, 18 staff across all roles & hotels, 15 guests, 11 room types, 42 rooms (mix of occupied/reserved/maintenance), 20 reservations (checked-in/confirmed/pending/checked-out/cancelled), room-reservations, 18 invoices, 11 payments (Cash/Card/Mobile Money/Paystack), 20 services, 16 service requests, feedback, 11 maintenance tasks, 15 notifications |
| `python manage.py seed_demo_data` | Legacy: 6 hotels, 3 departments per hotel, 8 room types, ~45 rooms |
| `python manage.py seed_operations_data` | Legacy: today's check-in / check-out / upcoming reservations, invoices, maintenance (run `seed_demo_data` first) |
| `python manage.py create_sample_accounts` | Legacy: one staff account per role (admin, manager, receptionist, accountant, housekeeping) |

All commands are merge-safe (`update_or_create` / `get_or_create`) and safe to re-run. Staff passwords set by the seeds: `admin123456` (admin), `manager123`, `reception123`, `accountant123`, `housekeeping123`.

---

## Staff Roles

| Role | Access |
|------|--------|
| `admin` | Everything: all dashboards, admin management, all branches |
| `manager` | Same as admin; branch-scoped only if assigned to a hotel (with a `?scope=all` toggle to see all) |
| `receptionist` | Receptionist dashboard, bookings; only their own hotel's data |
| `accountant` | Accountant dashboard (invoices/payments); only their own hotel's data |
| `housekeeping` | Housekeeping dashboard (rooms, maintenance); only their own hotel's data |
| `guest` | Public guest pages; cannot access staff pages |

Branch scoping is enforced by `BranchScopedQuerysetMixin` (in `apps/common/mixins.py`) across every API viewset, and by `_role_required` + per-view filtering on the web dashboards.

---

## Web Pages & Flow

The complete page map, navigation flow, and guard rules live in **[`PAGE_FLOW.md`](PAGE_FLOW.md)**. Quick overview:

- **Guest:** `/` (splash) → `/landing/` → `/signin/` or `/create-account/` → `/home/` → `/explore/?category=…&q=…` → `/hotel-details/?hotel=…` → `/booking/` → `/reservation-confirmed/`
- **Staff:** `/staff-login/` → role dashboard (`/manager/`, `/receptionist/`, `/accountant/`, `/housekeeping/`) + `/admin-management/` + `/staff-profile/`
- **Auth extras:** `/verification-method/` + `/verification/` (2FA), `/password-reset/`, Google OAuth via the sign-in pages
- Unauthorized staff roles get `access_denied.html`; guests who log in as staff are redirected to their dashboard and vice versa.

---

## REST API

Base paths are mounted in `config/urls.py` under `/api/…`. Most resources are full CRUD `ModelViewSet`s with django-filter support.

| Resource | Path | Notes |
|----------|------|-------|
| Token | `POST /api/token/`, `POST /api/token/refresh/` | SimpleJWT |
| Staff | `/api/accounts/staff/` | Role/hotel/department filters |
| Hotels | `/api/hotels/hotels/`, `/api/hotels/departments/` | |
| Rooms | `/api/rooms/rooms/`, `/api/rooms/room-types/`, `/api/rooms/maintenance/` | |
| Guests | `/api/guests/guests/` | Scoped via reservations for branch staff |
| Reservations | `/api/reservations/reservations/`, `/api/reservations/room-reservations/` | |
| Services | `/api/services/services/`, `/api/services/service-requests/` | |
| Billing | `/api/billing/invoices/`, `/api/billing/payments/` | |
| Feedback | `/api/feedback/feedback/` | |
| Mobile | `/api/mobile/rooms/`, `/api/mobile/checkin/`, `/api/mobile/checkout/`, `/api/mobile/housekeeping/update/` | For the RN app |
| Web helpers | `POST /api/auth/login/`, `POST /api/auth/register/`, `POST /api/auth/two-factor/verify/`, `GET /api/auth/google/`, `GET /api/auth/google/callback/`, `GET /api/booking/options/`, `POST /api/booking/create/`, `GET /api/reservations/<id>/status/`, `GET /api/health/database/` | Session-based (web) |

API docs: `drf-spectacular` is configured as the DRF default schema class. The OpenAPI schema is live at **`/api/schema/`** and Swagger UI at **`/api/schema/swagger-ui/`**.

---

## Payments (Paystack)

1. **Checkout init** — `POST /api/billing/paystack/checkout/` with `{"invoice_id": …}` returns an `authorization_url`.
2. **Webhook** — Paystack sends `charge.success` events to `/api/billing/paystack/webhook/`. The endpoint verifies the `x-paystack-signature` (HMAC-SHA512) before recording the payment, updating the invoice status (paid/partial) and confirming the reservation.
3. **Verification** — `GET /api/billing/paystack/verify/<reference>/` polls Paystack as a fallback when webhooks are delayed.

Invoices are auto-created at booking time with `(nightly rate × nights) + ₵45 service fee + 12% tax`. Partial payments are supported — an invoice becomes `PAID` only when the sum of payments covers `total_amount`.

---

## Mobile App

The `mobile-app/` directory is an Expo (React Native) app for guests.

```bash
cd mobile-app
npm install
npm start          # Expo dev server; scan the QR with Expo Go
# or: npm run android / npm run ios
```

It uses a stack navigator (Login → SignUp → Main) plus a bottom tab navigator (Home, Search, Bookings, Profile), and talks to the Django backend's `/api/mobile/` endpoints. Point the app at your backend by setting the API base URL in the screens (defaults assume a local Django server at `http://localhost:8000`).

---

## Running Tests

Each Django app has a `tests.py`, and there's a root-level integration test script:

```bash
python manage.py test               # run all app test suites
python manage.py test apps.accounts apps.billing apps.feedback apps.guests \
    apps.hotels apps.reservations apps.rooms apps.services   # or specific apps
python test_integration.py          # manual/integration smoke checks
```

---

## Deployment Notes

- **Debug off:** set `DEBUG=False` and a real `SECRET_KEY` before production.
- **Database:** set `DB_ENGINE=postgres` and the `DB_*` variables for PostgreSQL.
- **Email:** switch `EMAIL_BACKEND` to `django.core.mail.backends.smtp.EmailBackend` (with the `SMTP_*` vars) or to the bundled Brevo backend `frontend.email_backend.BrevoEmailBackend` (with `BREVO_API_KEY`), and configure `DEFAULT_FROM_EMAIL` with a verified sender.
- **Payments:** use Paystack **test keys** for development, live keys for production. Register the deployed webhook URL with Paystack and keep `PAYSTACK_RETURN_URL` pointing at the deployed booking page.
- **Google OAuth:** register the exact deployed callback URI in Google Cloud.
- **Static/media:** run `python manage.py collectstatic` and serve `STATIC_ROOT`; `MEDIA_ROOT` holds uploaded profile/hotel images.
- **Hosts:** `ALLOWED_HOSTS` defaults to `"*"` — tighten it and update `CSRF_TRUSTED_ORIGINS` for your domain (ngrok-friendly by default).

---

## Documentation

| File | Contents |
|------|----------|
| [`PAGE_FLOW.md`](PAGE_FLOW.md) | Full page map, navigation, guards, data model summary, design tokens |
| [`AUTH_AND_PAYMENTS_SETUP.md`](AUTH_AND_PAYMENTS_SETUP.md) | Step-by-step setup for Brevo (email/SMS), Google OAuth, and Paystack |
| [`task_checklist.md`](task_checklist.md) | Optimization plan / development checklist |
