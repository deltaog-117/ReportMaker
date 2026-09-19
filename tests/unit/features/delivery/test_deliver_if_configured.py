"""Unit tests for delivering a report based on its YAML config."""

import yaml

from reportmaker.features.delivery.models import DeliveryChannel
from reportmaker.features.delivery.services import deliver_if_configured


def write_config(path, delivery):
    data = {"name": "Demo"}
    if delivery is not None:
        data["delivery"] = delivery
    path.write_text(yaml.safe_dump(data))
    return str(path)


def make_report(tmp_path):
    report = tmp_path / "report.pdf"
    report.write_bytes(b"%PDF-1.4 fake report")
    return str(report)


def test_returns_none_when_the_config_has_no_delivery_section(tmp_path):
    config = write_config(tmp_path / "cfg.yaml", None)
    assert deliver_if_configured(config, make_report(tmp_path)) is None


def test_returns_none_for_an_empty_config_file(tmp_path):
    empty = tmp_path / "cfg.yaml"
    empty.write_text("")
    assert deliver_if_configured(str(empty), make_report(tmp_path)) is None


def test_copies_the_report_when_local_delivery_is_configured(tmp_path):
    archive = tmp_path / "archive"
    config = write_config(
        tmp_path / "cfg.yaml", {"channel": "local", "local_dir": str(archive)}
    )

    result = deliver_if_configured(config, make_report(tmp_path))

    assert result.success and result.channel == DeliveryChannel.LOCAL
    assert (archive / "report.pdf").read_bytes() == b"%PDF-1.4 fake report"


def test_reports_an_invalid_delivery_section_instead_of_raising(tmp_path):
    config = write_config(tmp_path / "cfg.yaml", {"channel": "email"})

    result = deliver_if_configured(config, make_report(tmp_path))

    assert not result.success
    assert "Invalid delivery configuration" in result.error


def test_reports_a_delivery_section_that_is_not_a_mapping(tmp_path):
    config = write_config(tmp_path / "cfg.yaml", "local")

    result = deliver_if_configured(config, make_report(tmp_path))

    assert not result.success
    assert "mapping" in result.error
