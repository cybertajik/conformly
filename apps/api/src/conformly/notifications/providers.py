import hashlib
import hmac
import json
import smtplib
import time
from email.message import EmailMessage

import httpx
import structlog

from conformly.config import Settings, get_settings
from conformly.notifications.worker import NotificationDeliveryError, NotificationProvider

logger = structlog.get_logger(__name__)


def _format_notification_content(kind: str, payload: dict[str, str]) -> tuple[str, str]:
    """Deterministically format email subject and plain-text body based on event kind."""
    if kind == "membership_invitation":
        tenant_name = payload.get("tenant_name", "Conformly")
        role = payload.get("role", "Member")
        token = payload.get("invitation_token", "")
        subject = f"You've been invited to join {tenant_name} on Conformly"
        body = (
            f"Hello,\n\n"
            f"You have been invited to join {tenant_name} on the Conformly compliance platform with role: {role}.\n\n"
            f"Invitation Code: {token}\n\n"
            f"Please accept your invitation through the Conformly portal.\n\n"
            f"Best regards,\n"
            f"The Conformly Team"
        )
        return subject, body

    if kind == "compliance_task_reminder":
        title = payload.get("task_title", "Compliance Task")
        due_date = payload.get("due_date", "Soon")
        subject = f"Reminder: Compliance Task Due — {title}"
        body = (
            f"Hello,\n\n"
            f"This is an automated reminder that your compliance task is due.\n\n"
            f"Task: {title}\n"
            f"Due Date: {due_date}\n\n"
            f"Please review and update the task status in your Conformly workspace.\n\n"
            f"Best regards,\n"
            f"Conformly Compliance Engine"
        )
        return subject, body

    if kind == "compliance_task_escalation":
        title = payload.get("task_title", "Compliance Task")
        days_overdue = payload.get("days_overdue", "overdue")
        subject = f"URGENT: Compliance Task Overdue Escalation — {title}"
        body = (
            f"Urgent Notice,\n\n"
            f"The following compliance task has been escalated as it is {days_overdue} days overdue:\n\n"
            f"Task: {title}\n\n"
            f"Immediate remediation or status review is required.\n\n"
            f"Best regards,\n"
            f"Conformly Compliance Engine"
        )
        return subject, body

    if kind == "policy_review_reminder":
        title = payload.get("policy_title", "Policy Document")
        subject = f"Action Required: Periodic Policy Review — {title}"
        body = (
            f"Hello,\n\n"
            f"The policy document '{title}' is scheduled for periodic compliance review.\n\n"
            f"Please inspect and initiate a new policy revision if updates are required.\n\n"
            f"Best regards,\n"
            f"Conformly Compliance Engine"
        )
        return subject, body

    if kind == "evidence_expiration_alert":
        title = payload.get("evidence_title", "Evidence Item")
        subject = f"Notice: Evidence Validity Expiring — {title}"
        body = (
            f"Hello,\n\n"
            f"The compliance evidence item '{title}' is approaching its validity expiration date.\n\n"
            f"Please upload renewed evidence to maintain control audit-readiness.\n\n"
            f"Best regards,\n"
            f"Conformly Compliance Engine"
        )
        return subject, body

    if kind == "continuous_compliance_alert":
        subject = payload.get("subject", "Conformly Continuous Compliance Alert")
        body = payload.get(
            "body", payload.get("message", "Continuous compliance posture check completed.")
        )
        return subject, body

    # Generic fallback
    subject = payload.get("subject", f"Conformly Notification: {kind.replace('_', ' ').title()}")
    body = payload.get("body", payload.get("message", json.dumps(payload, indent=2)))
    return subject, body


class SmtpNotificationProvider:
    """Production SMTP delivery provider supporting standard RFC 5322 MIME messages."""

    def __init__(
        self,
        *,
        host: str = "localhost",
        port: int = 1025,
        from_email: str = "no-reply@conformly.de",
        username: str | None = None,
        password: str | None = None,
        use_tls: bool = False,
        timeout: float = 10.0,
    ) -> None:
        self.host = host
        self.port = port
        self.from_email = from_email
        self.username = username
        self.password = password
        self.use_tls = use_tls
        self.timeout = timeout

    def deliver(
        self,
        *,
        kind: str,
        payload: dict[str, str],
        idempotency_key: str,
    ) -> None:
        recipient = payload.get("recipient_email") or payload.get("email")
        if not recipient or "@" not in recipient:
            raise NotificationDeliveryError("invalid_recipient_email", retryable=False)

        subject, body = _format_notification_content(kind, payload)

        msg = EmailMessage()
        msg["From"] = self.from_email
        msg["To"] = recipient
        msg["Subject"] = subject
        msg["X-Conformly-Kind"] = kind
        msg["X-Conformly-Idempotency-Key"] = idempotency_key
        msg.set_content(body)

        try:
            with smtplib.SMTP(self.host, self.port, timeout=self.timeout) as smtp:
                if self.use_tls:
                    smtp.starttls()
                if self.username and self.password:
                    smtp.login(self.username, self.password)
                smtp.send_message(msg)
            logger.info(
                "smtp_notification_sent",
                kind=kind,
                recipient=recipient,
                idempotency_key=idempotency_key,
            )
        except smtplib.SMTPRecipientsRefused as exc:
            raise NotificationDeliveryError("recipient_refused", retryable=False) from exc
        except smtplib.SMTPAuthenticationError as exc:
            raise NotificationDeliveryError("smtp_auth_failed", retryable=False) from exc
        except (smtplib.SMTPServerDisconnected, TimeoutError, OSError, ConnectionError) as exc:
            raise NotificationDeliveryError("smtp_connection_failed", retryable=True) from exc
        except smtplib.SMTPException as exc:
            raise NotificationDeliveryError("smtp_protocol_error", retryable=True) from exc


