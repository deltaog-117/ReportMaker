"""ReportMaker CLI entrypoint."""

import sys
import json
from pathlib import Path

import click

from reportmaker.shared.logging import setup_logging, get_logger
from reportmaker.features.report_generation.services import generate_report

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
            # Try to parse as JSON to support booleans, numbers, etc.
            try:
                # Attempt to parse as JSON
                parsed = json.loads(value)
                # If it's a string, keep it as string; if it's a number/bool, use that
                parameters[key] = parsed
            except json.JSONDecodeError:
                # Fallback to string
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


if __name__ == "__main__":
    cli()
