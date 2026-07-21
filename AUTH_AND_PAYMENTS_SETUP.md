# Authentication and payments setup

## Email and SMS authentication

For real delivery, configure Brevo for email and SMS. Email verification still uses the existing mail path, while sign-in can now be sent by SMS when the user selects it.

`BREVO_API_KEY=your_brevo_api_key`

`BREVO_SMS_SENDER=StayHub`

Also set `DEFAULT_FROM_EMAIL` to a sender verified in Brevo. Never commit the key or provider passwords. If a provider credential has appeared in a debug page or source control, revoke and replace it.

## Google sign-in

Create a Google Cloud OAuth **Web application** client, then set the three `GOOGLE_OAUTH_*` values. Register the callback exactly as configured; locally it is:

`http://localhost:8000/api/auth/google/callback/`

For production, use the HTTPS deployed equivalent. Google requires the redirect URI to match exactly.

## Payments

Use your **Paystack test keys** for development. Add the public and secret keys through environment variables. The app now creates an invoice for each booking and exposes a server-side Paystack checkout plus webhook endpoint.

`PAYSTACK_PUBLIC_KEY=your_paystack_public_key`

`PAYSTACK_SECRET_KEY=your_paystack_secret_key`

`PAYSTACK_RETURN_URL=http://localhost:8000/booking/`
