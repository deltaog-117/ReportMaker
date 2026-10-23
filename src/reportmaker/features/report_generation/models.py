"""Pydantic models for report configuration and results."""

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional, Union

from pydantic import BaseModel, Field, field_validator, model_validator


class OutputFormat(str, Enum):
    PDF = "pdf"
    HTML = "html"
    EXCEL = "excel"


class ChartKind(str, Enum):
    BAR = "bar"
    LINE = "line"


class ParameterType(str, Enum):
    STRING = "string"
    INTEGER = "integer"
    FLOAT = "float"
    DATE = "date"
    BOOLEAN = "boolean"


class ParameterSchema(BaseModel):
    """Definition of a dynamic parameter."""
    name: str = Field(..., description="Parameter name (used in template as {{ name }})")
    type: ParameterType = Field(..., description="Data type of the parameter")
    required: bool = Field(True, description="Whether the parameter must be provided")
    default: Optional[Any] = Field(None, description="Default value if not provided")
    description: Optional[str] = Field(None, description="Human-readable description")


class DataSourceConfig(BaseModel):
    """Configuration for a data source (database connection)."""
    url: str = Field(..., description="Database URL (SQLAlchemy format)")
    query: str = Field(..., description="SQL query to execute (may contain Jinja2 placeholders)")
    parameters: Optional[Dict[str, Any]] = Field(None, description="Static query parameters")


class TransformConfig(BaseModel):
    """Configuration for data transformation."""
    group_by: Optional[List[str]] = Field(None, description="Columns to group by")
    aggregations: Optional[Dict[str, str]] = Field(None, description="Column -> aggregation function (e.g., 'revenue': 'sum')")
    pivot: Optional[Dict[str, Any]] = Field(None, description="Pivot configuration (index, columns, values)")

    @field_validator("aggregations", mode="before")
    def validate_aggregations(cls, v):
        if v is not None:
            allowed = {"sum", "mean", "count", "min", "max", "std"}
            for col, func in v.items():
                if func not in allowed:
                    raise ValueError(f"Aggregation function '{func}' not allowed. Use one of {allowed}")
        return v


class ChartConfig(BaseModel):
    """Configuration for a chart."""
    kind: ChartKind = Field(..., description="Type of chart (bar or line)")
    x_column: str = Field(..., description="Column for the x-axis")
    y_column: str = Field(..., description="Column for the y-axis (or multiple columns)")
    title: Optional[str] = Field(None, description="Chart title")
    x_label: Optional[str] = None
    y_label: Optional[str] = None


class ReportConfig(BaseModel):
    """Full report configuration."""
    name: str = Field(..., description="Report name (used for output filename)")
    description: Optional[str] = None
    parameters: Optional[List[ParameterSchema]] = Field(None, description="Dynamic parameters definition")
    data_source: DataSourceConfig
    transform: Optional[TransformConfig] = None
    output: List[OutputFormat] = Field(
        default_factory=lambda: [OutputFormat.PDF],
        description="One format or a list of formats; each is rendered from the same data in a single run",
    )
    chart: Optional[ChartConfig] = None
    schedule: Optional[str] = Field(None, description="Cron expression (not used in core generation)")

    @field_validator("output", mode="before")
    def normalize_output(cls, v):
        """Accept ``output: pdf`` as shorthand for ``output: [pdf]``."""
        return [v] if isinstance(v, (str, OutputFormat)) else v

    @field_validator("output")
    def validate_output(cls, v):
        if not v:
            raise ValueError("output must list at least one format")
        # dict.fromkeys drops repeats but keeps order, so "pdf, pdf" renders once.
        return list(dict.fromkeys(v))

    @model_validator(mode="after")
    def validate_parameter_defaults(self):
        """Ensure default values match the declared type."""
        if self.parameters:
            for param in self.parameters:
                if param.default is not None:
                    # Basic type checking; Pydantic will cast if possible
                    if param.type == ParameterType.INTEGER:
                        try:
                            int(param.default)
                        except (ValueError, TypeError):
                            raise ValueError(f"Default for {param.name} must be an integer")
                    elif param.type == ParameterType.FLOAT:
                        try:
                            float(param.default)
                        except (ValueError, TypeError):
                            raise ValueError(f"Default for {param.name} must be a float")
                    elif param.type == ParameterType.DATE:
                        # We'll accept string or datetime; if string, try to parse
                        if isinstance(param.default, str):
                            try:
                                datetime.fromisoformat(param.default)
                            except ValueError:
                                raise ValueError(f"Default for {param.name} must be a date in ISO format (YYYY-MM-DD)")
                        elif not isinstance(param.default, datetime):
                            raise ValueError(f"Default for {param.name} must be a date (string or datetime)")
        return self


class ReportRequest(BaseModel):
    """Request to generate a report."""
    config: ReportConfig
    output_dir: str = Field(default="./reports", description="Directory to save output")
    parameters: Optional[Dict[str, Any]] = Field(None, description="Dynamic parameter overrides")


class ReportResult(BaseModel):
    """Result of a report generation run."""
    success: bool
    output_path: Optional[str] = Field(None, description="First generated file (kept for single-file callers)")
    output_paths: List[str] = Field(default_factory=list, description="Every generated file, one per format")
    error: Optional[str] = None
    metrics: Dict[str, Any] = Field(default_factory=dict)
    logs: List[str] = Field(default_factory=list)
    generated_at: datetime = Field(default_factory=datetime.utcnow)

    @model_validator(mode="after")
    def sync_output_paths(self):
        """Keep ``output_path`` and ``output_paths`` consistent whichever one was set."""
        if self.output_path and not self.output_paths:
            self.output_paths = [self.output_path]
        elif self.output_paths and not self.output_path:
            self.output_path = self.output_paths[0]
        return self
