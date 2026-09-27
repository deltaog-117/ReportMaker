"""GUI service layer: everything the pages need, with no NiceGUI import.

Keeping this free of the UI framework means it can be unit-tested directly
and reused if the front-end is ever swapped.
"""

import tempfile
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from reportmaker.features.delivery.services import deliver_if_configured
from reportmaker.features.gui.exceptions import GuiError
from reportmaker.features.gui.models import (
    Frequency,
    OutputFile,
    OutputKind,
    RunOutcome,
    ScheduleRequest,
)
from reportmaker.features.report_generation.exceptions import ConfigError
from reportmaker.features.report_generation.models import ReportResult
from reportmaker.features.report_generation.services import (
    generate_report,
    load_and_validate_config,
)
from reportmaker.features.scheduling.exceptions import SchedulingError
from reportmaker.features.scheduling.models import ScheduleConfig
from reportmaker.features.scheduling.services import SchedulerService
from reportmaker.features.template_management.models import TemplateImportResult
from reportmaker.features.template_management.services import TemplateManager
from reportmaker.shared.file_utils import ensure_directory
from reportmaker.shared.logging import get_logger
from reportmaker.shared.validators import validate_cron_expression

logger = get_logger(__name__)

_KIND_BY_SUFFIX = {
    ".pdf": OutputKind.PDF,
    ".html": OutputKind.HTML,
    ".htm": OutputKind.HTML,
    ".xlsx": OutputKind.EXCEL,
    ".xls": OutputKind.EXCEL,
    # The pipeline names Excel reports after the format value, not the extension.
    ".excel": OutputKind.EXCEL,
}
_SIZE_UNITS = ("B", "KB", "MB", "GB", "TB")


# ---------- Running reports ----------
def run_report_with_delivery(
    config_path: str, output_dir: Path, parameters: Dict[str, Any]
) -> RunOutcome:
    """Generate a report and deliver it if its config asks for delivery.

    Never raises: a UI needs a message to show, not a traceback, so any
    failure is logged and returned as an unsuccessful result.
    """
    started = time.perf_counter()
    logger.info(
        f"GUI run requested: config={config_path} parameters={sorted(parameters)}"
    )
    try:
        ensure_directory(output_dir)
        result = generate_report(config_path, str(output_dir), parameters)
    except Exception as e:
        logger.exception(f"GUI run failed before a result was produced: {config_path}")
        message = str(e) or e.__class__.__name__
        return RunOutcome(
            result=ReportResult(
                success=False, error=message, logs=[f"Failed: {message}"]
            )
        )

    delivery = None
    if result.success and result.output_path:
        delivery = deliver_if_configured(config_path, result.output_path)
    logger.info(
        f"GUI run finished: success={result.success} "
        f"duration={time.perf_counter() - started:.2f}s"
    )
    return RunOutcome(result=result, delivery=delivery)


# ---------- Past reports ----------
def classify_output(path: Path) -> OutputKind:
    """Guess what kind of report a file is from its extension."""
    return _KIND_BY_SUFFIX.get(path.suffix.lower(), OutputKind.OTHER)


def format_size(size_bytes: int) -> str:
    """Render a byte count for humans, e.g. 1536 -> '1.5 KB'."""
    size = float(max(size_bytes, 0))
    for unit in _SIZE_UNITS[:-1]:
        if size < 1024:
            return f"{int(size)} {unit}" if unit == "B" else f"{size:.1f} {unit}"
        size /= 1024
    return f"{size:.1f} {_SIZE_UNITS[-1]}"


def _describe_output(path: Path) -> Optional[OutputFile]:
    try:
        stat = path.stat()
    except OSError:
        # Deleted between listing and stat; nothing useful to show.
        return None
    return OutputFile(
        name=path.name,
        path=path,
        size_bytes=stat.st_size,
        modified=datetime.fromtimestamp(stat.st_mtime),
        kind=classify_output(path),
    )


def list_output_files(output_dir: Path, limit: int = 200) -> List[OutputFile]:
    """Return generated reports in output_dir, newest first."""
    if not output_dir.is_dir():
        return []
    candidates = (
        p for p in output_dir.iterdir() if p.is_file() and not p.name.startswith(".")
    )
    described = (item for item in map(_describe_output, candidates) if item is not None)
    return sorted(described, key=lambda item: item.modified, reverse=True)[:limit]


