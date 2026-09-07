"""Core report generation service with pluggable pipeline stages."""

import io
import time
import logging
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

import pandas as pd
import matplotlib.pyplot as plt
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image
from sqlalchemy import create_engine, text

from reportmaker.shared.db import get_engine
from reportmaker.shared.logging import get_logger
from reportmaker.shared.file_utils import ensure_directory, safe_filename
from reportmaker.features.report_generation.models import ReportConfig, ReportRequest, ReportResult, TransformConfig
from reportmaker.features.report_generation.exceptions import (
    ConfigError,
    DataExtractionError,
    DataTransformationError,
    RenderingError,
)

# Suppress matplotlib font debug messages
logging.getLogger("matplotlib.font_manager").setLevel(logging.WARNING)

logger = get_logger(__name__)


# ---------- Abstract Interfaces ----------
class Extractor(ABC):
    """Extract raw data from a data source."""
    @abstractmethod
    def extract(self, config: ReportConfig, parameters: Optional[Dict[str, Any]] = None) -> pd.DataFrame:
        """Execute query and return DataFrame."""
        pass


class Transformer(ABC):
    """Transform raw data into the final dataset for rendering."""
    @abstractmethod
    def transform(self, df: pd.DataFrame, config: ReportConfig) -> pd.DataFrame:
        """Apply transformations (groupby, pivot, aggregations)."""
        pass


class Renderer(ABC):
    """Render the processed data into an output file."""
    @abstractmethod
    def render(self, df: pd.DataFrame, config: ReportConfig, output_path: str) -> str:
        """Generate the report file and return its path."""
        pass


# ---------- Concrete Implementations ----------
class SQLAlchemyExtractor(Extractor):
    """Extract data using SQLAlchemy engine built from config URL."""
    def extract(self, config: ReportConfig, parameters: Optional[Dict[str, Any]] = None) -> pd.DataFrame:
        url = config.data_source.url
        engine = create_engine(url)
        query = config.data_source.query
        params = config.data_source.parameters or {}
        if parameters:
            params.update(parameters)
        try:
            with engine.connect() as conn:
                df = pd.read_sql(text(query), conn, params=params)
            logger.info(f"Extracted {len(df)} rows from query")
            return df
        except Exception as e:
            raise DataExtractionError(f"Failed to extract data: {e}") from e


class PandasTransformer(Transformer):
    """Transform data using pandas operations."""
    def transform(self, df: pd.DataFrame, config: ReportConfig) -> pd.DataFrame:
        if config.transform is None:
            return df

        tf = config.transform
        df = df.copy()

        if tf.group_by and tf.aggregations:
            try:
                df = df.groupby(tf.group_by).agg(tf.aggregations).reset_index()
                if isinstance(df.columns, pd.MultiIndex):
                    df.columns = ['_'.join(col).strip('_') for col in df.columns.values]
            except Exception as e:
                raise DataTransformationError(f"Groupby/aggregation failed: {e}") from e

        if tf.pivot:
            try:
                pivot_config = tf.pivot
                index = pivot_config.get("index")
                columns = pivot_config.get("columns")
                values = pivot_config.get("values")
                if index and columns and values:
                    df = df.pivot(index=index, columns=columns, values=values).reset_index()
                    df.columns = ['_'.join(col).strip('_') if isinstance(col, tuple) else col for col in df.columns]
            except Exception as e:
                raise DataTransformationError(f"Pivot failed: {e}") from e

        logger.info(f"Transformed data: {len(df)} rows, {len(df.columns)} columns")
        return df


