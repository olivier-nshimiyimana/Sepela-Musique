import json
import logging
from urllib import error as urlerror
from urllib import request as urlrequest

from django.conf import settings
from django.core.mail.backends.base import BaseEmailBackend
from django.core.mail.backends.smtp import EmailBackend as DjangoSMTPEmailBackend
from django.core.mail.utils import DNS_NAME

logger = logging.getLogger(__name__)


class CompatEmailBackend(DjangoSMTPEmailBackend):
    """SMTP backend compatible with Python 3.13 starttls signature."""

    def open(self):
        if self.connection:
            return False

        connection_params = {"local_hostname": DNS_NAME.get_fqdn()}
        if self.timeout is not None:
            connection_params["timeout"] = self.timeout

        if self.use_ssl:
            connection_params.update(
                {
                    "keyfile": self.ssl_keyfile,
                    "certfile": self.ssl_certfile,
                }
            )

        try:
            try:
                self.connection = self.connection_class(
                    self.host, self.port, **connection_params
                )
            except TypeError:
                # Python 3.12+ drops keyfile/certfile kwargs.
                connection_params.pop("keyfile", None)
                connection_params.pop("certfile", None)
                self.connection = self.connection_class(
                    self.host, self.port, **connection_params
                )

            if not self.use_ssl and self.use_tls:
                try:
                    self.connection.starttls(
                        keyfile=self.ssl_keyfile, certfile=self.ssl_certfile
                    )
                except TypeError:
                    self.connection.starttls()

            if self.username and self.password:
                self.connection.login(self.username, self.password)
            return True
        except OSError:
            if not self.fail_silently:
                raise


class BrevoApiEmailBackend(BaseEmailBackend):
    """Send mail through Brevo HTTP API using BREVO_API_KEY."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.api_key = kwargs.get("api_key")

    def _as_recipients(self, message):
        recipients = []
        for email in message.recipients():
            if email and email not in recipients:
                recipients.append(email)
        return [{"email": email} for email in recipients]

    def _extract_html_content(self, message):
        for alternative, mimetype in getattr(message, "alternatives", []):
            if mimetype == "text/html":
                return alternative
        if message.content_subtype == "html":
            return message.body
        return None

    def _build_error_details(self, err):
        if isinstance(err, urlerror.HTTPError):
            try:
                body = err.read().decode("utf-8", errors="replace").strip()
            except Exception:
                body = ""
            if body:
                return "Brevo API HTTP %s: %s" % (err.code, body)
            return "Brevo API HTTP %s: %s" % (err.code, err.reason)
        return "Brevo API request failed: %s" % err

    def send_messages(self, email_messages):
        if not email_messages:
            return 0

        api_key = self.api_key or getattr(settings, "BREVO_API_KEY", "")
        timeout = getattr(settings, "EMAIL_TIMEOUT", 20)
        if not api_key:
            if self.fail_silently:
                return 0
            raise ValueError("BREVO_API_KEY is required for BrevoApiEmailBackend.")

        sent_count = 0
        endpoint = "https://api.brevo.com/v3/smtp/email"

        for message in email_messages:
            to_recipients = self._as_recipients(message)
            if not to_recipients:
                continue

            from_email = message.from_email or getattr(
                settings, "DEFAULT_FROM_EMAIL", ""
            )
            if not from_email:
                if self.fail_silently:
                    continue
                raise ValueError("Missing sender email address for Brevo API email.")

            payload = {
                "sender": {"email": from_email},
                "to": to_recipients,
                "subject": message.subject or "",
                "textContent": message.body or "",
            }

            html_content = self._extract_html_content(message)
            if html_content:
                payload["htmlContent"] = html_content

            if message.reply_to:
                payload["replyTo"] = {"email": message.reply_to[0]}

            request = urlrequest.Request(
                endpoint,
                data=json.dumps(payload).encode("utf-8"),
                headers={
                    "accept": "application/json",
                    "content-type": "application/json",
                    "api-key": api_key,
                },
                method="POST",
            )
            try:
                with urlrequest.urlopen(request, timeout=timeout) as response:
                    status_code = getattr(response, "status", response.getcode())
                    response_body = response.read().decode("utf-8", errors="replace")
                    if 200 <= status_code < 300:
                        message_id = ""
                        if response_body:
                            try:
                                message_id = json.loads(response_body).get("messageId", "")
                            except (TypeError, ValueError):
                                message_id = ""
                        logger.warning(
                            "Brevo email accepted status=%s message_id=%s to=%s subject=%s",
                            status_code,
                            message_id or "n/a",
                            ",".join([recipient["email"] for recipient in to_recipients]),
                            message.subject or "",
                        )
                        sent_count += 1
                    elif not self.fail_silently:
                        raise RuntimeError("Brevo API request failed with status %s." % status_code)
            except (urlerror.URLError, urlerror.HTTPError, ValueError, RuntimeError) as exc:
                if not self.fail_silently:
                    raise RuntimeError(self._build_error_details(exc)) from exc

        return sent_count
