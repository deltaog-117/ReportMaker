"""Configuration loading from environment and YAML files."""

import os
from pathlib import Path
from typing import Any

import yaml
from dotenv import load_dotenv

load_dotenv()


def load_yaml_config(path: str | Path) -> dict[str, Any]:
    """Load a YAML configuration file."""
    with open(path, "r") as f:
        return yaml.safe_load(f)


def get_env(key: str, default: str | None = None) -> str | None:
    """Get an environment variable."""
    return os.getenv(key, default)
