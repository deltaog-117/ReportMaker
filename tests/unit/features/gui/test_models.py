"""Unit tests for GUI models."""

from datetime import datetime
from pathlib import Path

import pytest
from pydantic import ValidationError

from reportmaker.features.gui.models import (
    Frequency,
    GuiSettings,
    OutputFile,
    OutputKind,
    ScheduleRequest,
)


def test_settings_default_to_local_only():
    assert GuiSettings().is_local_only is True


@pytest.mark.parametrize("host", ["0.0.0.0", "192.168.1.20", "reports.example.com"])
def test_settings_flag_hosts_reachable_from_other_machines(host):
    assert GuiSettings(host=host).is_local_only is False


@pytest.mark.parametrize("port", [0, 65536, -1])
def test_settings_reject_invalid_ports(port):
    with pytest.raises(ValidationError):
        GuiSettings(port=port)


@pytest.mark.parametrize(
    ("kind", "previewable"),
    [
        (OutputKind.PDF, True),
        (OutputKind.HTML, True),
        (OutputKind.EXCEL, False),
        (OutputKind.OTHER, False),
    ],
)
def test_only_pdf_and_html_can_be_previewed(kind, previewable):
    output = OutputFile(
        name="r", path=Path("r"), size_bytes=1, modified=datetime(2026, 9, 5), kind=kind
    )
    assert output.is_previewable is previewable


def test_interval_schedule_requires_minutes():
    with pytest.raises(ValidationError):
        ScheduleRequest(name="n", report_config="r.yaml", frequency=Frequency.INTERVAL)


def test_custom_schedule_requires_a_cron_expression():
    with pytest.raises(ValidationError):
        ScheduleRequest(
            name="n",
            report_config="r.yaml",
            frequency=Frequency.CUSTOM,
            custom_cron="  ",
        )


def test_schedule_request_trims_names_and_rejects_blank_ones():
    request = ScheduleRequest(
        name="  nightly ", report_config="r.yaml", frequency=Frequency.DAILY
    )
    assert request.name == "nightly"
    with pytest.raises(ValidationError):
        ScheduleRequest(name="   ", report_config="r.yaml", frequency=Frequency.DAILY)


@pytest.mark.parametrize(
    "field, value",
    [("hour", 24), ("minute", 60), ("day_of_month", 29), ("day_of_month", 0)],
)
def test_schedule_request_rejects_out_of_range_times(field, value):
    with pytest.raises(ValidationError):
        ScheduleRequest(
            name="n",
            report_config="r.yaml",
            frequency=Frequency.DAILY,
            **{field: value},
        )
