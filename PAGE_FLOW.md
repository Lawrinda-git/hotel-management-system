# StayHub Page Flow & Navigation Map

## Guest Flow (Not Logged In)

```
splash/ (/) 
    ├── landing/
    │       ├── signin/
    │       │       ├── [Login Success] → guest_home/
    │       │       └── [Staff Login Link] → staff-login/
    │       │               ├── [First Admin] → admin-signup/
    │       │               │       └── [Create Admin] → staff-login/
    │       │               └── [Login Success] → manager_dashboard/ (admin/manager)
    │       │                                       ├── receptionist_dashboard/ (receptionist)
    │       │                                       ├── accountant_dashboard/ (accountant)
    │       │                                       └── housekeeping_dashboard/ (housekeeping)
    │       │
    │       └── create-account/
    │               └── [Register Success] → signin/
    │
    ├── team/
    └── explore/ (with category filters)
            ├── hotel-details/?hotel=1 → booking/
            └── hotel-details/?hotel=2 → booking/
                                └── [Confirm Booking] → reservation-confirmed/
                                └── [Paystack] → reservation-confirmed/?paid=1

Password Reset Flow:
    signin/ → [Forgot Password] → password-reset/
        └── [Enter Email] → password-reset/done/
            └── [Check Email] → reset/<uidb64>/<token>/
                └── [New Password] → reset/done/
```

## Staff Flow (Logged In)

```
staff-login/
    └── [Login Success - Role Based]
        ├── admin → manager_dashboard/
        │           ├── booking/ (New Booking)
        │           ├── admin-management/
        │           │       ├── tab: Rooms
        │           │       ├── tab: Employees
        │           │       ├── tab: Hotels & Resorts (with category filter)
        │       │       │               ├── All/Resort/Hotel/Cabin/Villa/etc.
        │       │       │               └── [Hotel Card] → Edit Hotel
        │       │       └── tab: Maintenance
        │       ├── profile/ (staff_profile.html)
        │       │       ├── Edit Profile
        │       │       ├── Change Password → password-reset/
        │       │       └── Sign Out → staff-login/
        │       └── [Bottom Nav]
        │
        ├── manager → manager_dashboard/
        │           └── (Same navigation as admin)
        │
        ├── receptionist → receptionist_dashboard/
        │           ├── booking/ (With "Find Guest" & "New Walk-in" actions)
        │           ├── explore/ (Redirects to dashboard if staff)
        │       │   ├── hotel-details/ (Redirects to dashboard if staff)
        │       │   └── guest_home/ (Redirects to dashboard if staff)
        │       ├── profile/ (staff_profile.html)
        │       └── [Bottom Nav]
        │
        ├── accountant → accountant_dashboard/
        │           ├── booking/
        │       │   ├── explore/ (Redirects to dashboard if staff)
        │       │   ├── hotel-details/ (Redirects to dashboard if staff)
        │       │   └── guest_home/ (Redirects to dashboard if staff)
        │       ├── profile/ (staff_profile.html)
        │       └── [Bottom Nav]
        │
        └── housekeeping → housekeeping_dashboard/
                    ├── booking/
                │   ├── explore/ (Redirects to dashboard if staff)
                │   ├── hotel-details/ (Redirects to dashboard if staff)
                │   ├── guest_home/ (Redirects to dashboard if staff)
                │   ├── profile/ (staff_profile.html)
                │   └── [Bottom Nav]
```

## Detailed Page List

### Public Pages (Guests)
| URL | Template | Purpose |
|-----|----------|---------|
| `/` or `/splash/` | `splash.html` | Landing splash screen |
| `/landing/` | `landing.html` | Hero page with sign-in/explore |
| `/signin/` | `signin.html` | Guest sign-in |
| `/create-account/` | `create_account.html` | Guest registration |
| `/home/` | `guest_home.html` | Guest home after login |
| `/explore/` | `explore_stays.html` | Browse hotels with category filters |
| `/hotel-details/` | `hotel_details.html` | Hotel details + book button |
| `/booking/` | `booking.html` | Multi-step booking process |
| `/reservation-confirmed/` | `reservation_confirmed.html` | Booking success + Paystack |
| `/team/` | `team.html` | About StayHub team |

