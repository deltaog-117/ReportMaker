"""Unit and property tests for the GUI service layer."""

import os
from datetime import datetime
from pathlib import Path
from unittest.mock import patch

import pytest
import yaml
from hypothesis import given, settings
from hypothesis import strategies as st

from apscheduler.triggers.cron import CronTrigger

from reportmaker.features.delivery.models import DeliveryChannel, DeliveryResult
from reportmaker.features.gui.exceptions import GuiError
from reportmaker.features.gui.models import (
    Frequency,
    OutputKind,
    ScheduleRequest,
    Weekday,
)
from reportmaker.features.gui.services import (
    blank_template_bytes,
    build_cron,
    classify_output,
    create_schedule,
    export_template_bytes,
    format_size,
    import_uploaded_template,
    list_output_files,
    parse_time_of_day,
    run_report_with_delivery,
)
from reportmaker.features.report_generation.exceptions import ConfigError
from reportmaker.features.report_generation.models import ReportResult
from reportmaker.features.scheduling.services import SchedulerService
from reportmaker.features.template_management.services import TemplateManager
from reportmaker.shared.validators import validate_cron_expression

VALID_REPORT = {
    "name": "Demo",
    "data_source": {"url": "sqlite:///demo.db", "query": "SELECT 1 AS n"},
    "output": "html",
}


def write_report_config(path: Path) -> Path:
    path.write_text(yaml.safe_dump(VALID_REPORT))
    return path


clock_schedules = st.builds(
    ScheduleRequest,
    name=st.just("nightly"),
    report_config=st.just("report.yaml"),
    frequency=st.sampled_from([Frequency.DAILY, Frequency.WEEKLY, Frequency.MONTHLY]),
    hour=st.integers(0, 23),
    minute=st.integers(0, 59),
    weekday=st.sampled_from(list(Weekday)),
    day_of_month=st.integers(1, 28),
)


# ---------- Properties ----------
@settings(deadline=None)
@given(clock_schedules)
def test_generated_cron_is_valid_and_fires_at_the_requested_time(request):
    cron = build_cron(request)
    validate_cron_expression(cron)
    trigger = CronTrigger.from_crontab(cron)
    # Mid-January keeps every candidate fire time clear of DST changes.
    now = datetime(2026, 1, 15, 12, 0, tzinfo=trigger.timezone)
    fire = trigger.get_next_fire_time(None, now)
    assert (fire.hour, fire.minute) == (request.hour, request.minute)


@given(st.integers(0, 23), st.integers(0, 59))
def test_time_of_day_round_trips(hour, minute):
    assert parse_time_of_day(f"{hour:02d}:{minute:02d}") == (hour, minute)
    assert parse_time_of_day(f" {hour}:{minute} ") == (hour, minute)


@given(st.text())
def test_time_of_day_either_parses_in_range_or_raises_value_error(text):
    try:
        hour, minute = parse_time_of_day(text)
    except ValueError:
        return
    assert 0 <= hour <= 23 and 0 <= minute <= 59


@given(st.integers(min_value=-5, max_value=10**18))
def test_format_size_always_ends_in_a_unit(size):
    assert format_size(size).split()[-1] in {"B", "KB", "MB", "GB", "TB"}


# ---------- Schedules ----------
def test_interval_schedules_have_no_cron():
    request = ScheduleRequest(
        name="n", report_config="r.yaml", frequency=Frequency.INTERVAL, every_minutes=15
    )
    assert build_cron(request) is None


def test_custom_cron_passes_through_trimmed():
    request = ScheduleRequest(
        name="n",
        report_config="r.yaml",
        frequency=Frequency.CUSTOM,
        custom_cron=" 0 9 * * mon-fri ",
    )
    assert build_cron(request) == "0 9 * * mon-fri"


@pytest.mark.parametrize(
    "text", ["", "9", "9:", ":30", "24:00", "09:60", "ab:cd", "9-30", "-1:00", "²:00"]
)
def test_time_of_day_rejects_bad_input(text):
    with pytest.raises(ValueError):
        parse_time_of_day(text)


