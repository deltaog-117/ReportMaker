"""Integration tests: drive the real GUI pages with NiceGUI's simulated browser."""

import asyncio
import sqlite3
from pathlib import Path

import pytest
import yaml

pytest.importorskip("nicegui")

from nicegui import ui  # noqa: E402
from nicegui.testing import User  # noqa: E402

from reportmaker.features.gui.models import GuiSettings  # noqa: E402
from reportmaker.features.gui.pages import register_pages  # noqa: E402
from reportmaker.features.template_management.services import TemplateManager  # noqa: E402


def make_sales_db(path: Path) -> None:
    with sqlite3.connect(path) as connection:
        connection.execute("CREATE TABLE sales (product TEXT, revenue REAL)")
        connection.executemany(
            "INSERT INTO sales VALUES (?, ?)", [("Widget", 10.0), ("Gadget", 25.5)]
        )


def write_template(templates_dir: Path, name: str, db: Path, query: str) -> None:
    templates_dir.mkdir(parents=True, exist_ok=True)
    config = {
        "name": name,
        "description": "Sales by product",
        "parameters": [
            {
                "name": "product",
                "type": "string",
                "required": True,
                "description": "Which product",
            }
        ],
        "data_source": {"url": f"sqlite:///{db}", "query": query},
        "output": "html",
    }
    (templates_dir / f"{name}.yaml").write_text(yaml.safe_dump(config))


@pytest.fixture
def gui_settings(tmp_path: Path) -> GuiSettings:
    db = tmp_path / "sales.db"
    make_sales_db(db)
    write_template(
        tmp_path / "templates",
        "sales",
        db,
        "SELECT product, revenue FROM sales WHERE product = '{{ product }}'",
    )
    return GuiSettings(
        templates_dir=tmp_path / "templates",
        output_dir=tmp_path / "reports",
        schedules_file=tmp_path / "schedules.yaml",
        open_browser=False,
    )


async def choose_report(user: User, name: str, marker: str = "run-report") -> None:
    user.find(marker=marker).click()
    user.find(name).click()


def table_row_names(user: User) -> list:
    return [
        row["name"] for table in user.find(kind=ui.table).elements for row in table.rows
    ]


async def eventually(check, timeout: float = 3.0) -> None:
    """Poll until check() is truthy; background work finishes after the click."""
    deadline = asyncio.get_running_loop().time() + timeout
    while not check():
        assert asyncio.get_running_loop().time() < deadline, "condition never became true"
        await asyncio.sleep(0.05)


def all_table_rows(user: User) -> list:
    return [row for table in user.find(kind=ui.table).elements for row in table.rows]


async def test_home_page_shows_every_tab(user: User, gui_settings: GuiSettings) -> None:
    register_pages(gui_settings)
    await user.open("/")
    for label in ("Run a report", "Past reports", "Schedules", "Templates"):
        await user.should_see(label)


async def test_choosing_a_report_shows_its_parameter_form(
    user: User, gui_settings: GuiSettings
) -> None:
    register_pages(gui_settings)
    await user.open("/")
    await choose_report(user, "sales")
    await user.should_see("Product *")
    await user.should_see("Which product")


async def test_running_a_report_produces_a_file_and_lists_it(
    user: User, gui_settings: GuiSettings
) -> None:
    register_pages(gui_settings)
    await user.open("/")
    await choose_report(user, "sales")
    user.find("Product *").type("Widget")
    user.find("Run report").click()

    await user.should_see("Your report is ready", retries=50)
    (generated,) = list(gui_settings.output_dir.glob("*.html"))
    assert "Widget" in generated.read_text()

    assert generated.name in table_row_names(user)


async def test_missing_required_value_is_explained_and_nothing_runs(
    user: User, gui_settings: GuiSettings
) -> None:
    register_pages(gui_settings)
    await user.open("/")
    await choose_report(user, "sales")
    user.find("Run report").click()

    await user.should_see("Product is required")
    assert not list(gui_settings.output_dir.glob("*"))


async def test_a_failing_report_shows_the_error_instead_of_crashing(
    user: User,
    tmp_path: Path,
    gui_settings: GuiSettings,
    caplog: pytest.LogCaptureFixture,
) -> None:
    write_template(
        gui_settings.templates_dir,
        "broken",
        tmp_path / "sales.db",
        "SELECT * FROM missing_table",
    )
    register_pages(gui_settings)
    await user.open("/")
    await choose_report(user, "broken")
    user.find("Product *").type("Widget")
    user.find("Run report").click()

    await user.should_see("The report could not be created", retries=50)
    await user.should_see("missing_table")
    # The pipeline logs this failure at ERROR on purpose; the user fixture would otherwise fail the test.
    caplog.clear()


async def test_adding_a_schedule_stores_it(
    user: User, gui_settings: GuiSettings
) -> None:
    register_pages(gui_settings)
    await user.open("/")
    user.find("Schedule name").type("nightly")
    await choose_report(user, "sales", marker="schedule-report")
    user.find("Product *").type("Widget")
    user.find("Add schedule").click()

    assert user.notify.contains("Schedule 'nightly' added.")
    stored = yaml.safe_load(gui_settings.schedules_file.read_text())["nightly"]
    assert stored["cron"] == "0 9 * * *"
    assert stored["parameters"] == {"product": "Widget"}


