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

logger = get_logger(__name__)


@click.group()
def cli():
    """ReportMaker – Dynamic Report Generator."""
    pass


@cli.command()
@click.option("--config", "-c", required=True, type=click.Path(exists=True), help="Path to YAML report configuration")
@click.option("--output-dir", "-o", default="./reports", help="Directory to save output")
@click.option("--verbose", "-v", is_flag=True, help="Enable verbose logging")
@click.option("--param", "-p", multiple=True, help="Dynamic parameter in key=value format (can be repeated)")
@click.option("--params-file", "-P", type=click.Path(exists=True), help="JSON file containing parameters")
def run(config: str, output_dir: str, verbose: bool, param: tuple, params_file: str):
    """Generate a report from a configuration file."""
    setup_logging(level="DEBUG" if verbose else "INFO", json_format=False)

    # Parse parameters
    parameters = {}
    if param:
        for p in param:
            if "=" not in p:
                click.echo(f"Error: invalid parameter format '{p}'. Use key=value", err=True)
                sys.exit(1)
            key, value = p.split("=", 1)
            try:
                parsed = json.loads(value)
                parameters[key] = parsed
            except json.JSONDecodeError:
                parameters[key] = value

    if params_file:
        with open(params_file, "r") as f:
            file_params = json.load(f)
            parameters.update(file_params)

    logger.info(f"Generating report from config: {config} with params: {parameters}")
    result = generate_report(config, output_dir, parameters)
    if result.success:
        click.echo(f"✅ Report generated successfully: {result.output_path}")
        click.echo(f"📊 Metrics: {result.metrics}")
        sys.exit(0)
    else:
        click.echo(f"❌ Report generation failed: {result.error}", err=True)
        sys.exit(1)


# ---------- Scheduling Commands ----------
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
        click.echo("Error: Must provide either --cron or --interval", err=True)
        sys.exit(1)
    if cron and interval:
        click.echo("Error: Provide only one of --cron or --interval", err=True)
        sys.exit(1)

    # Parse parameters
    parameters = {}
    if param:
        for p in param:
            if "=" not in p:
                click.echo(f"Error: invalid parameter format '{p}'. Use key=value", err=True)
                sys.exit(1)
            key, value = p.split("=", 1)
            try:
                parsed = json.loads(value)
                parameters[key] = parsed
            except json.JSONDecodeError:
                parameters[key] = value
    if params_file:
        with open(params_file, "r") as f:
            file_params = json.load(f)
            parameters.update(file_params)

    try:
        cfg = ScheduleConfig(
            name=name,
            cron=cron,
            interval_seconds=interval,
            report_config=config,
            parameters=parameters,
            enabled=enabled,
        )
        service.add_schedule(cfg)
        click.echo(f"✅ Schedule '{name}' added successfully.")
        if not enabled:
            click.echo("⚠️ Schedule is disabled. Use --enabled to activate.")
    except ScheduleAlreadyExistsError as e:
        click.echo(f"❌ {e}", err=True)
        sys.exit(1)
    except Exception as e:
        click.echo(f"❌ Error adding schedule: {e}", err=True)
        sys.exit(1)


@schedule.command("list")
@click.option("--schedules-file", type=click.Path(), default="schedules.yaml", help="Path to schedules storage file")
def schedule_list(schedules_file):
    """List all scheduled report runs."""
    setup_logging(level="INFO", json_format=False)
    service = SchedulerService(schedules_file)
    statuses = service.list_schedules()
    if not statuses:
        click.echo("No schedules found.")
        return

    # Pretty print table
    from tabulate import tabulate
    table = []
    for s in statuses:
        table.append([
            s.name,
            "✅" if s.enabled else "❌",
            f"{s.trigger_type}: {s.trigger_value}",
            s.last_run.strftime("%Y-%m-%d %H:%M") if s.last_run else "Never",
            s.next_run.strftime("%Y-%m-%d %H:%M") if s.next_run else "N/A",
        ])
    click.echo(tabulate(table, headers=["Name", "Enabled", "Trigger", "Last Run", "Next Run"], tablefmt="grid"))


@schedule.command("remove")
@click.option("--name", "-n", required=True, help="Name of the schedule to remove")
@click.option("--schedules-file", type=click.Path(), default="schedules.yaml", help="Path to schedules storage file")
def schedule_remove(name, schedules_file):
    """Remove a scheduled report run."""
    setup_logging(level="INFO", json_format=False)
    service = SchedulerService(schedules_file)
    try:
        service.remove_schedule(name)
        click.echo(f"✅ Schedule '{name}' removed.")
    except ScheduleNotFoundError as e:
        click.echo(f"❌ {e}", err=True)
        sys.exit(1)
    except Exception as e:
        click.echo(f"❌ Error removing schedule: {e}", err=True)
        sys.exit(1)


@schedule.command("start")
@click.option("--schedules-file", type=click.Path(), default="schedules.yaml", help="Path to schedules storage file")
@click.option("--foreground", is_flag=True, default=True, help="Run in foreground (default)")
def schedule_start(schedules_file, foreground):
    """Start the scheduler daemon (runs all scheduled jobs)."""
    setup_logging(level="INFO", json_format=False)
    service = SchedulerService(schedules_file)
    click.echo(f"Starting scheduler... (foreground={foreground})")
    service.start(foreground=foreground)


if __name__ == "__main__":
    cli()
