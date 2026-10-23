"""Unit and property tests for the GUI template editor logic."""

import sqlite3
from pathlib import Path

import pytest
import yaml
from hypothesis import given, settings
from hypothesis import strategies as st

from reportmaker.features.gui.exceptions import GuiError
from reportmaker.features.gui.models import (
    AggregationRow,
    ParameterRow,
    TemplateDraft,
)
from reportmaker.features.gui.services import (
    build_report_config,
    draft_from_config,
    load_template_draft,
    preview_query,
    save_template_draft,
)
from reportmaker.features.template_management.services import TemplateManager


def make_draft(db_url: str = "sqlite:///demo.db", **overrides) -> TemplateDraft:
    fields = {
        "name": "Demo",
        "database_url": db_url,
        "query": "SELECT 1 AS n",
        "output": ["html"],
    }
    fields.update(overrides)
    return TemplateDraft(**fields)


@pytest.fixture
def sales_db(tmp_path: Path) -> str:
    path = tmp_path / "sales.db"
    with sqlite3.connect(path) as conn:
        conn.execute("CREATE TABLE sales (region TEXT, amount REAL)")
        conn.executemany(
            "INSERT INTO sales VALUES (?, ?)",
            [("north", 10.0), ("south", None)] + [("east", float(i)) for i in range(40)],
        )
    return f"sqlite:///{path}"


# ---------- build_report_config ----------
def test_minimal_draft_builds_a_config():
    config = build_report_config(make_draft())
    assert config.name == "Demo"
    assert [f.value for f in config.output] == ["html"]
    assert config.chart is None and config.transform is None
    assert config.parameters is None


def test_full_draft_builds_every_section():
    draft = make_draft(
        chart_kind="bar",
        chart_x="region",
        chart_y="total",
        chart_title="Sales",
        group_by="region, product",
        aggregations=[AggregationRow(column="amount", function="SUM")],
        parameters=[
            ParameterRow(name="limit", type="integer", required=False, default="5"),
            ParameterRow(name="since", type="date", default="2026-01-01"),
        ],
    )
    config = build_report_config(draft)
    assert config.chart.kind.value == "bar" and config.chart.title == "Sales"
    assert config.transform.group_by == ["region", "product"]
    assert config.transform.aggregations == {"amount": "sum"}
    assert config.parameters[0].default == 5
    assert config.parameters[1].default == "2026-01-01"


def test_every_problem_is_reported_at_once():
    with pytest.raises(GuiError) as caught:
        build_report_config(TemplateDraft(chart_kind="bar"))
    message = str(caught.value)
    for fragment in ("name", "database URL", "SQL query", "X column"):
        assert fragment in message


@pytest.mark.parametrize(
    "overrides, fragment",
    [
        ({"chart_x": "region"}, "Pick a chart type"),
        ({"pivot_index": "region"}, "pivot needs"),
        (
            {"aggregations": [AggregationRow(column="a"), AggregationRow(column="a")]},
            "twice",
        ),
        (
            {"aggregations": [AggregationRow(column="a", function="median")]},
            "median",
        ),
        (
            {"parameters": [ParameterRow(name="n", type="integer", default="abc")]},
            "Parameter 'n'",
        ),
        (
            {"parameters": [ParameterRow(name="n"), ParameterRow(name="n")]},
            "listed twice",
        ),
        ({"parameters": [ParameterRow(name="", default="x")]}, "no name"),
        ({"query": "SELECT {{ broken"}, "Jinja2"),
        ({"database_url": "not a url"}, "database URL"),
        ({"output": ["docx"]}, "output"),
    ],
)
def test_invalid_drafts_are_rejected_with_a_clear_message(overrides, fragment):
    with pytest.raises(GuiError, match=fragment):
        build_report_config(make_draft(**overrides))


def test_blank_rows_are_ignored():
    draft = make_draft(
        aggregations=[AggregationRow(column="  ")],
        parameters=[ParameterRow(name="")],
    )
    config = build_report_config(draft)
    assert config.transform is None and config.parameters is None


def test_base_settings_without_form_fields_are_kept():
    base = build_report_config(make_draft())
    base = base.model_copy(
        update={
            "schedule": "0 9 * * *",
            "data_source": base.data_source.model_copy(update={"parameters": {"a": 1}}),
        }
    )
    edited = build_report_config(make_draft(name="Renamed"), base)
    assert edited.schedule == "0 9 * * *"
    assert edited.data_source.parameters == {"a": 1}


# ---------- round trip ----------
words = st.text(
    alphabet=st.characters(whitelist_categories=("Ll", "Lu", "Nd")),
    min_size=1,
    max_size=8,
)


@st.composite
def drafts(draw) -> TemplateDraft:
    with_chart = draw(st.booleans())
    with_pivot = draw(st.booleans())
    return make_draft(
        name=draw(words),
        description=draw(st.one_of(st.just(""), words)),
        output=draw(st.lists(st.sampled_from(["pdf", "html", "excel"]), min_size=1, unique=True)),
        chart_kind=draw(st.sampled_from(["bar", "line"])) if with_chart else "",
        chart_x=draw(words) if with_chart else "",
        chart_y=draw(words) if with_chart else "",
        chart_title=draw(st.one_of(st.just(""), words)) if with_chart else "",
        group_by=", ".join(draw(st.lists(words, max_size=3, unique=True))),
        aggregations=[
            AggregationRow(column=column, function=draw(st.sampled_from(["sum", "mean", "max"])))
            for column in draw(st.lists(words, max_size=3, unique=True))
        ],
        pivot_index=draw(words) if with_pivot else "",
        pivot_columns=draw(words) if with_pivot else "",
        pivot_values=draw(words) if with_pivot else "",
        parameters=[
            ParameterRow(
                name=name,
                type="string",
                required=draw(st.booleans()),
                default=draw(st.one_of(st.just(""), words)),
            )
            for name in draw(st.lists(words, max_size=3, unique=True))
        ],
    )


