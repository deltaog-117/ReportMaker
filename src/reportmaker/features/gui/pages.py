"""NiceGUI pages: the browser front-end for ReportMaker.

All decisions live in ``services`` and ``parameters``; this module only
lays out widgets and wires them to those functions.
"""

from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Sequence
from urllib.parse import quote

import matplotlib
from nicegui import app, events, run, ui

from reportmaker.features.delivery.models import DeliveryChannel
from reportmaker.features.gui.exceptions import GuiError, ParameterInputError
from reportmaker.features.gui.models import (
    AggregationRow,
    Frequency,
    GuiSettings,
    OutputFile,
    ParameterRow,
    QueryPreview,
    RunOutcome,
    ScheduleRequest,
    TemplateDraft,
    Weekday,
)
from reportmaker.features.gui.parameters import build_parameters, field_label
from reportmaker.features.gui.services import (
    blank_template_bytes,
    create_schedule,
    deliver_after_schedule_run,
    export_template_bytes,
    format_size,
    import_uploaded_template,
    list_output_files,
    load_template_draft,
    parse_time_of_day,
    preview_query,
    run_report_with_delivery,
    save_template_draft,
)
from reportmaker.features.report_generation.models import ParameterSchema, ParameterType
from reportmaker.features.scheduling.exceptions import ScheduleNotFoundError
from reportmaker.features.scheduling.models import RunRecord
from reportmaker.features.scheduling.services import SchedulerService
from reportmaker.features.template_management.exceptions import (
    TemplateNotFoundError,
    TemplateValidationError,
)
from reportmaker.features.template_management.models import TemplateInfo
from reportmaker.features.template_management.services import TemplateManager
from reportmaker.shared.file_utils import ensure_directory
from reportmaker.shared.logging import get_logger

logger = get_logger(__name__)

REPORTS_URL = "/generated"
_TIME_FREQUENCIES = (
    Frequency.DAILY.value,
    Frequency.WEEKLY.value,
    Frequency.MONTHLY.value,
)
_TRUE_WORDS = ("true", "1", "yes", "on")
_OUTPUT_CHOICES = {"pdf": "PDF", "html": "HTML page", "excel": "Excel"}
_CHART_CHOICES = {"": "No chart", "bar": "Bar chart", "line": "Line chart"}
_AGGREGATION_FUNCTIONS = ["sum", "mean", "count", "min", "max", "std"]
_PARAMETER_TYPES = [kind.value for kind in ParameterType]

_ACTION_SLOT = """
<q-td :props="props" auto-width>
  {buttons}
</q-td>
"""

_TOGGLE_SLOT = """
<q-td :props="props" auto-width>
  <q-toggle :model-value="props.row.enabled" @update:model-value="val =>
    $parent.$emit('toggle', {name: props.row.name, enabled: val})" />
</q-td>
"""


def _action_button(event: str, icon: str, tooltip: str, condition: str = "") -> str:
    guard = f' v-if="{condition}"' if condition else ""
    return (
        f'<q-btn{guard} flat dense round icon="{icon}" '
        f"@click=\"() => $parent.$emit('{event}', props.row)\">"
        f"<q-tooltip>{tooltip}</q-tooltip></q-btn>"
    )


def _initial_text(default: Any) -> str:
    if default is None:
        return ""
    if hasattr(default, "isoformat"):
        return str(default.isoformat())[:10]
    return str(default)


def _initial_number(default: Any) -> Optional[float]:
    try:
        return float(default)
    except (TypeError, ValueError):
        return None


