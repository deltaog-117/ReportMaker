"""GUI service layer: everything the pages need, with no NiceGUI import.

Keeping this free of the UI framework means it can be unit-tested directly
and reused if the front-end is ever swapped.
"""

import tempfile
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from pydantic import ValidationError
from sqlalchemy import create_engine, text
from sqlalchemy.exc import SQLAlchemyError

from reportmaker.features.delivery.services import deliver_if_configured
from reportmaker.features.gui.exceptions import GuiError
from reportmaker.features.gui.models import (
    AggregationRow,
    Frequency,
    OutputFile,
    OutputKind,
    ParameterRow,
    QueryPreview,
    RunOutcome,
    ScheduleRequest,
    TemplateDraft,
)
from reportmaker.features.report_generation.exceptions import ConfigError
from reportmaker.features.report_generation.models import (
    ChartConfig,
    DataSourceConfig,
    ParameterSchema,
    ParameterType,
    ReportConfig,
    ReportResult,
    TransformConfig,
)
from reportmaker.features.report_generation.services import (
    generate_report,
    load_and_validate_config,
    validate_report_config_semantics,
)
from reportmaker.features.scheduling.exceptions import SchedulingError
from reportmaker.features.scheduling.models import ScheduleConfig
from reportmaker.features.scheduling.services import SchedulerService
from reportmaker.features.template_management.exceptions import (
    TemplateAlreadyExistsError,
    TemplateError,
    TemplateValidationError,
)
from reportmaker.features.template_management.models import TemplateImportResult
from reportmaker.features.template_management.services import TemplateManager
from reportmaker.shared.file_utils import ensure_directory
from reportmaker.shared.logging import get_logger
from reportmaker.shared.templating import (
    process_parameters,
    render_sql_query,
    validate_and_cast_parameter,
)
from reportmaker.shared.validators import (
    collect_errors,
    validate_cron_expression,
    validate_database_url,
    validate_jinja2_syntax,
)

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
PREVIEW_ROWS = 20
_CAST_ON_SAVE = (ParameterType.INTEGER, ParameterType.FLOAT, ParameterType.BOOLEAN)


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


# ---------- Template editor ----------
def _first_message(error: ValidationError) -> str:
    first = error.errors()[0]
    where = ".".join(str(part) for part in first["loc"])
    return f"{where}: {first['msg']}" if where else first["msg"]


def _parameter_schema(row: ParameterRow) -> ParameterSchema:
    """Turn one editor row into a schema; raises ValueError with a message."""
    name = row.name.strip()
    default_text = row.default.strip()
    default: Optional[Any] = default_text or None
    try:
        kind = ParameterType(row.type)
        if default is not None and kind in _CAST_ON_SAVE:
            # Stored typed so the YAML holds 5, not "5".
            default = validate_and_cast_parameter(
                default, ParameterSchema(name=name or "?", type=kind)
            )
        return ParameterSchema(
            name=name,
            type=kind,
            required=row.required,
            default=default,
            description=row.description.strip() or None,
        )
    except ValidationError as e:
        raise ValueError(_first_message(e)) from e


def _parameter_schemas(rows: List[ParameterRow]) -> Tuple[List[ParameterSchema], List[str]]:
    schemas: List[ParameterSchema] = []
    errors: List[str] = []
    seen: set = set()
    for row in rows:
        if not row.name.strip():
            if row.default.strip() or row.description.strip():
                errors.append("A parameter has no name")
            continue
        label = f"Parameter '{row.name.strip()}'"
        if row.name.strip() in seen:
            errors.append(f"{label} is listed twice")
            continue
        seen.add(row.name.strip())
        try:
            schemas.append(_parameter_schema(row))
        except ValueError as e:
            errors.append(f"{label}: {e}")
    return schemas, errors


def _draft_problems(draft: TemplateDraft) -> List[str]:
    """Catch what the form can get wrong before pydantic sees it."""
    problems: List[str] = []
    if not draft.name.strip():
        problems.append("Give the report a name")
    if not draft.database_url.strip():
        problems.append("Enter the database URL")
    if not draft.query.strip():
        problems.append("Enter the SQL query")
    if draft.chart_kind:
        if not (draft.chart_x.strip() and draft.chart_y.strip()):
            problems.append("A chart needs both an X column and a Y column")
    elif draft.chart_x.strip() or draft.chart_y.strip():
        problems.append("Pick a chart type, or clear the chart columns")
    pivot = [draft.pivot_index, draft.pivot_columns, draft.pivot_values]
    if any(p.strip() for p in pivot) and not all(p.strip() for p in pivot):
        problems.append("A pivot needs index, columns and values all filled in")
    columns = [a.column.strip() for a in draft.aggregations if a.column.strip()]
    if len(columns) != len(set(columns)):
        problems.append("A column appears twice in the aggregations")
    return problems


