"""Unit tests for report models."""

import pytest
from pydantic import ValidationError

from reportmaker.features.report_generation.models import ReportConfig, TransformConfig, ChartConfig, ChartKind, OutputFormat, DataSourceConfig


def test_valid_report_config():
    config = ReportConfig(
        name="Test Report",
        data_source=DataSourceConfig(url="sqlite:///test.db", query="SELECT * FROM sales"),
        output=OutputFormat.PDF,
        chart=ChartConfig(kind=ChartKind.BAR, x_column="product", y_column="revenue"),
    )
    assert config.name == "Test Report"


def test_invalid_aggregation():
    with pytest.raises(ValidationError) as exc_info:
        TransformConfig(aggregations={"revenue": "invalid_func"})
    assert "Aggregation function 'invalid_func' not allowed" in str(exc_info.value)


def test_valid_aggregation():
    tf = TransformConfig(aggregations={"revenue": "sum", "count": "count"})
    assert tf.aggregations["revenue"] == "sum"