class ParameterForm:
    """A block of inputs generated from a report's declared parameters."""

    def __init__(self) -> None:
        """Create an empty form; call show() to fill it."""
        self._container = ui.column().classes("w-full gap-2")
        self._schemas: List[ParameterSchema] = []
        self._getters: Dict[str, Callable[[], Any]] = {}

    def show(self, schemas: Sequence[ParameterSchema]) -> None:
        """Replace the inputs with ones for these parameters."""
        self._container.clear()
        self._schemas = list(schemas)
        self._getters = {}
        with self._container:
            for schema in self._schemas:
                self._getters[schema.name] = self._add_field(schema)

    def collect(self) -> Dict[str, Any]:
        """Read and validate the current values.

        Raises:
            ParameterInputError: listing every field that is unusable.

        """
        raw = {name: getter() for name, getter in self._getters.items()}
        return build_parameters(self._schemas, raw)

    def _add_field(self, schema: ParameterSchema) -> Callable[[], Any]:
        needs_value = schema.required and schema.default is None
        label = field_label(schema.name) + (" *" if needs_value else "")
        if schema.type == ParameterType.BOOLEAN:
            default_on = str(schema.default).strip().lower() in _TRUE_WORDS
            widget: Any = ui.switch(label, value=default_on)
        elif schema.type in (ParameterType.INTEGER, ParameterType.FLOAT):
            widget = ui.number(
                label,
                value=_initial_number(schema.default),
                precision=0 if schema.type == ParameterType.INTEGER else None,
            ).classes("w-full")
        elif schema.type == ParameterType.DATE:
            widget = self._date_input(label, _initial_text(schema.default))
        else:
            widget = ui.input(label, value=_initial_text(schema.default)).classes(
                "w-full"
            )
        if schema.description:
            ui.label(schema.description).classes("text-caption text-grey")
        return lambda: widget.value

    @staticmethod
    def _date_input(label: str, value: str) -> ui.input:
        with ui.input(label, value=value, placeholder="YYYY-MM-DD").classes(
            "w-full"
        ) as date_input:
            with ui.menu().props("no-parent-event") as menu:
                with ui.date().bind_value(date_input):
                    with ui.row().classes("justify-end"):
                        ui.button("Close", on_click=menu.close).props("flat")
            with date_input.add_slot("append"):
                ui.icon("edit_calendar").on("click", menu.open).classes(
                    "cursor-pointer"
                )
        return date_input