def test_create_schedule_stores_an_absolute_report_path(tmp_path):
    config = write_report_config(tmp_path / "report.yaml")
    schedules_file = tmp_path / "schedules.yaml"
    request = ScheduleRequest(
        name="nightly",
        report_config=str(config),
        frequency=Frequency.DAILY,
        hour=7,
        minute=15,
    )

    create_schedule(schedules_file, request, {"region": "EU"})

    stored = yaml.safe_load(schedules_file.read_text())["nightly"]
    assert stored["cron"] == "15 7 * * *"
    assert stored["parameters"] == {"region": "EU"}
    assert Path(stored["report_config"]).is_absolute()


def test_create_schedule_supports_intervals(tmp_path):
    config = write_report_config(tmp_path / "report.yaml")
    request = ScheduleRequest(
        name="often",
        report_config=str(config),
        frequency=Frequency.INTERVAL,
        every_minutes=15,
    )
    create_schedule(tmp_path / "schedules.yaml", request, {})
    (status,) = SchedulerService(str(tmp_path / "schedules.yaml")).list_schedules()
    assert status.trigger_value == "every 900s"


def test_create_schedule_rejects_duplicate_names(tmp_path):
    config = write_report_config(tmp_path / "report.yaml")
    request = ScheduleRequest(
        name="dup", report_config=str(config), frequency=Frequency.DAILY
    )
    create_schedule(tmp_path / "schedules.yaml", request, {})
    with pytest.raises(GuiError, match="already exists"):
        create_schedule(tmp_path / "schedules.yaml", request, {})


def test_create_schedule_rejects_a_bad_cron_expression(tmp_path):
    config = write_report_config(tmp_path / "report.yaml")
    request = ScheduleRequest(
        name="bad",
        report_config=str(config),
        frequency=Frequency.CUSTOM,
        custom_cron="not cron",
    )
    with pytest.raises(GuiError, match="cron"):
        create_schedule(tmp_path / "schedules.yaml", request, {})
    assert not (tmp_path / "schedules.yaml").exists()


def test_create_schedule_rejects_an_invalid_report_config(tmp_path):
    broken = tmp_path / "broken.yaml"
    broken.write_text("name: only-a-name\n")
    request = ScheduleRequest(
        name="x", report_config=str(broken), frequency=Frequency.DAILY
    )
    with pytest.raises(GuiError, match="invalid report configuration"):
        create_schedule(tmp_path / "schedules.yaml", request, {})


# ---------- Past reports ----------
@pytest.mark.parametrize(
    ("filename", "kind"),
    [
        ("a.pdf", OutputKind.PDF),
        ("a.HTML", OutputKind.HTML),
        ("a.xlsx", OutputKind.EXCEL),
        ("a_20260911.excel", OutputKind.EXCEL),
        ("a.csv", OutputKind.OTHER),
        ("noextension", OutputKind.OTHER),
    ],
)
def test_classify_output(filename, kind):
    assert classify_output(Path(filename)) is kind


@pytest.mark.parametrize(
    ("size", "text"),
    [(0, "0 B"), (1023, "1023 B"), (1536, "1.5 KB"), (5 * 1024**2, "5.0 MB")],
)
def test_format_size_examples(size, text):
    assert format_size(size) == text


def test_list_output_files_is_newest_first_and_skips_noise(tmp_path):
    old, new = tmp_path / "old.pdf", tmp_path / "new.html"
    old.write_bytes(b"old")
    new.write_bytes(b"new")
    os.utime(old, (1_000_000_000, 1_000_000_000))
    os.utime(new, (2_000_000_000, 2_000_000_000))
    (tmp_path / ".hidden.pdf").write_bytes(b"x")
    (tmp_path / "subdir").mkdir()

    assert [f.name for f in list_output_files(tmp_path)] == ["new.html", "old.pdf"]


def test_list_output_files_respects_the_limit(tmp_path):
    for index in range(5):
        (tmp_path / f"r{index}.pdf").write_bytes(b"x")
    assert len(list_output_files(tmp_path, limit=3)) == 3


def test_list_output_files_handles_a_missing_directory(tmp_path):
    assert list_output_files(tmp_path / "does-not-exist") == []


