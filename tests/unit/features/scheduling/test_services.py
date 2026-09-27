"""Unit tests for the scheduler service."""

from unittest.mock import patch

import pytest
import yaml

from reportmaker.features.report_generation.models import ReportResult
from reportmaker.features.scheduling.exceptions import (
    ScheduleAlreadyExistsError,
    ScheduleNotFoundError,
)
from reportmaker.features.scheduling.models import ScheduleConfig
from reportmaker.features.scheduling.services import SchedulerService


def make_service(tmp_path, **kwargs) -> SchedulerService:
    return SchedulerService(str(tmp_path / "schedules.yaml"), **kwargs)


def add_daily_schedule(service: SchedulerService, name: str = "nightly") -> None:
    service.add_schedule(
        ScheduleConfig(name=name, cron="0 9 * * *", report_config="report.yaml")
    )


# ---------- CRUD ----------
def test_add_schedule_persists_to_disk(tmp_path):
    service = make_service(tmp_path)
    add_daily_schedule(service)

    stored = yaml.safe_load((tmp_path / "schedules.yaml").read_text())
    assert "nightly" in stored


def test_add_schedule_rejects_a_duplicate_name(tmp_path):
    service = make_service(tmp_path)
    add_daily_schedule(service)
    with pytest.raises(ScheduleAlreadyExistsError):
        add_daily_schedule(service)


def test_remove_schedule_raises_when_missing(tmp_path):
    service = make_service(tmp_path)
    with pytest.raises(ScheduleNotFoundError):
        service.remove_schedule("missing")


def test_set_enabled_persists_and_raises_when_missing(tmp_path):
    service = make_service(tmp_path)
    add_daily_schedule(service)

    service.set_enabled("nightly", False)

    reloaded = make_service(tmp_path)
    (status,) = reloaded.list_schedules()
    assert status.enabled is False

    with pytest.raises(ScheduleNotFoundError):
        service.set_enabled("missing", True)


# ---------- Background scheduling ----------
def test_start_background_registers_enabled_jobs_and_returns_immediately(tmp_path):
    service = make_service(tmp_path)
    add_daily_schedule(service)

    service.start_background()
    try:
        assert service.scheduler is not None
        assert service.scheduler.running
        assert service.scheduler.get_job("schedule_nightly") is not None
    finally:
        service.stop()

    assert service.scheduler is None


def test_start_background_skips_disabled_schedules(tmp_path):
    service = make_service(tmp_path)
    service.add_schedule(
        ScheduleConfig(
            name="off", cron="0 9 * * *", report_config="r.yaml", enabled=False
        )
    )
    service.start_background()
    try:
        assert service.scheduler.get_job("schedule_off") is None
    finally:
        service.stop()


def test_set_enabled_adds_and_removes_the_live_job(tmp_path):
    service = make_service(tmp_path)
    service.add_schedule(
        ScheduleConfig(
            name="toggle", cron="0 9 * * *", report_config="r.yaml", enabled=False
        )
    )
    service.start_background()
    try:
        assert service.scheduler.get_job("schedule_toggle") is None

        service.set_enabled("toggle", True)
        assert service.scheduler.get_job("schedule_toggle") is not None

        service.set_enabled("toggle", False)
        assert service.scheduler.get_job("schedule_toggle") is None
    finally:
        service.stop()


def test_add_schedule_reaches_an_already_running_scheduler(tmp_path):
    service = make_service(tmp_path)
    service.start_background()
    try:
        add_daily_schedule(service)
        assert service.scheduler.get_job("schedule_nightly") is not None
    finally:
        service.stop()


# ---------- Run history ----------
def test_job_function_records_a_successful_run(tmp_path):
    service = make_service(tmp_path)
    add_daily_schedule(service)
    result = ReportResult(success=True, output_path=str(tmp_path / "out.pdf"))

    with patch(
        "reportmaker.features.scheduling.services.generate_report", return_value=result
    ):
        service._job_function("nightly")

    (record,) = service.list_run_history("nightly")
    assert record.success is True
    assert record.output_path == str(tmp_path / "out.pdf")
    assert record.duration_seconds >= 0


def test_job_function_records_a_failed_run(tmp_path):
    service = make_service(tmp_path)
    add_daily_schedule(service)
    result = ReportResult(success=False, error="query failed")

    with patch(
        "reportmaker.features.scheduling.services.generate_report", return_value=result
    ):
        service._job_function("nightly")

    (record,) = service.list_run_history("nightly")
    assert record.success is False
    assert record.error == "query failed"


def test_job_function_records_an_exception_as_a_failed_run(tmp_path):
    service = make_service(tmp_path)
    add_daily_schedule(service)

    with patch(
        "reportmaker.features.scheduling.services.generate_report",
        side_effect=RuntimeError("boom"),
    ):
        service._job_function("nightly")

    (record,) = service.list_run_history("nightly")
    assert record.success is False
    assert record.error == "boom"


def test_job_function_calls_on_report_generated_after_success(tmp_path):
    calls = []
    service = make_service(
        tmp_path, on_report_generated=lambda cfg, result: calls.append((cfg, result))
    )
    add_daily_schedule(service)
    result = ReportResult(success=True, output_path=str(tmp_path / "out.pdf"))

    with patch(
        "reportmaker.features.scheduling.services.generate_report", return_value=result
    ):
        service._job_function("nightly")

    assert len(calls) == 1
    assert calls[0][0].name == "nightly"


def test_disabled_schedule_is_skipped_without_recording_a_run(tmp_path):
    service = make_service(tmp_path)
    service.add_schedule(
        ScheduleConfig(
            name="off", cron="0 9 * * *", report_config="r.yaml", enabled=False
        )
    )

    with patch("reportmaker.features.scheduling.services.generate_report") as gen:
        service._job_function("off")

    gen.assert_not_called()
    assert service.list_run_history("off") == []
