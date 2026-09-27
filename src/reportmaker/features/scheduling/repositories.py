"""Persistence for schedule run history."""

from pathlib import Path
from typing import List, Optional

import yaml

from reportmaker.features.scheduling.models import RunRecord
from reportmaker.shared.file_utils import ensure_directory

DEFAULT_MAX_RECORDS = 200


class RunHistoryStore:
    """A bounded, file-backed log of schedule runs, newest first.

    Kept separate from ``schedules.yaml`` because a schedule's definition and
    its execution history have different lifecycles: removing a schedule
    should not erase what it already did, and the history grows on every
    run rather than only on user edits.
    """

    def __init__(self, history_file: str, max_records: int = DEFAULT_MAX_RECORDS):
        """Point the store at a YAML file, capped at `max_records` entries."""
        self.history_file = Path(history_file)
        self.max_records = max_records

    def _load(self) -> List[RunRecord]:
        if not self.history_file.exists():
            return []
        with open(self.history_file, "r") as f:
            data = yaml.safe_load(f) or []
        return [RunRecord(**entry) for entry in data]

    def _save(self, records: List[RunRecord]) -> None:
        ensure_directory(self.history_file.parent)
        data = [r.model_dump(mode="json") for r in records]
        with open(self.history_file, "w") as f:
            yaml.dump(data, f, default_flow_style=False)

    def append(self, record: RunRecord) -> None:
        """Add a run record, keeping only the most recent ``max_records``."""
        records = self._load()
        records.insert(0, record)
        self._save(records[: self.max_records])

    def list_recent(
        self, schedule_name: Optional[str] = None, limit: int = 50
    ) -> List[RunRecord]:
        """Return recent runs, newest first, optionally filtered to one schedule."""
        records = self._load()
        if schedule_name is not None:
            records = [r for r in records if r.schedule_name == schedule_name]
        return records[:limit]