class WebhookNotificationProvider:
    """Outbox webhook delivery provider with HMAC-SHA256 replay-protected signing."""

    def __init__(
        self,
        *,
        secret: str = "conformly-webhook-secret",
        timeout: float = 10.0,
    ) -> None:
        self.secret = secret.encode("utf-8")
        self.timeout = timeout

    def deliver(
        self,
        *,
        kind: str,
        payload: dict[str, str],
        idempotency_key: str,
    ) -> None:
        target_url = payload.get("webhook_url") or payload.get("target_url")
        if not target_url or not target_url.startswith(("http://", "https://")):
            raise NotificationDeliveryError("invalid_webhook_url", retryable=False)

        timestamp_str = str(int(time.time()))
        body_bytes = json.dumps(
            {
                "kind": kind,
                "idempotency_key": idempotency_key,
                "payload": payload,
                "timestamp": timestamp_str,
            },
            sort_keys=True,
        ).encode("utf-8")

        signature = hmac.new(self.secret, body_bytes, hashlib.sha256).hexdigest()
        headers = {
            "Content-Type": "application/json",
            "X-Conformly-Signature": f"sha256={signature}",
            "X-Conformly-Timestamp": timestamp_str,
            "X-Conformly-Idempotency-Key": idempotency_key,
        }

        try:
            with httpx.Client(timeout=self.timeout) as client:
                response = client.post(target_url, content=body_bytes, headers=headers)
                if response.status_code >= 500 or response.status_code == 429:
                    raise NotificationDeliveryError(f"http_{response.status_code}", retryable=True)
                if response.status_code >= 400:
                    raise NotificationDeliveryError(f"http_{response.status_code}", retryable=False)
        except (httpx.TimeoutException, httpx.NetworkError) as exc:
            raise NotificationDeliveryError("webhook_network_error", retryable=True) from exc
        except NotificationDeliveryError:
            raise
        except Exception as exc:
            raise NotificationDeliveryError("webhook_unknown_error", retryable=True) from exc


class LoggingNotificationProvider:
    """Mock notification provider recording deliveries to structured log for testing/dev."""

    def __init__(self) -> None:
        self.deliveries: list[dict[str, str]] = []

    def deliver(
        self,
        *,
        kind: str,
        payload: dict[str, str],
        idempotency_key: str,
    ) -> None:
        self.deliveries.append({"kind": kind, "idempotency_key": idempotency_key, **payload})
        logger.info(
            "logging_notification_delivered",
            kind=kind,
            idempotency_key=idempotency_key,
            recipient=payload.get("recipient_email", payload.get("email", "unknown")),
        )


class CompositeNotificationProvider:
    """Intelligently routes notifications to SMTP, Webhook, or Logging based on destination."""

    def __init__(
        self,
        *,
        smtp_provider: SmtpNotificationProvider | None = None,
        webhook_provider: WebhookNotificationProvider | None = None,
        fallback_provider: LoggingNotificationProvider | None = None,
    ) -> None:
        self.smtp_provider = smtp_provider
        self.webhook_provider = webhook_provider
        self.fallback_provider = fallback_provider or LoggingNotificationProvider()

    def deliver(
        self,
        *,
        kind: str,
        payload: dict[str, str],
        idempotency_key: str,
    ) -> None:
        if payload.get("webhook_url") or payload.get("target_url"):
            if self.webhook_provider is not None:
                self.webhook_provider.deliver(
                    kind=kind, payload=payload, idempotency_key=idempotency_key
                )
                return
        if (
            payload.get("recipient_email") or payload.get("email")
        ) and self.smtp_provider is not None:
            self.smtp_provider.deliver(kind=kind, payload=payload, idempotency_key=idempotency_key)
            return
        self.fallback_provider.deliver(kind=kind, payload=payload, idempotency_key=idempotency_key)


def get_notification_provider(settings: Settings | None = None) -> NotificationProvider:
    """Factory creating the appropriate configured notification provider."""
    cfg = settings or get_settings()
    provider_type = cfg.notification_provider.lower().strip()

    smtp_provider = SmtpNotificationProvider(
        host=cfg.smtp_host,
        port=cfg.smtp_port,
        from_email=cfg.smtp_from_email,
        username=cfg.smtp_username,
        password=cfg.smtp_password,
        use_tls=cfg.smtp_use_tls,
    )
    webhook_provider = WebhookNotificationProvider(
        secret=cfg.invitation_token_pepper or "conformly-default-webhook-secret",
        timeout=cfg.webhook_timeout_seconds,
    )
    logging_provider = LoggingNotificationProvider()

    if provider_type == "logging":
        return logging_provider
    if provider_type == "webhook":
        return webhook_provider

    # Default: composite provider with SMTP as primary for emails and Webhook for URLs
    return CompositeNotificationProvider(
        smtp_provider=smtp_provider,
        webhook_provider=webhook_provider,
        fallback_provider=logging_provider,
    )
