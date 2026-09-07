"""Unit and property-based tests for report generation services."""

import pandas as pd
import pytest
from hypothesis import given, strategies as st
from unittest.mock import MagicMock, patch

from reportmaker.features.report_generation.services import PandasTransformer, SQLAlchemyExtractor, PDFRenderer
from reportmaker.features.report_generation.models import ReportConfig, TransformConfig, DataSourceConfig, ChartConfig, ChartKind
from reportmaker.features.report_generation.exceptions import DataTransformationError


# ---------- Transformer Tests ----------
def test_pandas_transformer_no_transform():
    df = pd.DataFrame({"a": [1, 2], "b": [3, 4]})
    config = ReportConfig(name="test", data_source=DataSourceConfig(url="", query=""))
    transformer = PandasTransformer()
    result = transformer.transform(df, config)
    assert result.equals(df)


def test_pandas_transformer_groupby_sum():
    df = pd.DataFrame({"product": ["A", "A", "B"], "revenue": [10, 20, 30]})
    config = ReportConfig(
        name="test",
        data_source=DataSourceConfig(url="", query=""),
        transform=TransformConfig(group_by=["product"], aggregations={"revenue": "sum"})
    )
    transformer = PandasTransformer()
    result = transformer.transform(df, config)
    expected = pd.DataFrame({"product": ["A", "B"], "revenue": [30, 30]})
    assert result.equals(expected)


def test_pandas_transformer_invalid_aggregation():
    df = pd.DataFrame({"product": ["A"], "revenue": [10]})
    config = ReportConfig(
        name="test",
        data_source=DataSourceConfig(url="", query=""),
        transform=TransformConfig(group_by=["product"], aggregations={"revenue": "invalid"})
    )
    transformer = PandasTransformer()
    # The transformer doesn't validate, it just passes to pandas; we expect pandas to raise an error.
    # But we have validation in the model, so this shouldn't happen. We'll test with a valid but wrong function.
    # For actual error, we can use a non-existent function:
    with pytest.raises(DataTransformationError):
        # Override aggregations to force a bad function
        config.transform.aggregations = {"revenue": "non_existent"}
        transformer.transform(df, config)


# Property-based test: transform should preserve certain properties
@given(st.lists(st.tuples(st.text(), st.integers()), min_size=1))
def test_groupby_preserves_total_sum(data):
    """After grouping by product and summing revenue, total sum should be preserved."""
    df = pd.DataFrame(data, columns=["product", "revenue"])
    config = ReportConfig(
        name="test",
        data_source=DataSourceConfig(url="", query=""),
        transform=TransformConfig(group_by=["product"], aggregations={"revenue": "sum"})
    )
    transformer = PandasTransformer()
    original_total = df["revenue"].sum()
    result = transformer.transform(df, config)
    result_total = result["revenue"].sum()
    assert abs(original_total - result_total) < 1e-9  # floating point tolerance


# ---------- Extractor Tests (mocked) ----------
def test_sqlalchemy_extractor_success():
    with patch("reportmaker.features.report_generation.services.get_engine") as mock_engine:
        mock_conn = MagicMock()
        mock_engine.return_value.connect.return_value.__enter__.return_value = mock_conn
        mock_conn.execute.return_value = MagicMock()
        # Mock pd.read_sql to return a DataFrame
        with patch("pandas.read_sql") as mock_read_sql:
            df = pd.DataFrame({"col": [1, 2]})
            mock_read_sql.return_value = df
            extractor = SQLAlchemyExtractor()
            config = ReportConfig(name="test", data_source=DataSourceConfig(url="", query="SELECT 1"))
            result = extractor.extract(config)
            assert result.equals(df)


# ---------- Renderer Tests (sanity check) ----------
def test_pdf_renderer_creates_file(tmp_path):
    df = pd.DataFrame({"Product": ["A", "B"], "Sales": [100, 200]})
    config = ReportConfig(
        name="Test Report",
        data_source=DataSourceConfig(url="", query=""),
        chart=ChartConfig(kind=ChartKind.BAR, x_column="Product", y_column="Sales")
    )
    output_path = tmp_path / "test.pdf"
    renderer = PDFRenderer()
    result = renderer.render(df, config, str(output_path))
    assert output_path.exists()
    assert result == str(output_path)
