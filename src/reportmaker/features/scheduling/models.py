"""Pydantic models for schedules."""

from datetime import datetime
from typing import Any, Dict, Optional
from pydantic import BaseModel, Field, model_validator


class ScheduleConfig(BaseModel):
    """Definition of a scheduled report run."""
    name: str = Field(..., description="Unique name for the schedule")
    cron: Optional[str] = Field(None, description="Cron expression (e.g., '0 9 * * *')")
    interval_seconds: Optional[int] = Field(None, description="Interval in seconds (alternative to cron)")
    report_config: str = Field(..., description="Path to the YAML report config")
    parameters: Dict[str, Any] = Field(default_factory=dict, description="Dynamic parameters to pass")
    enabled: bool = Field(True, description="Whether the schedule is active")
    last_run: Optional[datetime] = Field(None, description="Timestamp of the last successful run")
    next_run: Optional[datetime] = Field(None, description="Timestamp of the next scheduled run")

    @model_validator(mode="after")
    def validate_trigger(self):
        """Ensure either cron or interval_seconds is set."""
        if not self.cron and not self.interval_seconds:
            raise ValueError("Either cron or interval_seconds must be provided")
        if self.cron and self.interval_seconds:
            raise ValueError("Provide only one of cron or interval_seconds")
        return self


class ScheduleStatus(BaseModel):
    """Status of a schedule (for listing)."""
    name: str
    enabled: bool
    trigger_type: str  # 'cron' or 'interval'
    trigger_value: str  # human-readable description
    last_run: Optional[datetime]
    next_run: Optional[datetime]
