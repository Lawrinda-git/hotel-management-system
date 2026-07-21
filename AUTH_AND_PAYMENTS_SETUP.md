# Authentication and payments setup

## Email authentication and two-step verification

For real delivery, configure either SMTP or Brevo's transactional API. The API path is preferred when `BREVO_API_KEY` is present:

`BREVO_API_KEY=your_brevo_api_key`

Also set `DEFAULT_FROM_EMAIL` to a sender verified in Brevo. Never commit the key or provider passwords. If a provider credential has appeared in a debug page or source control, revoke and replace it.

## Google sign-in

Create a Google Cloud OAuth **Web application** client, then set the three `GOOGLE_OAUTH_*` values. Register the callback exactly as configured; locally it is:

`http://localhost:8000/api/auth/google/callback/`

For production, use the HTTPS deployed equivalent. Google requires the redirect URI to match exactly.

## Temporary payments recommendation

Use a **Stripe Sandbox** first. It lets you test card and other payment flows without moving real money. Once it is selected, add its publishable and secret sandbox keys through environment variables, then implement a server-created PaymentIntent and webhook before showing a payment form.

PayPal Sandbox is also suitable if the project specifically needs a PayPal wallet checkout. It supplies fictitious buyer and business accounts, but should not be used with real customer details.
