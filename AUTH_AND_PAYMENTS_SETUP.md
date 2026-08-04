# Authentication and payments setup

## Email and SMS authentication

For real delivery, configure **Brevo** for email and SMS. The two-factor (2FA)
verification code is sent through the channel the user picks:

- **Email** — sent with Django's `send_mail`, so it follows `EMAIL_BACKEND`.
  Point it at the bundled Brevo backend (`frontend.email_backend.BrevoEmailBackend`,
  POSTs to `https://api.brevo.com/v3/smtp/email`) or an SMTP backend in production.
- **SMS** — POSTs to `https://api.brevo.com/v3/transactionalSMS/send`.

Set these:

```
BREVO_API_KEY=your_brevo_api_key
BREVO_SMS_SENDER=StayHub
```

Also set `DEFAULT_FROM_EMAIL` to a sender verified in Brevo (the Brevo backend
parses the display name + address from it). Never commit the key or provider
passwords. If a provider credential has appeared in a debug page or source
control, revoke and replace it.

## Google sign-in

Create a Google Cloud OAuth **Web application** client, then set the
`GOOGLE_OAUTH_*` values:

```
GOOGLE_OAUTH_CLIENT_ID=...
GOOGLE_OAUTH_CLIENT_SECRET=...
GOOGLE_OAUTH_REDIRECT_URI=http://localhost:8000/api/auth/google/callback/
GOOGLE_OAUTH_REDIRECT_URIS=http://localhost:8000/api/auth/google/callback/,https://npc0sh6x-8000.euw.devtunnels.ms/api/auth/google/callback/
```

Register the callback **exactly** as configured in Google Cloud — Google requires
an exact match. The view picks the callback whose host matches the current
request, so `GOOGLE_OAUTH_REDIRECT_URIS` (comma-separated) lets you support
local, the dev tunnel, and the production domain at once. The callback verifies
the `state` token and the ID token's audience/issuer/email, then logs in the
guest (or the matching staff account when the staff-login flow was used).

## Payments (Paystack)

Use your **Paystack test keys** for development. The app creates an invoice for
every booking and uses a **server-side** checkout (redirect) — there is no
client-side popup:

```
PAYSTACK_SECRET_KEY=your_paystack_secret_key
# PAYSTACK_PUBLIC_KEY is accepted for compatibility but is not used by the
# server-side checkout, so it can be left empty.
# PAYSTACK_RETURN_URL is a legacy default; the app builds the callback URL from
# the incoming request instead (the booking page, or /staff/walkin/ for walk-ins).
```

### Checkout flow

1. **Create the booking** — `POST /api/booking/create/` returns the new
   `invoice.id`.
2. **Initialize checkout** — `POST /api/billing/paystack/checkout/` with
   `{"invoice_id": …}` returns an `authorization_url` to redirect the guest to.
   - Standard bookings: the callback returns to `/booking/`.
   - **Walk-in bookings (mobile money only):** pass
     `payment_method: "mobile_money"` plus `mobile_money_phone`
     (e.g. `+233241234567`), `mobile_money_provider` (`mtn`, `vodafone`, or
     `atl`), and `callback_url_name: "walkin_booking"`. The charge is then
     restricted to **Ghana mobile money** (`channels: ["mobile_money"]`,
     `currency: GHS`) and pushed to the client's number for them to confirm.
3. **Webhook** — register
   `https://npc0sh6x-8000.euw.devtunnels.ms/api/billing/paystack/webhook/`
   in your Paystack dashboard (Settings → Webhooks → Add webhook). The
   endpoint verifies the `x-paystack-signature` (HMAC-SHA512 over the raw
   body) before recording the payment, updating the invoice status (paid/
   partial), and confirming the reservation.
4. **Verification fallback** — `GET /api/billing/paystack/verify/<reference>/`
   polls Paystack when webhooks are delayed; on success it records the payment,
   marks the invoice `PAID`, and confirms the reservation.