"""Data transfer objects for template management."""

from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import List, Optional
from pydantic import BaseModel, Field


class VersionSource(str, Enum):
    """What replaced or removed the content a version holds."""
    SAVE = "save"
    IMPORT = "import"
    DELETE = "delete"
    ROLLBACK = "rollback"


class TemplateVersion(BaseModel):
    """One entry in a template's history."""
    version_id: str
    created_at: datetime
    source: VersionSource
    size_bytes: int


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
