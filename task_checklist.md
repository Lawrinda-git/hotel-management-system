# Full Optimization Plan

## Phase 1: New Landing Page
- [x] Create `landing.html` with the hero design (between splash and signin)
- [x] Add `landing` view in views.py
- [x] Add `landing` URL in urls.py
- [x] Update splash auto-redirect to go to landing instead of signin

## Phase 2: Fix Guest Home Page
- [x] Add hotel ID params to hotel detail links (differentiate La Palm, Kempinski, Royal Senchi)
- [x] Add category filter params to category links
- [x] Replace "View all" link with dropdown menu
- [x] Make search bar functional (navigate with query param)

## Phase 3: Fix Views
- [x] Update `hotel_details` view to accept hotel ID param
- [x] Update `explore_stays` view to accept category and search params

## Phase 4: Fix Bottom Nav on Mobile
- [x] Fix explore_stays.html bottom nav (solid bg, consistent with guest_home)
- [x] Fix booking.html bottom nav (add if missing)
- [x] Fix profile.html bottom nav (add if missing)