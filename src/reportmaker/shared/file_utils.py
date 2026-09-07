"""File I/O helpers."""

import os
from pathlib import Path
from typing import Optional


def ensure_directory(path: str | Path) -> Path:
    """Ensure a directory exists, creating it if necessary."""
    p = Path(path)
    p.mkdir(parents=True, exist_ok=True)
    return p


def safe_filename(name: str) -> str:
    """Generate a safe filename from a string."""
    return "".join(c if c.isalnum() or c in "._- " else "_" for c in name).strip()
