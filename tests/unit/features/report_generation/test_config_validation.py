"""Unit tests for report configuration validation."""

import pytest

from reportmaker.features.report_generation.exceptions import ConfigError
from reportmaker.features.report_generation.models import ChartConfig, ChartKind, DataSourceConfig, ReportConfig
from reportmaker.features.report_generation.services import load_and_validate_config, validate_report_config_semantics


def _config(**overrides) -> ReportConfig:
    defaults = dict(
        name="Sales Report",
        data_source=DataSourceConfig(url="sqlite:///sales.db", query="SELECT 1"),
    )
    defaults.update(overrides)
    return ReportConfig(**defaults)


def test_valid_config_has_no_semantic_errors():
    assert validate_report_config_semantics(_config()) == []


def test_invalid_database_url_is_reported():
    config = _config(data_source=DataSourceConfig(url="not-a-url", query="SELECT 1"))
    errors = validate_report_config_semantics(config)
    assert any("database URL" in e for e in errors)


def test_broken_query_template_is_reported():
    config = _config(data_source=DataSourceConfig(url="sqlite:///sales.db", query="{% if %}"))
    errors = validate_report_config_semantics(config)
    assert any("Jinja2 syntax" in e for e in errors)


def test_empty_chart_column_is_reported():
    config = _config(chart=ChartConfig(kind=ChartKind.BAR, x_column="", y_column="revenue"))
    errors = validate_report_config_semantics(config)
    assert any("chart.x_column" in e for e in errors)


def test_load_and_validate_config_raises_config_error_for_malformed_yaml(tmp_path):
    config_path = tmp_path / "bad.yaml"
    config_path.write_text("name: Sales Report\ndata_source:\n  url: not-a-url\n  query: SELECT 1\n")

    with pytest.raises(ConfigError, match="database URL"):
        load_and_validate_config(str(config_path))


def test_load_and_validate_config_returns_config_for_valid_yaml(tmp_path):
    config_path = tmp_path / "good.yaml"
    config_path.write_text(
        "name: Sales Report\n"
        "data_source:\n"
        "  url: sqlite:///sales.db\n"
        "  query: SELECT 1\n"
    )

    config = load_and_validate_config(str(config_path))
    assert config.name == "Sales Report"