### Password Reset Pages
| URL | Template | Purpose |
|-----|----------|---------|
| `/password-reset/` | `password_reset.html` | Enter email for reset |
| `/password-reset/done/` | `password_reset_done.html` | Check email confirmation |
| `/reset/<uidb64>/<token>/` | `password_reset_confirm.html` | Enter new password |
| `/reset/done/` | `password_reset_complete.html` | Password updated success |

### Staff Authentication
| URL | Template | Purpose |
|-----|----------|---------|
| `/staff-login/` | `staff_login.html` | Staff portal login |
| `/admin-signup/` | `admin_signup.html` | Create first admin account |

### Staff Dashboards
| URL | Template | Role Access | Key Features |
|-----|----------|-------------|--------------|
| `/manager/` | `manager_dashboard.html` | admin, manager | KPIs, reservations table, maintenance |
| `/receptionist/` | `receptionist_dashboard.html` | receptionist | Check-ins/outs, room grid, bookings |
| `/accountant/` | `accountant_dashboard.html` | accountant | Invoices, payments, financial overview |
| `/housekeeping/` | `housekeeping_dashboard.html` | housekeeping | Dirty/clean rooms, tasks, inspection |
| `/admin-management/` | `admin_management.html` | admin, manager | Tabbed: Rooms, Employees, Hotels, Maintenance |
| `/staff-profile/` | `staff_profile.html` | all staff | Edit profile, picture, password |

## Navigation Structure

### Guest Bottom Navigation (on public pages)
```
[Home] [Explore] [Bookings] [Profile]
```
- Home → `/home/`
- Explore → `/explore/`
- Bookings → (shows guest bookings if logged in)
- Profile → `/profile/` or login prompt

### Staff Bottom Navigation (on all dashboard pages)
```
[Dashboard] [Bookings] [Manage/Explore] [Profile]
```
- Dashboard → Role-specific dashboard
- Bookings → `/booking/`
- Manage (admin/manager) → `/admin-management/`
- Explore (other roles) → `/booking/`
- Profile → `/staff-profile/`

### Staff Top Navigation (all dashboard pages)
- Back arrow to dashboard
- App logo + role label
- Profile icon → `/staff-profile/`
- Logout icon → `/logout/` → redirects to `/staff-login/`

## Guards & Redirects

### Staff Protection
- All `/manager/`, `/receptionist/`, `/accountant/`, `/housekeeping/`, `/admin-management/`, `/staff-profile/` URLs require login
- Unauthorized roles → `access_denied.html`
- Not logged in → `staff-login/`

### Guest Protection
- Staff pages redirect to role-specific dashboard if accessed by staff
- `/home/`, `/explore/`, `/hotel-details/` redirect staff to dashboards

### Logout Behavior
- Staff → `/staff-login/`
- Guest → `/signin/`

## Category Filter Flow

```
/explore/ (All)
    ├── Filter: RESORT → /explore/?category=RESORT
    ├── Filter: HOTEL → /explore/?category=HOTEL
    ├── Filter: CABIN → /explore/?category=CABIN
    ├── Filter: VILLA → /explore/?category=VILLA
    ├── Filter: APARTMENT → /explore/?category=APARTMENT
    ├── Filter: HOMESTAY → /explore/?category=HOMESTAY
    └── Filter: GUEST_HOUSE → /explore/?category=GUEST_HOUSE

/hotel-details/ shows:
    - Category badge (e.g., "RESORT")
    - Category-specific booking button ("Book This Resort")
```

## Admin Management Tabs

```
/admin-management/
    ├── [Rooms] Tab
    │   ├── Room table with status badges
    │   ├── Add Room button (coming soon)
    │   ├── Edit button per room (coming soon)
    │   └── Delete button per room (coming soon)
    │
    ├── [Employees] Tab
    │   ├── Staff table with role badges
    │   ├── Add Employee button (coming soon)
    │   ├── Edit button per employee (coming soon)
    │   └── Remove button (not for admin)
    │
    ├── [Hotels & Resorts] Tab
    │   ├── Category filter chips (All, Resort, Hotel, Cabin, Villa, etc.)
    │   ├── Hotel cards with images
    │   ├── Category badge on each card
    │   └── Add Property button (coming soon)
    │
    └── [Maintenance] Tab
        ├── Open maintenance tasks
        └── Status badges (OPEN, IN_PROGRESS, etc.)
```