class PDFRenderer(Renderer):
    """Render data to PDF with a table and optional chart."""
    def render(self, df: pd.DataFrame, config: ReportConfig, output_path: str) -> str:
        try:
            ensure_directory(Path(output_path).parent)
            doc = SimpleDocTemplate(output_path, pagesize=A4,
                                    topMargin=0.75*inch, bottomMargin=0.75*inch,
                                    leftMargin=0.75*inch, rightMargin=0.75*inch)
            styles = getSampleStyleSheet()
            story = []

            # Title
            title = config.name or "Report"
            story.append(Paragraph(title, styles['Title']))
            story.append(Spacer(1, 0.25*inch))

            # Table
            if df.empty:
                story.append(Paragraph("No data available.", styles['Normal']))
            else:
                table_data = [df.columns.tolist()] + df.values.tolist()
                col_count = len(df.columns)
                col_widths = [2.5*inch] * col_count
                table = Table(table_data, colWidths=col_widths, repeatRows=1)
                table.setStyle(TableStyle([
                    ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
                    ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                    ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                    ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                    ('FONTSIZE', (0, 0), (-1, 0), 10),
                    ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
                    ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
                    ('GRID', (0, 0), (-1, -1), 1, colors.black),
                    ('FONTSIZE', (0, 1), (-1, -1), 8),
                ]))
                story.append(table)

            # Chart
            if config.chart and not df.empty:
                story.append(Spacer(1, 0.5*inch))
                story.append(Paragraph("Chart", styles['Heading2']))
                story.append(Spacer(1, 0.2*inch))

                chart_config = config.chart
                try:
                    fig, ax = plt.subplots(figsize=(6, 4))
                    if chart_config.kind.value == "bar":
                        df.plot(kind='bar', x=chart_config.x_column, y=chart_config.y_column, ax=ax, legend=True)
                    elif chart_config.kind.value == "line":
                        df.plot(kind='line', x=chart_config.x_column, y=chart_config.y_column, ax=ax, marker='o', legend=True)
                    else:
                        raise ValueError(f"Unsupported chart kind: {chart_config.kind}")

                    ax.set_title(chart_config.title or "Chart")
                    if chart_config.x_label:
                        ax.set_xlabel(chart_config.x_label)
                    if chart_config.y_label:
                        ax.set_ylabel(chart_config.y_label)
                    ax.grid(True, linestyle='--', alpha=0.6)

                    # Save chart to memory as PNG
                    img_buf = io.BytesIO()
                    plt.savefig(img_buf, format='png', dpi=100, bbox_inches='tight')
                    plt.close(fig)
                    img_buf.seek(0)

                    # Embed image in PDF – pass the buffer directly
                    story.append(Image(img_buf, width=6*inch, height=4*inch))
                except Exception as e:
                    logger.error(f"Failed to generate chart: {e}")
                    story.append(Paragraph(f"Chart generation failed: {e}", styles['Italic']))

            # Build PDF
            doc.build(story)
            logger.info(f"PDF rendered to {output_path}")
            return output_path
        except Exception as e:
            raise RenderingError(f"PDF rendering failed: {e}") from e


# ---------- Pipeline Orchestrator ----------
class ReportPipeline:
    """Orchestrates the extraction, transformation, and rendering stages."""
    def __init__(self, extractor: Extractor, transformer: Transformer, renderer: Renderer):
        self.extractor = extractor
        self.transformer = transformer
        self.renderer = renderer

    def run(self, request: ReportRequest) -> ReportResult:
        start_time = time.time()
        config = request.config
        output_dir = request.output_dir
        try:
            logger.info(f"Starting report generation for '{config.name}'")

            df = self.extractor.extract(config, request.parameters)
            extraction_rows = len(df)

            df = self.transformer.transform(df, config)
            transform_rows = len(df)

            safe_name = safe_filename(config.name)
            timestamp = pd.Timestamp.now().strftime("%Y%m%d_%H%M%S")
            filename = f"{safe_name}_{timestamp}.{config.output.value}"
            output_path = str(Path(output_dir) / filename)

            self.renderer.render(df, config, output_path)

            duration = time.time() - start_time
            metrics = {
                "duration_seconds": duration,
                "extraction_rows": extraction_rows,
                "transform_rows": transform_rows,
                "output_format": config.output.value,
            }
            logger.info(f"Report generated successfully in {duration:.2f}s", extra={"metrics": metrics})

            return ReportResult(
                success=True,
                output_path=output_path,
                metrics=metrics,
                logs=[f"Generated {config.name} successfully"],
            )
        except Exception as e:
            logger.error(f"Report generation failed: {e}", exc_info=True)
            return ReportResult(
                success=False,
                error=str(e),
                metrics={"duration_seconds": time.time() - start_time},
                logs=[f"Failed: {e}"],
            )


# ---------- Factory and Convenience Functions ----------
def create_default_pipeline() -> ReportPipeline:
    """Create a pipeline with default implementations."""
    return ReportPipeline(
        extractor=SQLAlchemyExtractor(),
        transformer=PandasTransformer(),
        renderer=PDFRenderer(),
    )


def generate_report(config_path: str, output_dir: str = "./reports", parameters: Optional[Dict[str, Any]] = None) -> ReportResult:
    """Convenience function to generate a report from a YAML config file."""
    from reportmaker.shared.config import load_yaml_config
    from reportmaker.features.report_generation.models import ReportConfig

    raw_config = load_yaml_config(config_path)
    config = ReportConfig(**raw_config)
    request = ReportRequest(config=config, output_dir=output_dir, parameters=parameters)
    pipeline = create_default_pipeline()
    return pipeline.run(request)
