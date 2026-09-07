"""Pydantic models for report configuration and results."""

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional, Union

from pydantic import BaseModel, Field, field_validator


class OutputFormat(str, Enum):
    PDF = "pdf"
    HTML = "html"
    EXCEL = "excel"


class ChartKind(str, Enum):
    BAR = "bar"
    LINE = "line"


class DataSourceConfig(BaseModel):
    """Configuration for a data source (database connection)."""
    url: str = Field(..., description="Database URL (SQLAlchemy format)")
    query: str = Field(..., description="SQL query to execute")
    parameters: Optional[Dict[str, Any]] = Field(None, description="Query parameters")


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
    data_source: DataSourceConfig
    transform: Optional[TransformConfig] = None
    output: OutputFormat = OutputFormat.PDF
    chart: Optional[ChartConfig] = None
    schedule: Optional[str] = Field(None, description="Cron expression (not used in core generation)")


class ReportRequest(BaseModel):
    """Request to generate a report."""
    config: ReportConfig
    output_dir: str = Field(default="./reports", description="Directory to save output")
    parameters: Optional[Dict[str, Any]] = Field(None, description="Parameter overrides for the query")


class ReportResult(BaseModel):
    """Result of a report generation run."""
    success: bool
    output_path: Optional[str] = None
    error: Optional[str] = None
    metrics: Dict[str, Any] = Field(default_factory=dict)
    logs: List[str] = Field(default_factory=list)
    generated_at: datetime = Field(default_factory=datetime.utcnow)
