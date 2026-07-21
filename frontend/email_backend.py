import json
from email.utils import parseaddr
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from django.conf import settings
from django.core.mail.backends.base import BaseEmailBackend
from django.core.mail.message import sanitize_address
from smtplib import SMTPException


class BrevoEmailBackend(BaseEmailBackend):
    """Send Django email messages through Brevo's transactional API."""

    api_url = "https://api.brevo.com/v3/smtp/email"

    def send_messages(self, email_messages):
        if not email_messages:
            return 0
        if not settings.BREVO_API_KEY:
            raise SMTPException("BREVO_API_KEY is not configured")
        sent = 0
        for message in email_messages:
            if self._send(message):
                sent += 1
        return sent

    def _send(self, message):
        sender_name, sender_email = parseaddr(message.from_email or settings.DEFAULT_FROM_EMAIL)
        sender_email = sanitize_address(sender_email, message.encoding or "utf-8")
        recipients = [sanitize_address(address, message.encoding or "utf-8") for address in message.to]
        payload = {
            "sender": {"name": sender_name or "StayHub", "email": sender_email},
            "to": [{"email": address} for address in recipients],
            "subject": message.subject,
            "textContent": message.body,
        }
        html_alternatives = [body for mimetype, body in message.alternatives if mimetype == "text/html"]
        if html_alternatives:
            payload["htmlContent"] = html_alternatives[-1]
        request = Request(
            self.api_url,
            data=json.dumps(payload).encode("utf-8"),
            headers={"accept": "application/json", "api-key": settings.BREVO_API_KEY, "content-type": "application/json"},
            method="POST",
        )
        try:
            with urlopen(request, timeout=15) as response:
                if response.status >= 300:
                    raise SMTPException(f"Brevo API returned HTTP {response.status}")
        except (HTTPError, URLError, OSError) as exc:
            raise SMTPException(f"Brevo email delivery failed: {exc}") from exc
        return True