async def test_an_invalid_schedule_is_explained_and_not_saved(
    user: User, gui_settings: GuiSettings
) -> None:
    register_pages(gui_settings)
    await user.open("/")
    user.find("Schedule name").type("nightly")
    await choose_report(user, "sales", marker="schedule-report")
    user.find("Time of day (24h)").clear().type("25:00")
    user.find("Product *").type("Widget")
    user.find("Add schedule").click()

    assert user.notify.contains("Time must look like 09:30")
    assert not gui_settings.schedules_file.exists()


async def test_schedules_tab_shows_the_always_on_scheduler_banner(
    user: User, gui_settings: GuiSettings
) -> None:
    register_pages(gui_settings)
    await user.open("/")
    await user.should_see("runs automatically")


async def test_templates_tab_lists_stored_templates(
    user: User, gui_settings: GuiSettings
) -> None:
    register_pages(gui_settings)
    await user.open("/")
    rows = [row for table in user.find(kind=ui.table).elements for row in table.rows]
    assert {"name": "sales", "description": "Sales by product"} in rows


async def test_new_template_from_the_editor_is_stored_and_listed(
    user: User, gui_settings: GuiSettings
) -> None:
    register_pages(gui_settings)
    await user.open("/")
    user.find(marker="new-template").click()
    user.find(marker="editor-name").type("Fresh Report")
    user.find(marker="editor-url").type("sqlite:///fresh.db")
    user.find(marker="editor-query").type("SELECT 1 AS n")
    user.find(marker="editor-save").click()

    assert user.notify.contains("Template 'fresh_report' saved.")
    stored = yaml.safe_load((gui_settings.templates_dir / "fresh_report.yaml").read_text())
    assert stored["name"] == "Fresh Report"
    await eventually(lambda: "fresh_report" in table_row_names(user))


async def test_saving_an_incomplete_template_explains_what_is_missing(
    user: User, gui_settings: GuiSettings
) -> None:
    register_pages(gui_settings)
    await user.open("/")
    user.find(marker="new-template").click()
    user.find(marker="editor-save").click()

    assert user.notify.contains("Give the report a name")
    assert not (gui_settings.templates_dir / ".yaml").exists()


async def test_test_query_shows_the_first_rows(
    user: User, gui_settings: GuiSettings, tmp_path: Path
) -> None:
    register_pages(gui_settings)
    await user.open("/")
    user.find(marker="new-template").click()
    user.find(marker="editor-url").type(f"sqlite:///{tmp_path / 'sales.db'}")
    user.find(marker="editor-query").type("SELECT product FROM sales ORDER BY product")
    user.find(marker="editor-test").click()

    await eventually(
        lambda: {"c0": "Gadget"} in [
            {"c0": row["c0"]} for row in all_table_rows(user) if "c0" in row
        ]
    )


async def test_test_query_explains_a_failure(
    user: User, gui_settings: GuiSettings, tmp_path: Path
) -> None:
    register_pages(gui_settings)
    await user.open("/")
    user.find(marker="new-template").click()
    user.find(marker="editor-url").type(f"sqlite:///{tmp_path / 'sales.db'}")
    user.find(marker="editor-query").type("SELECT * FROM nowhere")
    user.find(marker="editor-test").click()

    await user.should_see("The query failed")


def press_row_button(user: User, event: str, name: str) -> None:
    """Fire a table's row-button event the way the browser would."""
    table = user.find(kind=ui.table).elements.pop()
    for listener_id, listener in table._event_listeners.items():
        if listener.type == event:
            table._handle_event({"listener_id": listener_id, "args": {"name": name}})


async def test_editing_a_template_prefills_the_form_and_saves_in_place(
    user: User, gui_settings: GuiSettings
) -> None:
    register_pages(gui_settings)
    await user.open("/")
    press_row_button(user, "edit", "sales")
    await user.should_see("Edit 'sales'")
    name = user.find(marker="editor-name").elements.pop()
    assert name.value == "sales"

    name.set_value("Sales Renamed")
    user.find(marker="editor-save").click()

    assert user.notify.contains("Template 'sales' saved.")
    stored = yaml.safe_load((gui_settings.templates_dir / "sales.yaml").read_text())
    assert stored["name"] == "Sales Renamed"
    assert stored["parameters"][0]["name"] == "product"
    assert [p.stem for p in gui_settings.templates_dir.glob("*.yaml")] == ["sales"]


def press_dialog_button(user: User, event: str, version_id: str) -> None:
    """Fire a row button of the version-history table (the one that has it)."""
    for table in user.find(kind=ui.table).elements:
        for listener_id, listener in table._event_listeners.items():
            if listener.type == event:
                table._handle_event(
                    {"listener_id": listener_id, "args": {"version_id": version_id}}
                )


async def test_version_history_dialog_compares_and_restores(
    user: User, gui_settings: GuiSettings
) -> None:
    register_pages(gui_settings)
    await user.open("/")
    path = gui_settings.templates_dir / "sales.yaml"
    original = path.read_bytes()
    press_row_button(user, "edit", "sales")
    await user.should_see("Edit 'sales'")
    user.find(marker="editor-name").elements.pop().set_value("Sales Renamed")
    user.find(marker="editor-save").click()
    assert user.notify.contains("Template 'sales' saved.")

    manager = TemplateManager(str(gui_settings.templates_dir))
    (version,) = manager.list_versions("sales")
    press_row_button(user, "versions", "sales")
    await user.should_see("Version history: sales")

    press_dialog_button(user, "compare", version.version_id)
    await user.should_see("Sales Renamed")

    press_dialog_button(user, "restore", version.version_id)
    assert user.notify.contains("Template 'sales' restored.")
    assert path.read_bytes() == original
