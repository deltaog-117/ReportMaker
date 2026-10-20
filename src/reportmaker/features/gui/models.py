"""Pydantic models for the GUI feature."""

from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import List, Optional

from pydantic import BaseModel, ConfigDict, Field, model_validator

from reportmaker.features.delivery.models import DeliveryResult
from reportmaker.features.report_generation.models import ReportResult

# The GUI can run arbitrary report SQL, so it must not be reachable from
# other machines unless the user explicitly asks for that.
LOOPBACK_HOSTS = frozenset({"127.0.0.1", "localhost", "::1"})


class GuiSettings(BaseModel):
    """Where the GUI listens and which folders it reads and writes."""

    host: str = Field("127.0.0.1", min_length=1)
    port: int = Field(8080, ge=1, le=65535)
    templates_dir: Path = Path("./templates")
    output_dir: Path = Path("./reports")
    schedules_file: Path = Path("./schedules.yaml")
    open_browser: bool = True

    @property
    def is_local_only(self) -> bool:
        """True when only this machine can reach the GUI."""
        return self.host in LOOPBACK_HOSTS


class OutputKind(str, Enum):
    """The kind of report file, used to decide whether it can be previewed."""

    PDF = "pdf"
    HTML = "html"
    EXCEL = "excel"
    OTHER = "other"


class OutputFile(BaseModel):
    """A generated report file found in the output directory."""

    name: str
    path: Path
    size_bytes: int = Field(ge=0)
    modified: datetime
    kind: OutputKind

    @property
    def is_previewable(self) -> bool:
        """Browsers can show PDF and HTML inline; Excel must be downloaded."""
        return self.kind in (OutputKind.PDF, OutputKind.HTML)


class RunOutcome(BaseModel):
    """What happened when a report was run from the GUI."""

    result: ReportResult
    delivery: Optional[DeliveryResult] = None

    @property
    def succeeded(self) -> bool:
        """True when the report file was generated."""
        return self.result.success


class Frequency(str, Enum):
    """Plain-language schedule choices, so users never have to write cron."""

    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"
    INTERVAL = "interval"
    CUSTOM = "custom"


# Names instead of numbers: APScheduler numbers weekdays from Monday=0 while
# classic cron starts on Sunday, so digits would mean different days.
class Weekday(str, Enum):
    """Days of the week, spelled the way cron expressions spell them."""

    MON = "mon"
    TUE = "tue"
    WED = "wed"
    THU = "thu"
    FRI = "fri"
    SAT = "sat"
    SUN = "sun"


class ScheduleRequest(BaseModel):
    """A schedule as the user describes it in the form."""

    model_config = ConfigDict(str_strip_whitespace=True)

    name: str = Field(..., min_length=1)
    report_config: str = Field(..., min_length=1)
    frequency: Frequency
    hour: int = Field(9, ge=0, le=23)
    minute: int = Field(0, ge=0, le=59)
    weekday: Weekday = Weekday.MON
    # Capped at 28 so "monthly" fires every month, including February.
    day_of_month: int = Field(1, ge=1, le=28)
    every_minutes: Optional[int] = Field(None, ge=1, le=10080)
    custom_cron: Optional[str] = None

    @model_validator(mode="after")
    def validate_frequency_fields(self) -> "ScheduleRequest":
        """Require the extra field each frequency needs."""
        if self.frequency == Frequency.INTERVAL and self.every_minutes is None:
            raise ValueError("Say how many minutes to wait between runs")
        if self.frequency == Frequency.CUSTOM and not (self.custom_cron or "").strip():
            raise ValueError("Enter a cron expression, or pick a simpler frequency")
        return self


class AggregationRow(BaseModel):
    """One 'column -> function' line of the grouping section."""

    column: str = ""
    function: str = "sum"


class ParameterRow(BaseModel):
    """One report parameter as typed into the editor (everything is text)."""

    name: str = ""
    type: str = "string"
    required: bool = True
    default: str = ""
    description: str = ""


class TemplateDraft(BaseModel):
    """A report definition as the editor form holds it.

    Plain strings throughout, so every widget can bind to a field directly;
    ``build_report_config`` is the single place they become typed values.
    An empty ``chart_kind`` means "no chart".
    """

    name: str = ""
    description: str = ""
    output: str = "pdf"
    database_url: str = ""
    query: str = ""
    chart_kind: str = ""
    chart_x: str = ""
    chart_y: str = ""
    chart_title: str = ""
    chart_x_label: str = ""
    chart_y_label: str = ""
    group_by: str = ""
    aggregations: List[AggregationRow] = Field(default_factory=list)
    pivot_index: str = ""
    pivot_columns: str = ""
    pivot_values: str = ""
    parameters: List[ParameterRow] = Field(default_factory=list)


class QueryPreview(BaseModel):
    """The first rows a query returned, rendered as text for display."""

    columns: List[str]
    rows: List[List[str]]
    truncated: bool = False
