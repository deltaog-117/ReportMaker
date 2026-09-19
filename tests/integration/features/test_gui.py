"""Integration tests: drive the real GUI pages with NiceGUI's simulated browser."""

import sqlite3
from pathlib import Path

import pytest
import yaml

pytest.importorskip("nicegui")

from nicegui import ui  # noqa: E402
from nicegui.testing import User  # noqa: E402

from reportmaker.features.gui.models import GuiSettings  # noqa: E402
from reportmaker.features.gui.pages import register_pages  # noqa: E402


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


async def test_templates_tab_lists_stored_templates(
    user: User, gui_settings: GuiSettings
) -> None:
    register_pages(gui_settings)
    await user.open("/")
    rows = [row for table in user.find(kind=ui.table).elements for row in table.rows]
    assert {"name": "sales", "description": "Sales by product"} in rows