@given(drafts())
@settings(max_examples=100, deadline=None)
def test_draft_to_config_to_draft_is_stable(draft):
    config = build_report_config(draft)
    assert build_report_config(draft_from_config(config)) == config


# ---------- save / load ----------
def test_save_then_load_round_trips(tmp_path):
    manager = TemplateManager(str(tmp_path))
    draft = make_draft(group_by="region", chart_kind="line", chart_x="a", chart_y="b")
    name = save_template_draft(manager, draft)
    assert name == "demo"
    loaded, config = load_template_draft(manager, name)
    assert build_report_config(loaded) == build_report_config(draft)
    assert config.name == "Demo"


def test_new_template_refuses_to_overwrite(tmp_path):
    manager = TemplateManager(str(tmp_path))
    save_template_draft(manager, make_draft())
    with pytest.raises(GuiError, match="already exists"):
        save_template_draft(manager, make_draft())


def test_editing_keeps_the_file_when_the_report_is_renamed(tmp_path):
    manager = TemplateManager(str(tmp_path))
    save_template_draft(manager, make_draft())
    name = save_template_draft(manager, make_draft(name="Other Title"), "demo")
    assert name == "demo"
    assert [i.name for i in manager.list_templates()] == ["demo"]
    assert manager.validate_template("demo").name == "Other Title"


def test_editing_keeps_sections_the_form_does_not_know(tmp_path):
    manager = TemplateManager(str(tmp_path))
    save_template_draft(manager, make_draft())
    path = tmp_path / "demo.yaml"
    data = yaml.safe_load(path.read_text())
    data["delivery"] = {"channels": [{"type": "local", "directory": "out"}]}
    path.write_text(yaml.safe_dump(data))

    save_template_draft(manager, make_draft(description="edited"), "demo")

    saved = yaml.safe_load(path.read_text())
    assert saved["delivery"] == data["delivery"]
    assert saved["description"] == "edited"


def test_load_of_a_missing_template_is_a_gui_error(tmp_path):
    with pytest.raises(GuiError, match="not found"):
        load_template_draft(TemplateManager(str(tmp_path)), "nope")


def test_a_name_with_no_usable_characters_is_refused(tmp_path):
    with pytest.raises(GuiError, match="letters or digits"):
        save_template_draft(TemplateManager(str(tmp_path)), make_draft(name="///"))


# ---------- preview_query ----------
def test_preview_returns_columns_and_text_rows(sales_db):
    preview = preview_query(
        make_draft(sales_db, query="SELECT region, amount FROM sales ORDER BY rowid"),
        limit=3,
    )
    assert preview.columns == ["region", "amount"]
    assert preview.rows == [["north", "10.0"], ["south", ""], ["east", "0.0"]]
    assert preview.truncated is True


def test_preview_is_not_truncated_when_everything_fits(sales_db):
    preview = preview_query(make_draft(sales_db, query="SELECT 1 AS n"), limit=5)
    assert preview.rows == [["1"]] and preview.truncated is False


@given(st.integers(min_value=1, max_value=60))
@settings(max_examples=20, deadline=None)
def test_preview_never_returns_more_than_the_limit(limit):
    preview = preview_query(
        make_draft(
            query="WITH RECURSIVE c(x) AS (SELECT 1 UNION ALL SELECT x+1 FROM c LIMIT 50) "
            "SELECT x FROM c",
            database_url="sqlite://",
        ),
        limit=limit,
    )
    assert len(preview.rows) == min(limit, 50)
    assert preview.truncated == (limit < 50)


def test_preview_uses_parameter_defaults(sales_db):
    draft = make_draft(
        sales_db,
        query="SELECT region FROM sales WHERE region = '{{ where_to }}' LIMIT 1",
        parameters=[ParameterRow(name="where_to", default="north", required=False)],
    )
    assert preview_query(draft).rows == [["north"]]


def test_preview_explains_a_required_parameter_without_default(sales_db):
    draft = make_draft(
        sales_db,
        query="SELECT '{{ p }}'",
        parameters=[ParameterRow(name="p", required=True)],
    )
    with pytest.raises(GuiError, match="default value"):
        preview_query(draft)


def test_preview_never_writes(sales_db):
    with pytest.raises(GuiError):
        preview_query(make_draft(sales_db, query="DELETE FROM sales"))
    with sqlite3.connect(sales_db.removeprefix("sqlite:///")) as conn:
        assert conn.execute("SELECT COUNT(*) FROM sales").fetchone()[0] == 42


@pytest.mark.parametrize(
    "overrides, fragment",
    [
        ({"query": "SELECT * FROM missing_table"}, "The query failed"),
        ({"query": ""}, "Enter the database URL"),
        ({"database_url": "nonsense"}, "database URL"),
        ({"query": "SELECT {{ broken"}, "Jinja2"),
    ],
)
def test_preview_reports_problems_as_gui_errors(sales_db, overrides, fragment):
    with pytest.raises(GuiError, match=fragment):
        preview_query(make_draft(sales_db, **overrides))