# ---------- Schedules ----------
def build_cron(request: ScheduleRequest) -> Optional[str]:
    """Translate a plain-language schedule into a 5-field cron expression.

    Returns None for interval schedules, which don't use cron.
    """
    clock = f"{request.minute} {request.hour}"
    if request.frequency == Frequency.DAILY:
        return f"{clock} * * *"
    if request.frequency == Frequency.WEEKLY:
        return f"{clock} * * {request.weekday.value}"
    if request.frequency == Frequency.MONTHLY:
        return f"{clock} {request.day_of_month} * *"
    if request.frequency == Frequency.CUSTOM:
        return (request.custom_cron or "").strip()
    return None


def parse_time_of_day(text: str) -> Tuple[int, int]:
    """Parse 'HH:MM' into (hour, minute). Raises ValueError with a friendly message."""
    hour_text, separator, minute_text = text.strip().partition(":")
    if not separator or not hour_text.isdecimal() or not minute_text.isdecimal():
        raise ValueError("Time must look like 09:30")
    hour, minute = int(hour_text), int(minute_text)
    if not (0 <= hour <= 23 and 0 <= minute <= 59):
        raise ValueError("Time must look like 09:30 (hours 0-23, minutes 0-59)")
    return hour, minute


def create_schedule(
    scheduler: SchedulerService, request: ScheduleRequest, parameters: Dict[str, Any]
) -> None:
    """Validate and store a new schedule on the given scheduler.

    Takes the scheduler instance (rather than a schedules-file path) so a
    schedule added while the GUI's own scheduler is running is picked up
    immediately, instead of only after the next restart.

    Raises:
        GuiError: with a user-facing message if the cron expression, the
            report config, or the schedule itself is invalid or duplicated.

    """
    cron = build_cron(request)
    # Stored absolute so the scheduler daemon finds the report no matter
    # which directory it is started from.
    report_config = str(Path(request.report_config).resolve())
    try:
        if cron:
            validate_cron_expression(cron)
        load_and_validate_config(report_config)
        config = ScheduleConfig(
            name=request.name,
            cron=cron,
            interval_seconds=(
                request.every_minutes * 60
                if request.frequency == Frequency.INTERVAL and request.every_minutes
                else None
            ),
            report_config=report_config,
            parameters=parameters,
        )
        scheduler.add_schedule(config)
    except (ValueError, ConfigError, SchedulingError) as e:
        raise GuiError(str(e)) from e
    logger.info(f"GUI created schedule '{request.name}'")


def deliver_after_schedule_run(cfg: ScheduleConfig, result: ReportResult) -> None:
    """Deliver a scheduled report the same way an interactive run would.

    Passed to ``SchedulerService`` as its ``on_report_generated`` hook so a
    report scheduled from the GUI honours its config's ``delivery:`` section
    just like the CLI's ``schedule start`` daemon does.
    """
    if result.output_path:
        deliver_if_configured(cfg.report_config, result.output_path)


# ---------- Templates ----------
def import_uploaded_template(
    manager: TemplateManager, filename: str, data: bytes, overwrite: bool
) -> TemplateImportResult:
    """Import an uploaded Excel template, returning problems instead of raising."""
    if Path(filename).suffix.lower() != ".xlsx":
        return TemplateImportResult(
            success=False, errors=["Please upload an Excel file (.xlsx)."]
        )
    with tempfile.TemporaryDirectory() as tmp:
        # A fixed on-disk name: never build a path from client-supplied text.
        path = Path(tmp) / "upload.xlsx"
        path.write_bytes(data)
        return manager.import_from_xlsx(str(path), force=overwrite)


def export_template_bytes(manager: TemplateManager, name: str) -> Tuple[str, bytes]:
    """Export a stored template to Excel and return (filename, file bytes)."""
    filename = f"{name}.xlsx"
    with tempfile.TemporaryDirectory() as tmp:
        exported = manager.export_to_xlsx(name, str(Path(tmp) / filename))
        return filename, exported.read_bytes()


def blank_template_bytes(manager: TemplateManager) -> Tuple[str, bytes]:
    """Build the blank Excel template and return (filename, file bytes)."""
    filename = "report_template.xlsx"
    with tempfile.TemporaryDirectory() as tmp:
        created = manager.create_blank_xlsx(str(Path(tmp) / filename))
        return filename, created.read_bytes()