class _Dashboard:
    """One browser tab's view of the app. A new instance is built per visit."""

    def __init__(self, settings: GuiSettings, scheduler: SchedulerService) -> None:
        """Bind the dashboard to the folders, files, and scheduler named in settings."""
        self._settings = settings
        self._scheduler = scheduler
        self._manager = TemplateManager(str(settings.templates_dir))
        self._template_selects: List[ui.select] = []

    # ---------- Layout ----------
    def build(self) -> None:
        """Lay out the header and the four tabs."""
        with ui.header().classes("items-center gap-2"):
            ui.icon("assessment", size="md")
            ui.label("ReportMaker").classes("text-h6")
        with ui.column().classes("w-full max-w-4xl mx-auto"):
            with ui.tabs().classes("w-full") as tabs:
                run_tab = ui.tab("Run a report", icon="play_arrow")
                history_tab = ui.tab("Past reports", icon="history")
                schedules_tab = ui.tab("Schedules", icon="schedule")
                templates_tab = ui.tab("Templates", icon="description")
            with ui.tab_panels(tabs, value=run_tab).classes("w-full"):
                with ui.tab_panel(run_tab):
                    self._run_panel()
                with ui.tab_panel(history_tab):
                    self._history_panel()
                with ui.tab_panel(schedules_tab):
                    self._schedules_panel()
                with ui.tab_panel(templates_tab):
                    self._templates_panel()

    # ---------- Shared helpers ----------
    def _templates_by_name(self) -> Dict[str, TemplateInfo]:
        return {info.name: info for info in self._manager.list_templates()}

    def _template_select(self, label: str, marker: str) -> ui.select:
        select = ui.select(
            options=list(self._templates_by_name()), label=label
        ).classes("w-full")
        select.mark(marker)
        self._template_selects.append(select)
        return select

    def _refresh_template_choices(self) -> None:
        names = list(self._templates_by_name())
        for select in self._template_selects:
            keep = select.value if select.value in names else None
            select.set_options(names, value=keep)

    def _load_parameters(
        self, name: Optional[str]
    ) -> Optional[Sequence[ParameterSchema]]:
        """Return a template's parameters, or None if unusable (the user is told)."""
        if not name:
            return None
        try:
            return self._manager.validate_template(name).parameters or []
        except (TemplateNotFoundError, TemplateValidationError) as e:
            ui.notify(str(e), type="negative", multi_line=True)
            return None

    @staticmethod
    def _download_file(path: Path) -> None:
        ui.download.file(path)

    def _preview(self, output: OutputFile) -> None:
        url = f"{REPORTS_URL}/{quote(output.name)}"
        with ui.dialog() as dialog, ui.card().classes("w-[90vw] max-w-5xl"):
            ui.label(output.name).classes("text-h6")
            ui.element("iframe").props(f'src="{url}"').classes("w-full").style(
                "height: 70vh; border: 0"
            )
            ui.button("Close", on_click=dialog.close).props("flat")
        dialog.on("hide", dialog.delete)
        dialog.open()

    # ---------- Run a report ----------
    def _run_panel(self) -> None:
        ui.label("Pick a report, fill in the details, then press Run.").classes(
            "text-subtitle1"
        )
        select = self._template_select("Choose a report", "run-report")
        form = ParameterForm()
        problems = ui.column().classes("w-full")
        button = ui.button("Run report", icon="play_arrow")
        result_area = ui.column().classes("w-full")

        def on_select() -> None:
            problems.clear()
            result_area.clear()
            form.show(self._load_parameters(select.value) or [])

        select.on_value_change(on_select)

        async def on_run() -> None:
            name = select.value
            info = self._templates_by_name().get(name or "")
            if info is None:
                ui.notify("Choose a report first.", type="warning")
                return
            problems.clear()
            try:
                parameters = form.collect()
            except ParameterInputError as e:
                with problems:
                    for field, message in e.errors.items():
                        ui.label(f"{field_label(field)} {message}").classes(
                            "text-negative"
                        )
                return
            result_area.clear()
            button.disable()
            with result_area:
                ui.spinner(size="lg")
                ui.label("Generating your report...")
            outcome = await run.io_bound(
                run_report_with_delivery,
                str(info.path),
                self._settings.output_dir,
                parameters,
            )
            button.enable()
            result_area.clear()
            if outcome is None:
                return
            with result_area:
                self._render_outcome(outcome)
            self._history.refresh()

        button.on_click(on_run)

    def _render_outcome(self, outcome: RunOutcome) -> None:
        if not outcome.succeeded:
            with ui.row().classes("items-center"):
                ui.icon("error", color="negative", size="md")
                ui.label("The report could not be created").classes("text-h6")
            ui.label(outcome.result.error or "Unknown error").classes(
                "whitespace-pre-wrap text-negative"
            )
            return

        result = outcome.result
        with ui.row().classes("items-center"):
            ui.icon("check_circle", color="positive", size="md")
            ui.label("Your report is ready").classes("text-h6")
        metrics = result.metrics
        ui.label(
            f"{metrics.get('transform_rows', '?')} rows, "
            f"created in {metrics.get('duration_seconds', 0):.1f}s"
        ).classes("text-grey")
        files = list_output_files(self._settings.output_dir)
        for output_path in result.output_paths:
            path = Path(output_path)
            output = next((f for f in files if f.name == path.name), None)
            with ui.row().classes("items-center"):
                if len(result.output_paths) > 1:
                    ui.label(path.name).classes("text-grey")
                # Default args pin this iteration's path; a bare closure would
                # see the last one for every button.
                ui.button(
                    "Download",
                    icon="download",
                    on_click=lambda p=path: self._download_file(p),
                )
                if output is not None and output.is_previewable:
                    ui.button(
                        "Preview",
                        icon="visibility",
                        on_click=lambda o=output: self._preview(o),
                    ).props("outline")
        delivery = outcome.delivery
        if delivery is not None and delivery.channel != DeliveryChannel.NONE:
            if delivery.success:
                ui.label(
                    f"Also sent via {delivery.channel.value}: {delivery.destination}"
                )
            else:
                ui.label(
                    f"The report was made, but sending failed: {delivery.error}"
                ).classes("text-warning whitespace-pre-wrap")

    # ---------- Past reports ----------
    def _history_panel(self) -> None:
        ui.label("Everything you have generated, newest first.").classes(
            "text-subtitle1"
        )
        self._history()

    @ui.refreshable
    def _history(self) -> None:
        files = list_output_files(self._settings.output_dir)
        if not files:
            ui.label("No reports yet. Run one and it will show up here.").classes(
                "text-grey"
            )
            return
        by_name = {f.name: f for f in files}
        rows = [
            {
                "name": f.name,
                "type": f.kind.value.upper(),
                "size": format_size(f.size_bytes),
                "modified": f.modified.strftime("%Y-%m-%d %H:%M"),
                "previewable": f.is_previewable,
            }
            for f in files
        ]
        columns = [
            {"name": "name", "label": "Report", "field": "name", "align": "left"},
            {"name": "type", "label": "Type", "field": "type", "align": "left"},
            {"name": "size", "label": "Size", "field": "size", "align": "right"},
            {
                "name": "modified",
                "label": "Created",
                "field": "modified",
                "align": "left",
            },
            {"name": "actions", "label": "", "field": "name"},
        ]
        table = ui.table(columns=columns, rows=rows, row_key="name").classes("w-full")
        buttons = _action_button(
            "preview", "visibility", "Preview", "props.row.previewable"
        )
        buttons += _action_button("download", "download", "Download")
        table.add_slot("body-cell-actions", _ACTION_SLOT.format(buttons=buttons))

        def with_output(
            handler: Callable[[OutputFile], None],
        ) -> Callable[[events.GenericEventArguments], None]:
            def wrapper(e: events.GenericEventArguments) -> None:
                # Only ever act on files we listed ourselves; the row name
                # comes from the browser and must not be trusted as a path.
                output = by_name.get(e.args.get("name", ""))
                if output is not None:
                    handler(output)

            return wrapper

        table.on("preview", with_output(self._preview))
        table.on(
            "download", with_output(lambda output: self._download_file(output.path))
        )

    # ---------- Schedules ----------
    def _schedules_panel(self) -> None:
        ui.label("Have a report run by itself on a schedule.").classes("text-subtitle1")
        ui.label(
            "The scheduler runs automatically while this app is open — "
            "no separate command needed."
        ).classes("bg-green-1 text-green-10 q-pa-sm rounded")
        self._schedule_list()
        self._schedule_form()

    @ui.refreshable
    def _schedule_list(self) -> None:
        statuses = self._scheduler.list_schedules()
        if not statuses:
            ui.label("No schedules yet.").classes("text-grey")
            return
        rows = [
            {
                "name": s.name,
                "when": s.trigger_value,
                "last_run": s.last_run.strftime("%Y-%m-%d %H:%M")
                if s.last_run
                else "Never",
                "enabled": s.enabled,
            }
            for s in statuses
        ]
        columns = [
            {"name": "name", "label": "Name", "field": "name", "align": "left"},
            {"name": "when", "label": "When", "field": "when", "align": "left"},
            {
                "name": "last_run",
                "label": "Last run",
                "field": "last_run",
                "align": "left",
            },
            {
                "name": "enabled",
                "label": "Enabled",
                "field": "enabled",
                "align": "center",
            },
            {"name": "actions", "label": "", "field": "name"},
        ]
        table = ui.table(columns=columns, rows=rows, row_key="name").classes("w-full")
        table.add_slot("body-cell-enabled", _TOGGLE_SLOT)
        buttons = _action_button("history", "history", "View run history")
        buttons += _action_button("remove", "delete", "Remove")
        table.add_slot("body-cell-actions", _ACTION_SLOT.format(buttons=buttons))
        table.on(
            "remove", lambda e: self._confirm_remove_schedule(e.args.get("name", ""))
        )
        table.on("history", lambda e: self._show_run_history(e.args.get("name", "")))
        table.on("toggle", self._on_toggle_schedule)

    def _on_toggle_schedule(self, e: events.GenericEventArguments) -> None:
        name = e.args.get("name", "")
        enabled = bool(e.args.get("enabled"))
        try:
            self._scheduler.set_enabled(name, enabled)
        except ScheduleNotFoundError as err:
            ui.notify(str(err), type="warning")
        self._schedule_list.refresh()

    def _show_run_history(self, name: str) -> None:
        records: List[RunRecord] = self._scheduler.list_run_history(name, limit=20)
        with ui.dialog() as dialog, ui.card().classes("w-full max-w-2xl"):
            ui.label(f"Run history: {name}").classes("text-h6")
            if not records:
                ui.label("No runs recorded yet.").classes("text-grey")
            else:
                rows = [
                    {
                        "started_at": r.started_at.strftime("%Y-%m-%d %H:%M"),
                        "outcome": "Success" if r.success else "Failed",
                        "duration": f"{r.duration_seconds:.1f}s",
                        "detail": r.output_path if r.success else (r.error or ""),
                    }
                    for r in records
                ]
                columns = [
                    {
                        "name": "started_at",
                        "label": "Started",
                        "field": "started_at",
                        "align": "left",
                    },
                    {
                        "name": "outcome",
                        "label": "Outcome",
                        "field": "outcome",
                        "align": "left",
                    },
                    {
                        "name": "duration",
                        "label": "Duration",
                        "field": "duration",
                        "align": "right",
                    },
                    {
                        "name": "detail",
                        "label": "Detail",
                        "field": "detail",
                        "align": "left",
                    },
                ]
                ui.table(
                    columns=columns, rows=rows, row_key="started_at"
                ).classes("w-full")
            ui.button("Close", on_click=dialog.close).props("flat")
        dialog.on("hide", dialog.delete)
        dialog.open()

    def _confirm_remove_schedule(self, name: str) -> None:
        def remove() -> None:
            try:
                self._scheduler.remove_schedule(name)
            except ScheduleNotFoundError as e:
                ui.notify(str(e), type="warning")
            dialog.close()
            self._schedule_list.refresh()

        with ui.dialog() as dialog, ui.card():
            ui.label(f"Remove the schedule '{name}'?")
            with ui.row():
                ui.button("Cancel", on_click=dialog.close).props("flat")
                ui.button("Remove", on_click=remove, color="negative")
        dialog.on("hide", dialog.delete)
        dialog.open()

    def _schedule_form(self) -> None:
        with ui.card().classes("w-full"):
            ui.label("Add a schedule").classes("text-h6")
            name = ui.input("Schedule name").classes("w-full")
            report = self._template_select("Report to run", "schedule-report")
            frequency = ui.select(
                {
                    Frequency.DAILY.value: "Every day",
                    Frequency.WEEKLY.value: "Every week",
                    Frequency.MONTHLY.value: "Every month",
                    Frequency.INTERVAL.value: "Every few minutes",
                    Frequency.CUSTOM.value: "Advanced (cron expression)",
                },
                value=Frequency.DAILY.value,
                label="How often?",
            ).classes("w-full")

            def only_for(*values: str) -> Dict[str, Any]:
                return {"backward": lambda current: current in values}

            time_input = ui.input(
                "Time of day (24h)", value="09:00", placeholder="09:30"
            )
            time_input.bind_visibility_from(
                frequency, "value", **only_for(*_TIME_FREQUENCIES)
            )
            weekday = ui.select(
                {day.value: day.name.title() for day in Weekday},
                value=Weekday.MON.value,
                label="Day of week",
            )
            weekday.bind_visibility_from(
                frequency, "value", **only_for(Frequency.WEEKLY.value)
            )
            day_of_month = ui.number(
                "Day of month (1-28)", value=1, min=1, max=28, precision=0
            )
            day_of_month.bind_visibility_from(
                frequency, "value", **only_for(Frequency.MONTHLY.value)
            )
            minutes = ui.number("Minutes between runs", value=60, min=1, precision=0)
            minutes.bind_visibility_from(
                frequency, "value", **only_for(Frequency.INTERVAL.value)
            )
            cron = ui.input("Cron expression", placeholder="0 9 * * mon-fri").classes(
                "w-full"
            )
            cron.bind_visibility_from(
                frequency, "value", **only_for(Frequency.CUSTOM.value)
            )

            ui.label("Values to use for every run").classes("text-subtitle2")
            form = ParameterForm()
            report.on_value_change(
                lambda: form.show(self._load_parameters(report.value) or [])
            )

            def save() -> None:
                info = self._templates_by_name().get(report.value or "")
                if not (name.value or "").strip() or info is None:
                    ui.notify(
                        "Give the schedule a name and choose a report.", type="warning"
                    )
                    return
                try:
                    hour, minute = (
                        parse_time_of_day(time_input.value or "")
                        if frequency.value in _TIME_FREQUENCIES
                        else (9, 0)
                    )
                    request = ScheduleRequest(
                        name=name.value,
                        report_config=str(info.path),
                        frequency=Frequency(frequency.value),
                        hour=hour,
                        minute=minute,
                        weekday=Weekday(weekday.value),
                        day_of_month=int(day_of_month.value or 1),
                        every_minutes=int(minutes.value) if minutes.value else None,
                        custom_cron=cron.value or None,
                    )
                    create_schedule(self._scheduler, request, form.collect())
                except (ValueError, GuiError) as e:
                    ui.notify(str(e), type="negative", multi_line=True)
                    return
                ui.notify(f"Schedule '{request.name}' added.", type="positive")
                name.set_value("")
                self._schedule_list.refresh()

            ui.button("Add schedule", icon="add", on_click=save)

    # ---------- Templates ----------
    def _templates_panel(self) -> None:
        ui.label(
            "Build a report with the editor, or fill in the Excel template "
            "and upload it."
        ).classes("text-subtitle1")
        new_button = ui.button(
            "New template", icon="add", on_click=lambda: self._open_editor(None)
        )
        new_button.mark("new-template")
        self._template_list()
        with ui.card().classes("w-full"):
            ui.label("Add a template").classes("text-h6")

            def download_blank() -> None:
                filename, data = blank_template_bytes(self._manager)
                ui.download.content(data, filename)

            ui.button(
                "Download blank template", icon="download", on_click=download_blank
            ).props("outline")
            overwrite = ui.switch("Replace a template with the same name")

            async def on_upload(e: events.UploadEventArguments) -> None:
                data = await e.file.read()
                result = import_uploaded_template(
                    self._manager, e.file.name, data, overwrite.value
                )
                upload.reset()
                if result.success:
                    ui.notify(
                        f"Template '{result.template_name}' added.", type="positive"
                    )
                    self._template_list.refresh()
                    self._refresh_template_choices()
                else:
                    ui.notify(
                        "\n".join(result.errors), type="negative", multi_line=True
                    )

            upload = (
                ui.upload(
                    label="Drop your filled-in Excel template here",
                    on_upload=on_upload,
                    auto_upload=True,
                    max_file_size=5_000_000,
                )
                .props('accept=".xlsx"')
                .classes("w-full")
            )

    @ui.refreshable
    def _template_list(self) -> None:
        templates = self._templates_by_name()
        if not templates:
            ui.label("No templates yet. Add one below.").classes("text-grey")
            return
        rows = [
            {"name": i.name, "description": i.description or ""}
            for i in templates.values()
        ]
        columns = [
            {"name": "name", "label": "Template", "field": "name", "align": "left"},
            {
                "name": "description",
                "label": "Description",
                "field": "description",
                "align": "left",
            },
            {"name": "actions", "label": "", "field": "name"},
        ]
        table = ui.table(columns=columns, rows=rows, row_key="name").classes("w-full")
        buttons = _action_button("edit", "edit", "Edit")
        buttons += _action_button("export", "download", "Download as Excel")
        buttons += _action_button("versions", "history", "Version history")
        buttons += _action_button("delete", "delete", "Delete")
        table.add_slot("body-cell-actions", _ACTION_SLOT.format(buttons=buttons))

        def export(e: events.GenericEventArguments) -> None:
            name = e.args.get("name", "")
            if name in templates:
                filename, data = export_template_bytes(self._manager, name)
                ui.download.content(data, filename)

        table.on("export", export)
        table.on(
            "edit",
            lambda e: (
                self._open_editor(e.args.get("name", ""))
                if e.args.get("name", "") in templates
                else None
            ),
        )
        table.on(
            "versions",
            lambda e: (
                self._open_version_history(e.args.get("name", ""))
                if e.args.get("name", "") in templates
                else None
            ),
        )
        table.on(
            "delete",
            lambda e: (
                self._confirm_delete_template(e.args.get("name", ""))
                if e.args.get("name", "") in templates
                else None
            ),
        )

    def _open_version_history(self, name: str) -> None:
        """Show a template's earlier versions, with compare and restore."""
        versions = self._manager.list_versions(name)
        with ui.dialog() as dialog, ui.card().classes("w-full max-w-3xl"):
            ui.label(f"Version history: {name}").classes("text-h6")
            if not versions:
                ui.label("No earlier versions yet. One is kept each time the template is changed.").classes("text-grey")
                ui.button("Close", on_click=dialog.close).props("flat")
                dialog.on("hide", dialog.delete)
                dialog.open()
                return
            known = {v.version_id for v in versions}
            rows = [
                {
                    "version_id": v.version_id,
                    "saved": v.created_at.strftime("%Y-%m-%d %H:%M:%S UTC"),
                    "replaced_by": v.source.value,
                }
                for v in versions
            ]
            columns = [
                {"name": "saved", "label": "Saved", "field": "saved", "align": "left"},
                {
                    "name": "replaced_by",
                    "label": "Replaced by",
                    "field": "replaced_by",
                    "align": "left",
                },
                {"name": "actions", "label": "", "field": "version_id"},
            ]
            table = ui.table(columns=columns, rows=rows, row_key="version_id").classes(
                "w-full"
            )
            buttons = _action_button("compare", "difference", "Compare with current")
            buttons += _action_button("restore", "restore", "Restore this version")
            table.add_slot("body-cell-actions", _ACTION_SLOT.format(buttons=buttons))
            diff_area = ui.column().classes("w-full")

            def compare(e: events.GenericEventArguments) -> None:
                version_id = e.args.get("version_id", "")
                if version_id not in known:
                    return
                diff_area.clear()
                with diff_area:
                    try:
                        diff = self._manager.diff_versions(name, version_id)
                    except TemplateNotFoundError as err:
                        ui.notify(str(err), type="warning")
                        return
                    if diff:
                        ui.code(diff).classes("w-full")
                    else:
                        ui.label("Identical to the current template.").classes("text-grey")

            def restore(e: events.GenericEventArguments) -> None:
                version_id = e.args.get("version_id", "")
                if version_id not in known:
                    return
                try:
                    self._manager.rollback(name, version_id)
                except TemplateNotFoundError as err:
                    ui.notify(str(err), type="warning")
                    return
                ui.notify(
                    f"Template '{name}' restored. The content it replaced is kept in the history.",
                    type="positive",
                )
                dialog.close()
                self._template_list.refresh()
                self._refresh_template_choices()

            table.on("compare", compare)
            table.on("restore", restore)
            ui.button("Close", on_click=dialog.close).props("flat")
        dialog.on("hide", dialog.delete)
        dialog.open()

    # ---------- Template editor ----------
    def _open_editor(self, existing: Optional[str]) -> None:
        """Open the create/edit dialog for a template (``None`` creates one)."""
        base = None
        draft = TemplateDraft()
        if existing:
            try:
                draft, base = load_template_draft(self._manager, existing)
            except GuiError as e:
                ui.notify(str(e), type="negative", multi_line=True)
                return

        with ui.dialog().props("persistent") as dialog, ui.card().classes(
            "w-[90vw] max-w-4xl"
        ):
            ui.label(f"Edit '{existing}'" if existing else "New template").classes(
                "text-h6"
            )
            with ui.column().classes("w-full gap-2").style(
                "max-height: 70vh; overflow-y: auto"
            ):
                self._editor_sections(draft, base)

            def save() -> None:
                try:
                    stored = save_template_draft(self._manager, draft, existing, base)
                except GuiError as e:
                    ui.notify(str(e), type="negative", multi_line=True)
                    return
                ui.notify(f"Template '{stored}' saved.", type="positive")
                dialog.close()
                self._template_list.refresh()
                self._refresh_template_choices()

            with ui.row().classes("justify-end w-full"):
                ui.button("Cancel", on_click=dialog.close).props("flat").mark(
                    "editor-cancel"
                )
                ui.button("Save", icon="save", on_click=save).mark("editor-save")
        dialog.on("hide", dialog.delete)
        dialog.open()

    def _editor_sections(self, draft: TemplateDraft, base: Optional[Any]) -> None:
        with ui.expansion("1. About the report", value=True).classes("w-full"):
            ui.input("Report name").bind_value(draft, "name").classes("w-full").mark(
                "editor-name"
            )
            ui.input("Description (optional)").bind_value(draft, "description").classes(
                "w-full"
            )
            ui.select(
                _OUTPUT_CHOICES, label="Output formats", multiple=True
            ).bind_value(draft, "output").classes("w-full").props("use-chips").mark(
                "editor-output"
            )

        with ui.expansion("2. Where the data comes from", value=True).classes("w-full"):
            ui.input(
                "Database URL", placeholder="sqlite:///sales.db"
            ).bind_value(draft, "database_url").classes("w-full").mark("editor-url")
            ui.textarea(
                "SQL query",
                placeholder="SELECT product, SUM(revenue) AS total FROM sales GROUP BY product",
            ).bind_value(draft, "query").classes("w-full").props("autogrow").mark(
                "editor-query"
            )
            ui.label(
                "Use {{ name }} in the query for a value you fill in at run time "
                "(declare it under Parameters)."
            ).classes("text-caption text-grey")
            preview_area = ui.column().classes("w-full")

            async def test_query() -> None:
                preview_area.clear()
                try:
                    # A copy: the form keeps changing while the query runs.
                    preview = await run.io_bound(
                        preview_query, draft.model_copy(deep=True), 20, base
                    )
                except GuiError as e:
                    with preview_area:
                        ui.label(str(e)).classes("text-negative").style(
                            "white-space: pre-wrap"
                        )
                    return
                with preview_area:
                    self._show_preview(preview)

            ui.button("Test query", icon="play_circle", on_click=test_query).props(
                "outline"
            ).mark("editor-test")

        with ui.expansion("3. Chart (optional)", value=bool(draft.chart_kind)).classes(
            "w-full"
        ):
            ui.select(_CHART_CHOICES, label="Chart type").bind_value(
                draft, "chart_kind"
            ).classes("w-full")
            with ui.row().classes("w-full"):
                ui.input("X column").bind_value(draft, "chart_x").mark("editor-chart-x")
                ui.input("Y column").bind_value(draft, "chart_y")
            ui.input("Chart title").bind_value(draft, "chart_title").classes("w-full")
            with ui.row().classes("w-full"):
                ui.input("X axis label").bind_value(draft, "chart_x_label")
                ui.input("Y axis label").bind_value(draft, "chart_y_label")

        has_grouping = bool(
            draft.group_by or draft.aggregations or draft.pivot_index
        )
        with ui.expansion("4. Grouping and totals (optional)", value=has_grouping).classes(
            "w-full"
        ):
            ui.input("Group by (comma-separated columns)").bind_value(
                draft, "group_by"
            ).classes("w-full")

            @ui.refreshable
            def aggregation_rows() -> None:
                for row in draft.aggregations:
                    with ui.row().classes("w-full items-center"):
                        ui.input("Column").bind_value(row, "column")
                        ui.select(_AGGREGATION_FUNCTIONS, label="Calculate").bind_value(
                            row, "function"
                        )
                        ui.button(
                            icon="delete",
                            on_click=lambda r=row: remove_aggregation(r),
                        ).props("flat round dense")

            def add_aggregation() -> None:
                draft.aggregations.append(AggregationRow())
                aggregation_rows.refresh()

            def remove_aggregation(row: AggregationRow) -> None:
                draft.aggregations.remove(row)
                aggregation_rows.refresh()

            aggregation_rows()
            ui.button("Add a calculation", icon="add", on_click=add_aggregation).props(
                "flat"
            )
            ui.label("Pivot (optional, fill in all three)").classes("text-subtitle2")
            with ui.row().classes("w-full"):
                ui.input("Index column").bind_value(draft, "pivot_index")
                ui.input("Columns").bind_value(draft, "pivot_columns")
                ui.input("Values").bind_value(draft, "pivot_values")

        with ui.expansion(
            "5. Values asked at run time (optional)", value=bool(draft.parameters)
        ).classes("w-full"):

            @ui.refreshable
            def parameter_rows() -> None:
                for row in draft.parameters:
                    with ui.row().classes("w-full items-center"):
                        ui.input("Name").bind_value(row, "name").mark("editor-param-name")
                        ui.select(_PARAMETER_TYPES, label="Type").bind_value(row, "type")
                        ui.checkbox("Required").bind_value(row, "required")
                        ui.input("Default").bind_value(row, "default")
                        ui.input("Description").bind_value(row, "description")
                        ui.button(
                            icon="delete", on_click=lambda r=row: remove_parameter(r)
                        ).props("flat round dense")

            def add_parameter() -> None:
                draft.parameters.append(ParameterRow())
                parameter_rows.refresh()

            def remove_parameter(row: ParameterRow) -> None:
                draft.parameters.remove(row)
                parameter_rows.refresh()

            parameter_rows()
            ui.button("Add a value", icon="add", on_click=add_parameter).props(
                "flat"
            ).mark("editor-add-param")

    @staticmethod
    def _show_preview(preview: QueryPreview) -> None:
        if not preview.rows:
            ui.label("The query ran but returned no rows.").classes("text-grey")
            return
        # Positional keys: result columns may repeat or hold odd characters.
        columns = [
            {"name": f"c{i}", "label": label, "field": f"c{i}", "align": "left"}
            for i, label in enumerate(preview.columns)
        ]
        rows = [
            {"_row": n, **{f"c{i}": value for i, value in enumerate(values)}}
            for n, values in enumerate(preview.rows)
        ]
        ui.table(columns=columns, rows=rows, row_key="_row").classes("w-full").props(
            "dense"
        )
        note = f"First {len(preview.rows)} rows"
        if preview.truncated:
            note += " (there are more)"
        ui.label(note).classes("text-caption text-grey")

    def _confirm_delete_template(self, name: str) -> None:
        def delete() -> None:
            try:
                self._manager.delete_template(name)
            except TemplateNotFoundError as e:
                ui.notify(str(e), type="warning")
            dialog.close()
            self._template_list.refresh()
            self._refresh_template_choices()

        with ui.dialog() as dialog, ui.card():
            ui.label(
                f"Delete the template '{name}'? Its version history is kept, so "
                "it can be restored with 'reportmaker template rollback'."
            )
            with ui.row():
                ui.button("Cancel", on_click=dialog.close).props("flat")
                ui.button("Delete", on_click=delete, color="negative")
        dialog.on("hide", dialog.delete)
        dialog.open()


def register_pages(settings: GuiSettings) -> None:
    """Serve generated reports, start the scheduler, and register the main page."""
    ensure_directory(settings.output_dir)
    app.add_static_files(REPORTS_URL, str(settings.output_dir.resolve()))

    scheduler = SchedulerService(
        str(settings.schedules_file), on_report_generated=deliver_after_schedule_run
    )
    scheduler.start_background()
    app.on_shutdown(scheduler.stop)

    @ui.page("/")
    def index() -> None:
        _Dashboard(settings, scheduler).build()


def run_app(settings: GuiSettings) -> None:
    """Start the web server and (optionally) open the browser. Blocks until stopped."""
    # Reports render on worker threads; a GUI matplotlib backend would try to
    # open a window from the wrong thread.
    matplotlib.use("Agg")
    if not settings.is_local_only:
        logger.warning(
            f"GUI is listening on {settings.host}, not just this machine. "
            "Anyone who can reach it can run reports and read their output."
        )
    register_pages(settings)
    ui.run(
        host=settings.host,
        port=settings.port,
        title="ReportMaker",
        favicon="📊",
        show=settings.open_browser,
        reload=False,
        dark=None,
        show_welcome_message=False,
    )
