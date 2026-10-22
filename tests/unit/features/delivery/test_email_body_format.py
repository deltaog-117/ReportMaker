"""Unit tests for the email body_format option."""

import pytest

from reportmaker.features.delivery.exceptions import EmailDeliveryError
from reportmaker.features.delivery.models import EmailBodyFormat, EmailDeliveryConfig
from reportmaker.features.delivery.services import EmailDeliveryHandler


def email_cfg(body_format):
    return EmailDeliveryConfig(to=["a@example.com"], body_format=body_format)


def test_defaults_to_a_plain_text_body(tmp_path):
    report = tmp_path / "r.html"
    report.write_text("<h1>Hi</h1>")
    message = EmailDeliveryHandler()._build_message(str(report), EmailDeliveryConfig(to=["a@example.com"]))
    assert message.get_body(("html",)) is None


def test_html_format_inlines_the_report_and_keeps_the_attachment(tmp_path):
    report = tmp_path / "r.html"
    report.write_text("<h1>Hi</h1>")
    message = EmailDeliveryHandler()._build_message(str(report), email_cfg(EmailBodyFormat.HTML))
    assert "<h1>Hi</h1>" in message.get_body(("html",)).get_content()
    assert [a.get_filename() for a in message.iter_attachments()] == ["r.html"]


def test_html_format_rejects_a_non_html_report(tmp_path):
    report = tmp_path / "r.pdf"
    report.write_bytes(b"%PDF")
    with pytest.raises(EmailDeliveryError):
        EmailDeliveryHandler()._build_message(str(report), email_cfg(EmailBodyFormat.HTML))
