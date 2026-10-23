"""Unit tests for running one report in several output formats."""

import sqlite3
from pathlib import Path

import pytest
from hypothesis import given, strategies as st
from pydantic import ValidationError

from reportmaker.features.report_generation.models import (
    OutputFormat,
    ReportConfig,
    ReportResult,
)
from reportmaker.features.report_generation.services import (
    ReportPipeline,
    SQLAlchemyExtractor,
    PandasTransformer,
    create_default_pipeline,
)
from reportmaker.features.report_generation.models import ReportRequest

SOURCE = {"url": "sqlite:///demo.db", "query": "SELECT 1"}


def make_config(output) -> ReportConfig:
    return ReportConfig(name="Demo", data_source=SOURCE, output=output)


# ---------- config model ----------
def test_a_single_format_is_wrapped_in_a_list():
    assert make_config("html").output == [OutputFormat.HTML]


def test_a_list_of_formats_is_kept_in_order():
    config = make_config(["excel", "pdf"])
    assert config.output == [OutputFormat.EXCEL, OutputFormat.PDF]


def test_repeated_formats_render_once():
    assert make_config(["pdf", "html", "pdf"]).output == [OutputFormat.PDF, OutputFormat.HTML]


def test_default_output_is_pdf():
    config = ReportConfig(name="Demo", data_source=SOURCE)
    assert config.output == [OutputFormat.PDF]


@pytest.mark.parametrize("bad", [[], ["docx"], ["pdf", "docx"]])
def test_empty_or_unknown_formats_are_rejected(bad):
    with pytest.raises(ValidationError):
        make_config(bad)


@given(st.lists(st.sampled_from(list(OutputFormat)), min_size=1, max_size=8))
def test_output_is_never_empty_and_never_repeats(formats):
    config = make_config(formats)
    assert config.output and len(config.output) == len(set(config.output))
    assert set(config.output) == set(formats)


# ---------- result model ----------
def test_result_with_only_output_path_fills_output_paths():
    assert ReportResult(success=True, output_path="a.pdf").output_paths == ["a.pdf"]


def test_result_with_only_output_paths_fills_output_path_with_the_first():
    result = ReportResult(success=True, output_paths=["a.pdf", "a.html"])
    assert result.output_path == "a.pdf"


# ---------- pipeline ----------
@pytest.fixture
def demo_db(tmp_path: Path) -> str:
    path = tmp_path / "demo.db"
    with sqlite3.connect(path) as conn:
        conn.execute("CREATE TABLE sales (product TEXT, revenue REAL)")
        conn.executemany("INSERT INTO sales VALUES (?, ?)", [("a", 1.0), ("b", 2.0)])
    return f"sqlite:///{path}"


def run_pipeline(db_url, output, out_dir):
    config = ReportConfig(
        name="Demo",
        data_source={"url": db_url, "query": "SELECT * FROM sales"},
        output=output,
    )
    pipeline = create_default_pipeline(config.output)
    return pipeline.run(ReportRequest(config=config, output_dir=str(out_dir)))


def test_one_run_writes_one_file_per_format(demo_db, tmp_path):
    result = run_pipeline(demo_db, ["pdf", "html", "excel"], tmp_path / "out")

    assert result.success, result.error
    assert [Path(p).suffix for p in result.output_paths] == [".pdf", ".html", ".excel"]
    assert all(Path(p).is_file() for p in result.output_paths)
    assert result.output_path == result.output_paths[0]
    assert result.metrics["output_formats"] == ["pdf", "html", "excel"]


def test_every_format_shares_one_timestamp(demo_db, tmp_path):
    result = run_pipeline(demo_db, ["pdf", "html"], tmp_path / "out")
    assert len({Path(p).stem for p in result.output_paths}) == 1


def test_a_single_format_still_yields_one_file(demo_db, tmp_path):
    result = run_pipeline(demo_db, "html", tmp_path / "out")
    assert len(result.output_paths) == 1 and result.output_path == result.output_paths[0]


def test_data_is_extracted_once_for_all_formats(demo_db, tmp_path):
    calls = []

    class CountingExtractor(SQLAlchemyExtractor):
        def extract(self, config, parameters):
            calls.append(1)
            return super().extract(config, parameters)

    config = ReportConfig(
        name="Demo",
        data_source={"url": demo_db, "query": "SELECT * FROM sales"},
        output=["pdf", "html"],
    )
    base = create_default_pipeline(config.output)
    pipeline = ReportPipeline(CountingExtractor(), PandasTransformer(), base.renderers)
    result = pipeline.run(ReportRequest(config=config, output_dir=str(tmp_path / "out")))

    assert result.success and len(calls) == 1