## Booking Flow (Staff vs Guest)

### Guest Booking Flow
```
/booking/
    ├── Step 1: Select Dates
    ├── Step 2: Choose Room (from available rooms)
    ├── Step 3: Guest Details (name, email, phone, ID)
    └── Step 4: Confirm & Pay (Paystack)
        └── /reservation-confirmed/ (success)
```

### Staff Booking Flow (Receptionist)
```
/booking/
    ├── [Find Guest] button (search by email/phone) ← NEW
    ├── [New Walk-in] button ← NEW
    ├── Step 1: Select Dates
    ├── Step 2: Choose Room
    ├── Step 3: Guest Details (pre-filled for walk-in)
    └── Step 4: Confirm & Pay
        └── /reservation-confirmed/
```

## Data Models & Relationships

```
Hotel (category: RESORT/HOTEL/CABIN/etc.)
    ├── image: hotel_image
    ├── hotel_name
    ├── hotel_address
    └── hotel_phone
         │
         ├── Room (many rooms per hotel)
         │   ├── room_number (unique per hotel)
         │   ├── room_type (FK to RoomType)
         │   ├── status: AVAILABLE/OCCUPIED/RESERVED/MAINTENANCE
         │   ├── housekeeping_status: DIRTY/CLEAN/INSPECTED
         │   └── reservation (FK to Reservation)
         │
         ├── Reservation (many per hotel)
         │   ├── guest (FK to Guest)
         │   ├── check_in / check_out
         │   ├── actual_check_in / actual_check_out
         │   ├── status: PENDING/CONFIRMED/CHECKED_IN/etc.
         │   └── invoice (1:1 to Invoice)
         │
         └── Department (many per hotel)
             └── dept_name

Guest
    ├── guest_name
    ├── guest_email (unique)
    ├── guest_phone
    ├── id_number (unique)
    └── nationality

Invoice (1 per reservation)
    ├── reservation (FK)
    ├── total_amount
    ├── status: UNPAID/PARTIAL/PAID/VOID
    └── payments (many)
        ├── amount
        ├── method: CASH/CARD/MOBILE_MONEY/BANK_TRANSFER/PAYSTACK
        ├── status: PENDING/SUCCESS/FAILED
        └── provider_reference

Staff (User model)
    ├── username (email)
    ├── email
    ├── role: admin/manager/receptionist/accountant/housekeeping/guest
    ├── staff_name
    ├── staff_phone
    ├── profile_picture
    └── hotel (FK - assigned hotel for branch staff)
```

## URL Map Summary

| URL Pattern | View | Access |
|-------------|------|--------|
| `/` | `splash` | Public |
| `/landing/` | `landing` | Public |
| `/signin/` | `signin` | Public |
| `/create-account/` | `create_account` | Public |
| `/home/` | `guest_home` | Guest/Staff redirect |
| `/explore/` | `explore_stays` | Public (staff redirect) |
| `/hotel-details/` | `hotel_details` | Public (staff redirect) |
| `/booking/` | `booking` | All |
| `/reservation-confirmed/` | `reservation_confirmed` | All |
| `/staff-login/` | `staff_login` | Public |
| `/admin-signup/` | `admin_signup` | Public (first admin only) |
| `/logout/` | `logout_view` | Authenticated |
| `/profile/` | `profile` | Guest |
| `/staff-profile/` | `profile` | Staff |
| `/manager/` | `manager_dashboard` | Admin/Manager |
| `/receptionist/` | `receptionist_dashboard` | Receptionist |
| `/accountant/` | `accountant_dashboard` | Accountant |
| `/housekeeping/` | `housekeeping_dashboard` | Housekeeping |
| `/admin-management/` | `admin_management` | Admin/Manager |
| `/password-reset/` | PasswordResetView | Public |
| `/password-reset/done/` | PasswordResetDoneView | Public |
| `/reset/<uidb64>/<token>/` | PasswordResetConfirmView | Public |
| `/reset/done/` | PasswordResetCompleteView | Public |
| `/team/` | `team` | Public |
| `/api/health/database/` | `database_health` | Public |

