"""Delivery service: send a generated report through a configured channel."""

import shutil
from abc import ABC, abstractmethod
from email.message import EmailMessage
from pathlib import Path
from smtplib import SMTP
from typing import Optional, Tuple

from pydantic import ValidationError

from reportmaker.shared.config import get_env, load_yaml_config
from reportmaker.shared.file_utils import ensure_directory
from reportmaker.shared.logging import get_logger
from reportmaker.features.delivery.exceptions import DeliveryError, EmailDeliveryError
from reportmaker.features.delivery.models import (
    DeliveryChannel,
    DeliveryConfig,
    DeliveryResult,
    EmailBodyFormat,
    EmailDeliveryConfig,
)

logger = get_logger(__name__)


class DeliveryHandler(ABC):
    """Deliver a generated report file to its destination."""

    @abstractmethod
    def deliver(self, report_path: str, config: DeliveryConfig) -> DeliveryResult:
        """Send or copy the report and return the outcome."""
        pass


class LocalDeliveryHandler(DeliveryHandler):
    """Copy the report into a target local directory."""

    def deliver(self, report_path: str, config: DeliveryConfig) -> DeliveryResult:
        try:
            dest_dir = ensure_directory(config.local_dir)
            dest_path = dest_dir / Path(report_path).name
            shutil.copy2(report_path, dest_path)
            logger.info(f"Delivered report to local path {dest_path}")
            return DeliveryResult(success=True, channel=DeliveryChannel.LOCAL, destination=str(dest_path))
        except OSError as e:
            return DeliveryResult(success=False, channel=DeliveryChannel.LOCAL, error=str(e))


class EmailDeliveryHandler(DeliveryHandler):
    """Send the report as an email attachment via SMTP."""

    def deliver(self, report_path: str, config: DeliveryConfig) -> DeliveryResult:
        try:
            message = self._build_message(report_path, config.email)
            self._send(message)
            logger.info(f"Delivered report by email to {config.email.to}")
            return DeliveryResult(
                success=True,
                channel=DeliveryChannel.EMAIL,
                destination=", ".join(config.email.to),
            )
        except (OSError, EmailDeliveryError) as e:
            return DeliveryResult(success=False, channel=DeliveryChannel.EMAIL, error=str(e))

    def _build_message(self, report_path: str, email_cfg: EmailDeliveryConfig) -> EmailMessage:
        path = Path(report_path)
        message = EmailMessage()
        message["From"] = get_env("SMTP_FROM") or get_env("SMTP_USER", "reportmaker@localhost")
        message["To"] = ", ".join(email_cfg.to)
        if email_cfg.cc:
            message["Cc"] = ", ".join(email_cfg.cc)
        message["Subject"] = email_cfg.subject or f"Report: {path.stem}"
        message.set_content(email_cfg.body or "Your report is attached.")
        if email_cfg.body_format == EmailBodyFormat.HTML:
            if path.suffix.lower() != ".html":
                raise EmailDeliveryError(
                    f"body_format 'html' needs an HTML report, but the report is {path.name}"
                )
            message.add_alternative(path.read_text(encoding="utf-8"), subtype="html")

        maintype, subtype = self._guess_content_type(path)
        message.add_attachment(path.read_bytes(), maintype=maintype, subtype=subtype, filename=path.name)
        return message

    @staticmethod
    def _guess_content_type(path: Path) -> Tuple[str, str]:
        suffix = path.suffix.lower()
        if suffix == ".pdf":
            return "application", "pdf"
        if suffix == ".html":
            return "text", "html"
        if suffix in (".xlsx", ".xls"):
            return "application", "vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        return "application", "octet-stream"

    def _send(self, message: EmailMessage) -> None:
        host = get_env("SMTP_HOST")
        if not host:
            raise EmailDeliveryError("SMTP_HOST environment variable is not set")
        port = int(get_env("SMTP_PORT", "587"))
        user = get_env("SMTP_USER")
        password = get_env("SMTP_PASSWORD")
        use_tls = (get_env("SMTP_USE_TLS", "true") or "true").lower() == "true"

        with SMTP(host, port, timeout=30) as smtp:
            if use_tls:
                smtp.starttls()
            if user and password:
                smtp.login(user, password)
            smtp.send_message(message)


def create_delivery_handler(channel: DeliveryChannel) -> Optional[DeliveryHandler]:
    """Return the handler for the given channel, or None if no delivery is configured."""
    if channel == DeliveryChannel.NONE:
        return None
    if channel == DeliveryChannel.LOCAL:
        return LocalDeliveryHandler()
    if channel == DeliveryChannel.EMAIL:
        return EmailDeliveryHandler()
    raise DeliveryError(f"Unsupported delivery channel: {channel}")


def deliver_report(report_path: str, config: DeliveryConfig) -> DeliveryResult:
    """Deliver a generated report according to its delivery configuration."""
    handler = create_delivery_handler(config.channel)
    if handler is None:
        return DeliveryResult(success=True, channel=DeliveryChannel.NONE, destination=None)
    return handler.deliver(report_path, config)


def deliver_if_configured(config_path: str, report_path: str) -> Optional[DeliveryResult]:
    """Deliver a report if its YAML config has a ``delivery`` section.

    Returns None when the config declares no delivery, so callers can tell
    "nothing to do" apart from a delivery that succeeded or failed. A
    malformed section is reported as a failed result rather than raised: the
    report itself was generated fine, so the user still needs to see it.
    """
    raw_delivery = (load_yaml_config(config_path) or {}).get("delivery")
    if not raw_delivery:
        return None
    if not isinstance(raw_delivery, dict):
        return DeliveryResult(
            success=False,
            channel=DeliveryChannel.NONE,
            error="Invalid delivery configuration: 'delivery' must be a mapping",
        )
    try:
        delivery_config = DeliveryConfig(**raw_delivery)
    except ValidationError as e:
        return DeliveryResult(
            success=False,
            channel=DeliveryChannel.NONE,
            error=f"Invalid delivery configuration: {e}",
        )
    return deliver_report(report_path, delivery_config)
