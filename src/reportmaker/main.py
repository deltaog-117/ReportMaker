"""ReportMaker CLI entrypoint."""

import sys
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
def run(config: str, output_dir: str, verbose: bool):
    """Generate a report from a configuration file."""
    setup_logging(level="DEBUG" if verbose else "INFO", json_format=False)
    logger.info(f"Generating report from config: {config}")
    result = generate_report(config, output_dir)
    if result.success:
        click.echo(f"✅ Report generated successfully: {result.output_path}")
        click.echo(f"📊 Metrics: {result.metrics}")
        sys.exit(0)
    else:
        click.echo(f"❌ Report generation failed: {result.error}", err=True)
        sys.exit(1)


if __name__ == "__main__":
    cli()
