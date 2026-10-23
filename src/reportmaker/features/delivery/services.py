"""Delivery service: send a generated report through a configured channel."""

import shutil
from abc import ABC, abstractmethod
from email.message import EmailMessage
from pathlib import Path
from smtplib import SMTP
from typing import List, Optional, Sequence, Tuple, Union

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
    def deliver(self, report_paths: List[str], config: DeliveryConfig) -> DeliveryResult:
        """Send or copy the report files and return the outcome."""
        pass


class LocalDeliveryHandler(DeliveryHandler):
    """Copy the report into a target local directory."""

    def deliver(self, report_paths: List[str], config: DeliveryConfig) -> DeliveryResult:
        try:
            dest_dir = ensure_directory(config.local_dir)
            for report_path in report_paths:
                dest_path = dest_dir / Path(report_path).name
                shutil.copy2(report_path, dest_path)
                logger.info(f"Delivered report to local path {dest_path}")
            return DeliveryResult(success=True, channel=DeliveryChannel.LOCAL, destination=str(dest_dir))
        except OSError as e:
            return DeliveryResult(success=False, channel=DeliveryChannel.LOCAL, error=str(e))


class EmailDeliveryHandler(DeliveryHandler):
    """Send the report as an email attachment via SMTP."""

    def deliver(self, report_paths: List[str], config: DeliveryConfig) -> DeliveryResult:
        try:
            message = self._build_message(report_paths, config.email)
            self._send(message)
            logger.info(f"Delivered report by email to {config.email.to}")
            return DeliveryResult(
                success=True,
                channel=DeliveryChannel.EMAIL,
                destination=", ".join(config.email.to),
            )
        except (OSError, EmailDeliveryError) as e:
            return DeliveryResult(success=False, channel=DeliveryChannel.EMAIL, error=str(e))

    def _build_message(
        self, report_paths: List[str], email_cfg: EmailDeliveryConfig
    ) -> EmailMessage:
        paths = [Path(p) for p in report_paths]
        message = EmailMessage()
        message["From"] = get_env("SMTP_FROM") or get_env("SMTP_USER", "reportmaker@localhost")
        message["To"] = ", ".join(email_cfg.to)
        if email_cfg.cc:
            message["Cc"] = ", ".join(email_cfg.cc)
        message["Subject"] = email_cfg.subject or f"Report: {paths[0].stem}"
        message.set_content(email_cfg.body or "Your report is attached.")
        if email_cfg.body_format == EmailBodyFormat.HTML:
            html_path = next((p for p in paths if p.suffix.lower() == ".html"), None)
            if html_path is None:
                raise EmailDeliveryError(
                    "body_format 'html' needs an HTML report, but the reports are "
                    + ", ".join(p.name for p in paths)
                )
            message.add_alternative(html_path.read_text(encoding="utf-8"), subtype="html")

        for path in paths:
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


def _as_paths(report_paths: Union[str, Sequence[str]]) -> List[str]:
    """Let callers pass one path or several; a bare str must not be iterated per character."""
    return [report_paths] if isinstance(report_paths, str) else list(report_paths)


def deliver_report(
    report_paths: Union[str, Sequence[str]], config: DeliveryConfig
) -> DeliveryResult:
    """Deliver the generated report file(s) according to the delivery configuration."""
    handler = create_delivery_handler(config.channel)
    if handler is None:
        return DeliveryResult(success=True, channel=DeliveryChannel.NONE, destination=None)
    return handler.deliver(_as_paths(report_paths), config)


def deliver_if_configured(
    config_path: str, report_paths: Union[str, Sequence[str]]
) -> Optional[DeliveryResult]:
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
    return deliver_report(report_paths, delivery_config)