# ---------- Running reports ----------
def test_run_delivers_after_a_successful_report(tmp_path):
    result = ReportResult(success=True, output_path=str(tmp_path / "r.pdf"))
    delivered = DeliveryResult(
        success=True, channel=DeliveryChannel.LOCAL, destination="/archive"
    )
    with (
        patch("reportmaker.features.gui.services.generate_report", return_value=result),
        patch(
            "reportmaker.features.gui.services.deliver_if_configured",
            return_value=delivered,
        ) as deliver,
    ):
        outcome = run_report_with_delivery("cfg.yaml", tmp_path, {"a": 1})

    assert outcome.succeeded and outcome.delivery == delivered
    deliver.assert_called_once_with("cfg.yaml", str(tmp_path / "r.pdf"))


def test_run_does_not_deliver_a_failed_report(tmp_path):
    result = ReportResult(success=False, error="query failed")
    with (
        patch("reportmaker.features.gui.services.generate_report", return_value=result),
        patch("reportmaker.features.gui.services.deliver_if_configured") as deliver,
    ):
        outcome = run_report_with_delivery("cfg.yaml", tmp_path, {})

    assert not outcome.succeeded and outcome.delivery is None
    deliver.assert_not_called()


def test_run_turns_exceptions_into_a_failed_outcome(tmp_path):
    with patch(
        "reportmaker.features.gui.services.generate_report",
        side_effect=ConfigError("bad config"),
    ):
        outcome = run_report_with_delivery("cfg.yaml", tmp_path, {})

    assert not outcome.succeeded
    assert outcome.result.error == "bad config"


def test_run_creates_the_output_directory(tmp_path):
    result = ReportResult(success=False, error="x")
    target = tmp_path / "nested" / "reports"
    with patch(
        "reportmaker.features.gui.services.generate_report", return_value=result
    ):
        run_report_with_delivery("cfg.yaml", target, {})
    assert target.is_dir()


# ---------- Templates ----------
def test_blank_template_can_be_uploaded_back(tmp_path):
    manager = TemplateManager(str(tmp_path / "templates"))
    filename, data = blank_template_bytes(manager)
    assert filename.endswith(".xlsx") and data.startswith(b"PK")

    result = import_uploaded_template(manager, filename, data, overwrite=False)

    assert result.success, result.errors
    assert [t.name for t in manager.list_templates()] == [result.template_name]


def test_uploading_the_same_template_twice_needs_overwrite(tmp_path):
    manager = TemplateManager(str(tmp_path / "templates"))
    filename, data = blank_template_bytes(manager)
    assert import_uploaded_template(manager, filename, data, overwrite=False).success

    assert not import_uploaded_template(
        manager, filename, data, overwrite=False
    ).success
    assert import_uploaded_template(manager, filename, data, overwrite=True).success


def test_upload_rejects_non_excel_files(tmp_path):
    manager = TemplateManager(str(tmp_path / "templates"))
    result = import_uploaded_template(manager, "notes.txt", b"hello", overwrite=False)
    assert not result.success and "Excel" in result.errors[0]


def test_upload_reports_corrupt_spreadsheets_instead_of_raising(tmp_path):
    manager = TemplateManager(str(tmp_path / "templates"))
    result = import_uploaded_template(
        manager, "broken.xlsx", b"not a zip", overwrite=False
    )
    assert not result.success and result.errors


def test_upload_ignores_path_tricks_in_the_client_filename(tmp_path):
    manager = TemplateManager(str(tmp_path / "templates"))
    _, data = blank_template_bytes(manager)
    result = import_uploaded_template(manager, "../../evil.xlsx", data, overwrite=False)
    assert result.success
    assert not (tmp_path / "evil.xlsx").exists()


def test_exported_template_is_an_excel_file(tmp_path):
    manager = TemplateManager(str(tmp_path / "templates"))
    filename, data = blank_template_bytes(manager)
    result = import_uploaded_template(manager, filename, data, overwrite=False)

    exported_name, exported = export_template_bytes(manager, result.template_name)

    assert exported_name == f"{result.template_name}.xlsx"
    assert exported.startswith(b"PK")