def build_report_config(
    draft: TemplateDraft, base: Optional[ReportConfig] = None
) -> ReportConfig:
    """Validate an editor draft and build the report config it describes.

    ``base`` is the config being edited; settings the form has no field for
    (static query parameters, the cron hint) are carried over from it.

    Raises:
        GuiError: listing every problem found, one per line.

    """
    schemas, parameter_problems = _parameter_schemas(draft.parameters)
    problems = _draft_problems(draft) + parameter_problems
    if problems:
        raise GuiError("\n".join(problems))

    group_by = [c.strip() for c in draft.group_by.split(",") if c.strip()]
    aggregations = {
        a.column.strip(): a.function.strip().lower()
        for a in draft.aggregations
        if a.column.strip()
    }
    pivot = (
        {
            "index": draft.pivot_index.strip(),
            "columns": draft.pivot_columns.strip(),
            "values": draft.pivot_values.strip(),
        }
        if draft.pivot_index.strip()
        else None
    )
    try:
        config = ReportConfig(
            name=draft.name.strip(),
            description=draft.description.strip() or None,
            parameters=schemas or None,
            data_source=DataSourceConfig(
                url=draft.database_url.strip(),
                query=draft.query.strip(),
                parameters=base.data_source.parameters if base else None,
            ),
            transform=(
                TransformConfig(
                    group_by=group_by or None,
                    aggregations=aggregations or None,
                    pivot=pivot,
                )
                if group_by or aggregations or pivot
                else None
            ),
            output=draft.output,
            chart=(
                ChartConfig(
                    kind=draft.chart_kind,
                    x_column=draft.chart_x.strip(),
                    y_column=draft.chart_y.strip(),
                    title=draft.chart_title.strip() or None,
                    x_label=draft.chart_x_label.strip() or None,
                    y_label=draft.chart_y_label.strip() or None,
                )
                if draft.chart_kind
                else None
            ),
            schedule=base.schedule if base else None,
        )
    except ValidationError as e:
        raise GuiError(_first_message(e)) from e
    semantic = validate_report_config_semantics(config)
    if semantic:
        raise GuiError("\n".join(semantic))
    return config


def draft_from_config(config: ReportConfig) -> TemplateDraft:
    """Fill an editor draft from a stored report config."""
    transform = config.transform
    pivot = (transform.pivot if transform else None) or {}
    chart = config.chart
    return TemplateDraft(
        name=config.name,
        description=config.description or "",
        output=config.output.value,
        database_url=config.data_source.url,
        query=config.data_source.query,
        chart_kind=chart.kind.value if chart else "",
        chart_x=chart.x_column if chart else "",
        chart_y=chart.y_column if chart else "",
        chart_title=(chart.title if chart else None) or "",
        chart_x_label=(chart.x_label if chart else None) or "",
        chart_y_label=(chart.y_label if chart else None) or "",
        group_by=", ".join((transform.group_by if transform else None) or []),
        aggregations=[
            AggregationRow(column=column, function=function)
            for column, function in ((transform.aggregations if transform else None) or {}).items()
        ],
        pivot_index=str(pivot.get("index", "")),
        pivot_columns=str(pivot.get("columns", "")),
        pivot_values=str(pivot.get("values", "")),
        parameters=[
            ParameterRow(
                name=p.name,
                type=p.type.value,
                required=p.required,
                default="" if p.default is None else str(p.default),
                description=p.description or "",
            )
            for p in (config.parameters or [])
        ],
    )


def load_template_draft(
    manager: TemplateManager, name: str
) -> Tuple[TemplateDraft, ReportConfig]:
    """Load a stored template for editing; returns the draft and its config."""
    try:
        config = manager.validate_template(name)
    except TemplateError as e:
        raise GuiError(str(e)) from e
    return draft_from_config(config), config


def save_template_draft(
    manager: TemplateManager,
    draft: TemplateDraft,
    existing_name: Optional[str] = None,
    base: Optional[ReportConfig] = None,
) -> str:
    """Validate and store a draft; returns the stored template's name.

    ``existing_name`` means "edit that template in place"; without it, saving
    over a template that already exists is refused.

    Raises:
        GuiError: with a user-facing message if the draft is invalid or the
            name is taken.

    """
    config = build_report_config(draft, base)
    try:
        path = manager.save_config(
            config, name=existing_name, force=existing_name is not None
        )
    except (TemplateAlreadyExistsError, TemplateValidationError) as e:
        raise GuiError(str(e)) from e
    return path.stem


def preview_query(
    draft: TemplateDraft,
    limit: int = PREVIEW_ROWS,
    base: Optional[ReportConfig] = None,
) -> QueryPreview:
    """Run the draft's query and return its first ``limit`` rows.

    Parameters take their default values; one that is required but has no
    default is reported, since there is nothing sensible to test with.
    Never writes: the connection is closed without committing, so even a
    mistyped UPDATE or DELETE is rolled back.

    Raises:
        GuiError: with a user-facing message if the query cannot be run.

    """
    url, query = draft.database_url.strip(), draft.query.strip()
    if not url or not query:
        raise GuiError("Enter the database URL and the SQL query first")
    schemas, parameter_problems = _parameter_schemas(draft.parameters)
    problems = parameter_problems + collect_errors(
        lambda: validate_database_url(url),
        lambda: validate_jinja2_syntax(query, "the query"),
    )
    if problems:
        raise GuiError("\n".join(problems))
    try:
        rendered = render_sql_query(query, process_parameters(schemas, None))
    except ValueError as e:
        raise GuiError(f"{e}. Give it a default value to test the query.") from e

    static = (base.data_source.parameters if base else None) or {}
    engine = create_engine(url)
    try:
        with engine.connect() as connection:
            result = connection.execute(text(rendered), static)
            if not result.returns_rows:
                raise GuiError("That statement does not return any rows")
            fetched = result.fetchmany(limit + 1)
            columns = list(result.keys())
    except (SQLAlchemyError, ImportError) as e:
        message = str(getattr(e, "orig", None) or e)
        raise GuiError(f"The query failed: {message}") from e
    finally:
        engine.dispose()

    logger.info(f"GUI query preview: {min(len(fetched), limit)} rows")
    return QueryPreview(
        columns=columns,
        rows=[["" if v is None else str(v) for v in row] for row in fetched[:limit]],
        truncated=len(fetched) > limit,
    )
