"""Configuration loading from environment and YAML files."""

import os
from datetime import datetime, date
from pathlib import Path
from typing import Any, Dict

import yaml
from dotenv import load_dotenv

load_dotenv()


def _normalize_for_yaml(obj: Any) -> Any:
    """Recursively convert non-YAML-native types to strings."""
    if isinstance(obj, dict):
        return {k: _normalize_for_yaml(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_normalize_for_yaml(v) for v in obj]
    if isinstance(obj, (datetime, date)):
        return obj.isoformat()
    return obj


def load_yaml_config(path: str | Path) -> Dict[str, Any]:
    """Load a YAML configuration file."""
    with open(path, "r") as f:
        return yaml.safe_load(f)


def save_yaml_config(data: Dict[str, Any], path: str | Path) -> None:
    """Save data to a YAML file, normalising non-native types to strings."""
    normalized = _normalize_for_yaml(data)
    with open(path, "w") as f:
        yaml.dump(normalized, f, default_flow_style=False, sort_keys=False)


def get_env(key: str, default: str | None = None) -> str | None:
    """Get an environment variable."""
    return os.getenv(key, default)
