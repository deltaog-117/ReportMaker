"""ReportMaker CLI entrypoint."""

import sys
import json
from pathlib import Path

import click

from reportmaker.shared.logging import setup_logging, get_logger
from reportmaker.features.report_generation.services import generate_report
from reportmaker.features.scheduling.services import SchedulerService
from reportmaker.features.scheduling.models import ScheduleConfig
from reportmaker.features.scheduling.exceptions import ScheduleAlreadyExistsError, ScheduleNotFoundError
from reportmaker.features.template_management.services import TemplateManager
from reportmaker.features.template_management.exceptions import (
    TemplateNotFoundError,
    TemplateAlreadyExistsError,
    TemplateValidationError,
    TemplateImportError,
)

logger = get_logger(__name__)


@click.group()
def cli():
    """ReportMaker – Dynamic Report Generator."""
    pass


# ---------- Run command ----------
@cli.command()
@click.option("--config", "-c", required=True, type=click.Path(exists=True), help="Path to YAML report configuration")
@click.option("--output-dir", "-o", default="./reports", help="Directory to save output")
@click.option("--verbose", "-v", is_flag=True, help="Enable verbose logging")
@click.option("--param", "-p", multiple=True, help="Dynamic parameter in key=value format (can be repeated)")
@click.option("--params-file", "-P", type=click.Path(exists=True), help="JSON file containing parameters")
def run(config: str, output_dir: str, verbose: bool, param: tuple, params_file: str):
    """Generate a report from a configuration file."""
    setup_logging(level="DEBUG" if verbose else "INFO", json_format=False)
    parameters = _parse_parameters(param, params_file)
    logger.info(f"Generating report from config: {config} with params: {parameters}")
    result = generate_report(config, output_dir, parameters)
    if result.success:
        click.echo(f"✅ Report generated successfully: {result.output_path}")
        click.echo(f"📊 Metrics: {result.metrics}")
        sys.exit(0)
    else:
        click.echo(f"❌ Report generation failed: {result.error}", err=True)
        sys.exit(1)


# ---------- Scheduling commands ----------
@cli.group()
def schedule():
    """Manage scheduled report runs."""
    pass


@schedule.command("add")
@click.option("--name", "-n", required=True, help="Unique name for the schedule")
@click.option("--cron", "-c", help="Cron expression (e.g., '0 9 * * *')")
@click.option("--interval", "-i", type=int, help="Interval in seconds (alternative to cron)")
@click.option("--config", required=True, type=click.Path(exists=True), help="Path to YAML report config")
@click.option("--param", "-p", multiple=True, help="Dynamic parameter in key=value format")
@click.option("--params-file", "-P", type=click.Path(exists=True), help="JSON file containing parameters")
@click.option("--enabled/--disabled", default=True, help="Enable or disable the schedule")
@click.option("--schedules-file", type=click.Path(), default="schedules.yaml", help="Path to schedules storage file")
def schedule_add(name, cron, interval, config, param, params_file, enabled, schedules_file):
    """Add a new scheduled report run."""
    setup_logging(level="INFO", json_format=False)
    service = SchedulerService(schedules_file)
    if not cron and not interval:
        click.echo("Error: Must provide either --cron or --interval", err=True); sys.exit(1)
    if cron and interval:
        click.echo("Error: Provide only one of --cron or --interval", err=True); sys.exit(1)
    parameters = _parse_parameters(param, params_file)
    try:
        cfg = ScheduleConfig(
            name=name, cron=cron, interval_seconds=interval,
            report_config=config, parameters=parameters, enabled=enabled,
        )
        service.add_schedule(cfg)
        click.echo(f"✅ Schedule '{name}' added successfully.")
    except ScheduleAlreadyExistsError as e:
        click.echo(f"❌ {e}", err=True); sys.exit(1)
    except Exception as e:
        click.echo(f"❌ Error adding schedule: {e}", err=True); sys.exit(1)


@schedule.command("list")
@click.option("--schedules-file", type=click.Path(), default="schedules.yaml")
def schedule_list(schedules_file):
    """List all scheduled report runs."""
    setup_logging(level="INFO", json_format=False)
    service = SchedulerService(schedules_file)
    statuses = service.list_schedules()
    if not statuses:
        click.echo("No schedules found."); return
    from tabulate import tabulate
    table = [[s.name, "✅" if s.enabled else "❌",
              f"{s.trigger_type}: {s.trigger_value}",
              s.last_run.strftime("%Y-%m-%d %H:%M") if s.last_run else "Never",
              s.next_run.strftime("%Y-%m-%d %H:%M") if s.next_run else "N/A"]
             for s in statuses]
    click.echo(tabulate(table, headers=["Name", "Enabled", "Trigger", "Last Run", "Next Run"], tablefmt="grid"))


@schedule.command("remove")
@click.option("--name", "-n", required=True)
@click.option("--schedules-file", type=click.Path(), default="schedules.yaml")
def schedule_remove(name, schedules_file):
    """Remove a scheduled report run."""
    setup_logging(level="INFO", json_format=False)
    service = SchedulerService(schedules_file)
    try:
        service.remove_schedule(name)
        click.echo(f"✅ Schedule '{name}' removed.")
    except ScheduleNotFoundError as e:
        click.echo(f"❌ {e}", err=True); sys.exit(1)


