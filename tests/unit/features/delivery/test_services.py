"""Unit tests for delivery services."""

from unittest.mock import MagicMock, patch

from reportmaker.features.delivery.models import DeliveryChannel, DeliveryConfig, EmailDeliveryConfig
from reportmaker.features.delivery.services import (
    LocalDeliveryHandler,
    EmailDeliveryHandler,
    create_delivery_handler,
    deliver_report,
)


def test_create_delivery_handler_none_returns_none():
    assert create_delivery_handler(DeliveryChannel.NONE) is None


def test_create_delivery_handler_local():
    assert isinstance(create_delivery_handler(DeliveryChannel.LOCAL), LocalDeliveryHandler)


def test_create_delivery_handler_email():
    assert isinstance(create_delivery_handler(DeliveryChannel.EMAIL), EmailDeliveryHandler)


def test_deliver_report_none_channel_is_a_noop_success(tmp_path):
    result = deliver_report(str(tmp_path / "report.pdf"), DeliveryConfig())
    assert result.success is True
    assert result.channel == DeliveryChannel.NONE


def test_local_delivery_handler_copies_file(tmp_path):
    report_path = tmp_path / "report.pdf"
    report_path.write_bytes(b"%PDF-1.4 fake report")
    dest_dir = tmp_path / "archive"

    config = DeliveryConfig(channel=DeliveryChannel.LOCAL, local_dir=str(dest_dir))
    result = LocalDeliveryHandler().deliver(str(report_path), config)

    assert result.success is True
    assert (dest_dir / "report.pdf").read_bytes() == b"%PDF-1.4 fake report"


def test_email_delivery_handler_sends_via_smtp(tmp_path, monkeypatch):
    report_path = tmp_path / "report.pdf"
    report_path.write_bytes(b"%PDF-1.4 fake report")

    monkeypatch.setenv("SMTP_HOST", "smtp.example.com")
    monkeypatch.setenv("SMTP_USER", "sender@example.com")
    monkeypatch.setenv("SMTP_PASSWORD", "secret")

    config = DeliveryConfig(
        channel=DeliveryChannel.EMAIL,
        email=EmailDeliveryConfig(to=["recipient@example.com"], subject="Test Report"),
    )

    with patch("reportmaker.features.delivery.services.SMTP") as mock_smtp_cls:
        mock_smtp = MagicMock()
        mock_smtp_cls.return_value.__enter__.return_value = mock_smtp

        result = EmailDeliveryHandler().deliver(str(report_path), config)

    assert result.success is True
    assert result.destination == "recipient@example.com"
    mock_smtp.login.assert_called_once_with("sender@example.com", "secret")
    mock_smtp.send_message.assert_called_once()


def test_email_delivery_handler_fails_without_smtp_host(tmp_path, monkeypatch):
    report_path = tmp_path / "report.pdf"
    report_path.write_bytes(b"%PDF-1.4 fake report")
    monkeypatch.delenv("SMTP_HOST", raising=False)

    config = DeliveryConfig(channel=DeliveryChannel.EMAIL, email=EmailDeliveryConfig(to=["recipient@example.com"]))
    result = EmailDeliveryHandler().deliver(str(report_path), config)

    assert result.success is False
    assert "SMTP_HOST" in result.error
