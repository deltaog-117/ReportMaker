"""Unit tests for YAML configuration helpers."""

from datetime import date
from enum import Enum

from reportmaker.shared.config import load_yaml_config, save_yaml_config


class Colour(str, Enum):
    RED = "red"


def test_saved_enums_are_plain_values_that_safe_load_can_read(tmp_path):
    path = tmp_path / "config.yaml"

    save_yaml_config({"colour": Colour.RED, "nested": [{"colour": Colour.RED}]}, path)

    assert load_yaml_config(path) == {"colour": "red", "nested": [{"colour": "red"}]}


def test_saved_dates_are_iso_strings(tmp_path):
    path = tmp_path / "config.yaml"

    save_yaml_config({"start": date(2026, 9, 5)}, path)

    assert load_yaml_config(path) == {"start": "2026-09-05"}