## API Endpoints

| URL | Method | Purpose |
|-----|--------|---------|
| `/api/auth/login/` | POST | Staff/Guest login |
| `/api/auth/register/` | POST | Guest registration |
| `/api/auth/two-factor/verify/` | POST | 2FA verification |
| `/api/auth/google/` | GET | Google OAuth start |
| `/api/auth/google/callback/` | GET | Google OAuth callback |
| `/api/booking/options/` | GET | Get available rooms |
| `/api/booking/create/` | POST | Create booking |
| `/api/reservations/<id>/status/` | GET | Reservation status |
| `/api/health/database/` | GET | Health check |

## Hotel Categories

| Code | Label | Example Use |
|------|-------|-------------|
| RESORT | Resort | La Palm Royal Beach Hotel |
| HOTEL | Hotel | Kempinski Hotel Gold Coast City |
| CABIN | Cabin | Mountain cabin |
| VILLA | Villa | Private villa |
| APARTMENT | Apartment | Serviced apartment |
| HOMESTAY | Homestay | Local homestay |
| GUEST_HOUSE | Guest House | Budget guest house |
| OTHER | Other | Miscellaneous |

## Template Structure

```
frontend/templates/frontend/
├── base.html (design system, colors, utilities)
├── splash.html
├── landing.html
├── signin.html
├── staff_login.html
├── admin_signup.html
├── create_account.html
├── guest_home.html
├── explore_stays.html (category filters)
├── hotel_details.html (category display)
├── booking.html (staff quick actions)
├── reservation_confirmed.html
├── profile.html (guest profile)
├── staff_profile.html (staff profile)
├── manager_dashboard.html
├── receptionist_dashboard.html
├── accountant_dashboard.html
├── housekeeping_dashboard.html
├── admin_management.html (tabbed interface)
├── team.html
├── access_denied.html
├── password_reset.html
├── password_reset_email.html
├── password_reset_confirm.html
├── password_reset_done.html
├── password_reset_complete.html
├── verification.html
├── verification_method.html
└── components/
    └── _guest_nav.html
```

## Color System (Material Design 3)

```
Primary: #1976D2 (Blue)
Primary Container: #C5CAE9
Secondary: #03DAC6 (Teal)
Secondary Container: #B2DFDB
Surface: #FFFFFF
Surface Container: #F5F5F5
Surface Container Lowest: #FAFAFA
Background: #FAFAFA
Error: #B00020
Error Container: #F9DEDC
On Primary: #FFFFFF
On Surface: #1C1B1F
On Surface Variant: #49454F
Outline: #79747E
Outline Variant: #CAC4D0
```

## Button Styles

| Class | Style | Use |
|-------|-------|-----|
| `btn-primary` | Filled primary blue | Primary actions |
| `btn-secondary` | Filled secondary teal | Secondary actions |
| `btn-outline` | Outlined | Secondary actions |
| `btn-ghost` | Transparent | Tertiary actions |
| `btn-sm` | Small size | Compact UI |
| `btn-lg` | Large size | Hero actions |
| `btn-icon` | Icon-only circles | Header actions |

## Status Badges

| Status | Badge Class | Color |
|--------|-------------|-------|
| Available | `badge-success` | Green |
| Occupied/Reserved | `badge-primary` | Blue |
| Maintenance | `badge-error` | Red |
| Pending | `badge-warning` | Amber |
| Paid | `badge-success` | Green |
| Unpaid | `badge-warning` | Amber |
| Partial | `badge-primary` | Blue |
| Admin | `badge-primary` | Blue |
| Manager | `badge-success` | Green |
| Receptionist | `badge-outline` | Gray |
| Accountant | `badge-secondary` | Teal |
| Housekeeping | `badge-warning` | Amber |