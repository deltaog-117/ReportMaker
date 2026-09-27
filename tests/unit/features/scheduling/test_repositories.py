"""Unit tests for the run-history store."""

from datetime import datetime

from reportmaker.features.scheduling.models import RunRecord
from reportmaker.features.scheduling.repositories import RunHistoryStore


def make_record(name: str = "nightly", success: bool = True, **overrides) -> RunRecord:
    defaults = dict(
        schedule_name=name,
        started_at=datetime(2026, 1, 1, 9, 0),
        duration_seconds=1.5,
        success=success,
        output_path="out.pdf" if success else None,
        error=None if success else "boom",
    )
    defaults.update(overrides)
    return RunRecord(**defaults)


def test_list_recent_on_missing_file_returns_empty(tmp_path):
    store = RunHistoryStore(str(tmp_path / "run_history.yaml"))
    assert store.list_recent() == []


def test_append_and_list_recent_newest_first(tmp_path):
    store = RunHistoryStore(str(tmp_path / "run_history.yaml"))
    store.append(make_record(started_at=datetime(2026, 1, 1, 9, 0)))
    store.append(make_record(started_at=datetime(2026, 1, 2, 9, 0)))

    records = store.list_recent()

    assert [r.started_at for r in records] == [
        datetime(2026, 1, 2, 9, 0),
        datetime(2026, 1, 1, 9, 0),
    ]


def test_list_recent_filters_by_schedule_name(tmp_path):
    store = RunHistoryStore(str(tmp_path / "run_history.yaml"))
    store.append(make_record(name="nightly"))
    store.append(make_record(name="weekly"))

    records = store.list_recent(schedule_name="weekly")

    assert [r.schedule_name for r in records] == ["weekly"]


def test_history_is_capped_at_max_records(tmp_path):
    store = RunHistoryStore(str(tmp_path / "run_history.yaml"), max_records=3)
    for i in range(5):
        store.append(make_record(started_at=datetime(2026, 1, 1 + i, 9, 0)))

    records = store.list_recent(limit=10)

    assert len(records) == 3
    assert records[0].started_at == datetime(2026, 1, 5, 9, 0)


def test_list_recent_respects_limit(tmp_path):
    store = RunHistoryStore(str(tmp_path / "run_history.yaml"))
    for i in range(5):
        store.append(make_record(started_at=datetime(2026, 1, 1 + i, 9, 0)))

    assert len(store.list_recent(limit=2)) == 2


def test_a_failed_run_round_trips_its_error(tmp_path):
    store = RunHistoryStore(str(tmp_path / "run_history.yaml"))
    store.append(make_record(success=False))

    (record,) = store.list_recent()

    assert record.success is False
    assert record.output_path is None
    assert record.error == "boom"
