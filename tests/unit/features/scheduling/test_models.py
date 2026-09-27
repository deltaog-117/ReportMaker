"""Unit tests for scheduling models."""

from datetime import datetime

import pytest
from pydantic import ValidationError

from reportmaker.features.scheduling.models import RunRecord


def test_run_record_accepts_a_successful_run():
    record = RunRecord(
        schedule_name="nightly",
        started_at=datetime(2026, 1, 1, 9, 0),
        duration_seconds=2.5,
        success=True,
        output_path="report.pdf",
    )
    assert record.error is None


def test_run_record_accepts_a_failed_run():
    record = RunRecord(
        schedule_name="nightly",
        started_at=datetime(2026, 1, 1, 9, 0),
        duration_seconds=0.1,
        success=False,
        error="query failed",
    )
    assert record.output_path is None


def test_run_record_rejects_a_negative_duration():
    with pytest.raises(ValidationError):
        RunRecord(
            schedule_name="nightly",
            started_at=datetime(2026, 1, 1, 9, 0),
            duration_seconds=-1,
            success=True,
        )
