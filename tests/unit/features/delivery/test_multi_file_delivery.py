"""Unit tests for delivering several report files in one go."""

import pytest

from reportmaker.features.delivery.exceptions import EmailDeliveryError
from reportmaker.features.delivery.models import (
    DeliveryChannel,
    DeliveryConfig,
    EmailBodyFormat,
    EmailDeliveryConfig,
)
from reportmaker.features.delivery.services import (
    EmailDeliveryHandler,
    LocalDeliveryHandler,
    deliver_report,
)


@pytest.fixture
def reports(tmp_path):
    pdf = tmp_path / "r.pdf"
    pdf.write_bytes(b"%PDF")
    html = tmp_path / "r.html"
    html.write_text("<h1>Hi</h1>")
    return [str(pdf), str(html)]


def email_cfg(**kwargs):
    return EmailDeliveryConfig(to=["a@example.com"], **kwargs)


def test_local_delivery_copies_every_file(tmp_path, reports):
    config = DeliveryConfig(channel=DeliveryChannel.LOCAL, local_dir=str(tmp_path / "archive"))
    result = LocalDeliveryHandler().deliver(reports, config)
    assert result.success
    assert sorted(p.name for p in (tmp_path / "archive").iterdir()) == ["r.html", "r.pdf"]


def test_one_email_carries_every_file(reports):
    message = EmailDeliveryHandler()._build_message(reports, email_cfg())
    assert [a.get_filename() for a in message.iter_attachments()] == ["r.pdf", "r.html"]


def test_html_body_uses_the_html_file_among_several(reports):
    message = EmailDeliveryHandler()._build_message(reports, email_cfg(body_format=EmailBodyFormat.HTML))
    assert "<h1>Hi</h1>" in message.get_body(("html",)).get_content()
    assert len(list(message.iter_attachments())) == 2


def test_html_body_without_an_html_file_is_refused(reports):
    with pytest.raises(EmailDeliveryError):
        EmailDeliveryHandler()._build_message(reports[:1], email_cfg(body_format=EmailBodyFormat.HTML))


def test_a_bare_path_is_treated_as_one_file(tmp_path, reports):
    config = DeliveryConfig(channel=DeliveryChannel.LOCAL, local_dir=str(tmp_path / "archive"))
    assert deliver_report(reports[0], config).success
    assert [p.name for p in (tmp_path / "archive").iterdir()] == ["r.pdf"]
