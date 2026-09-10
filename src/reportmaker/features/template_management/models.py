"""Data transfer objects for template management."""

from pathlib import Path
from typing import List, Optional
from pydantic import BaseModel, Field


class TemplateInfo(BaseModel):
    """Metadata about a stored template."""
    name: str
    path: Path
    description: Optional[str] = None


class TemplateImportResult(BaseModel):
    """Result of importing a spreadsheet template."""
    success: bool
    template_name: Optional[str] = None
    yaml_path: Optional[Path] = None
    errors: List[str] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)