@schedule.command("start")
@click.option("--schedules-file", type=click.Path(), default="schedules.yaml")
@click.option("--foreground", is_flag=True, default=True)
def schedule_start(schedules_file, foreground):
    """Start the scheduler daemon (runs all scheduled jobs)."""
    setup_logging(level="INFO", json_format=False)
    service = SchedulerService(schedules_file)
    click.echo(f"Starting scheduler... (foreground={foreground})")
    service.start(foreground=foreground)


# ---------- Template commands ----------
@cli.group()
def template():
    """Manage report templates (Excel ↔ YAML)."""
    pass


@template.command("init")
@click.argument("output_path", type=click.Path())
def template_init(output_path):
    """Create a blank template spreadsheet you can fill out in Excel."""
    setup_logging(level="INFO", json_format=False)
    manager = TemplateManager()  # only used for create_blank_xlsx
    path = manager.create_blank_xlsx(output_path)
    click.echo(f"✅ Blank template created: {path}")
    click.echo("   Open it in Excel (or LibreOffice Calc), fill in the fields, then run:")
    click.echo(f"   reportmaker template import {path}")


@template.command("import")
@click.argument("xlsx_path", type=click.Path(exists=True))
@click.option("--templates-dir", default="./templates", help="Directory to store templates")
@click.option("--name", help="Override the template name (defaults to 'Report Name' from the sheet)")
@click.option("--force", is_flag=True, help="Overwrite if a template with the same name exists")
def template_import(xlsx_path, templates_dir, name, force):
    """Import a spreadsheet and save it as a YAML template."""
    setup_logging(level="INFO", json_format=False)
    manager = TemplateManager(templates_dir)
    result = manager.import_from_xlsx(xlsx_path, name_override=name, force=force)
    if result.success:
        click.echo(f"✅ Template imported: {result.template_name}")
        click.echo(f"   Saved to: {result.yaml_path}")
        click.echo(f"   To run it: reportmaker run --config {result.yaml_path}")
    else:
        for err in result.errors:
            click.echo(f"❌ {err}", err=True)
        sys.exit(1)


@template.command("export")
@click.argument("name")
@click.argument("output_path", type=click.Path())
@click.option("--templates-dir", default="./templates")
def template_export(name, output_path, templates_dir):
    """Export a stored YAML template back to a spreadsheet for editing."""
    setup_logging(level="INFO", json_format=False)
    manager = TemplateManager(templates_dir)
    try:
        path = manager.export_to_xlsx(name, output_path)
        click.echo(f"✅ Template '{name}' exported to: {path}")
    except TemplateNotFoundError as e:
        click.echo(f"❌ {e}", err=True); sys.exit(1)
    except Exception as e:
        click.echo(f"❌ Export failed: {e}", err=True); sys.exit(1)


@template.command("list")
@click.option("--templates-dir", default="./templates")
def template_list(templates_dir):
    """List all stored templates."""
    setup_logging(level="INFO", json_format=False)
    manager = TemplateManager(templates_dir)
    infos = manager.list_templates()
    if not infos:
        click.echo(f"No templates found in {manager.templates_dir}")
        click.echo("Create one with: reportmaker template init my_template.xlsx")
        return
    from tabulate import tabulate
    table = [[i.name, i.description or "", str(i.path)] for i in infos]
    click.echo(tabulate(table, headers=["Name", "Description", "Path"], tablefmt="grid"))


@template.command("validate")
@click.argument("name")
@click.option("--templates-dir", default="./templates")
def template_validate(name, templates_dir):
    """Validate a stored template against the schema."""
    setup_logging(level="INFO", json_format=False)
    manager = TemplateManager(templates_dir)
    try:
        config = manager.validate_template(name)
        click.echo(f"✅ Template '{name}' is valid.")
        click.echo(f"   Report name: {config.name}")
        click.echo(f"   Output format: {config.output.value}")
        click.echo(f"   Parameters: {len(config.parameters) if config.parameters else 0}")
        click.echo(f"   Has chart: {'yes' if config.chart else 'no'}")
    except TemplateNotFoundError as e:
        click.echo(f"❌ {e}", err=True); sys.exit(1)
    except TemplateValidationError as e:
        click.echo(f"❌ {e}", err=True); sys.exit(1)


@template.command("delete")
@click.argument("name")
@click.option("--templates-dir", default="./templates")
@click.confirmation_option(prompt="Are you sure you want to delete this template?")
def template_delete(name, templates_dir):
    """Delete a stored template."""
    setup_logging(level="INFO", json_format=False)
    manager = TemplateManager(templates_dir)
    try:
        manager.delete_template(name)
        click.echo(f"✅ Template '{name}' deleted.")
    except TemplateNotFoundError as e:
        click.echo(f"❌ {e}", err=True); sys.exit(1)


# ---------- Helpers ----------
def _parse_parameters(param: tuple, params_file: str) -> dict:
    """Parse CLI parameters from --param and --params-file."""
    parameters = {}
    if param:
        for p in param:
            if "=" not in p:
                click.echo(f"Error: invalid parameter format '{p}'. Use key=value", err=True)
                sys.exit(1)
            key, value = p.split("=", 1)
            try:
                parameters[key] = json.loads(value)
            except json.JSONDecodeError:
                parameters[key] = value
    if params_file:
        with open(params_file, "r") as f:
            parameters.update(json.load(f))
    return parameters


if __name__ == "__main__":
    cli()
