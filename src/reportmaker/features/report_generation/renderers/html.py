"""HTML renderer using Jinja2."""

import base64
import io
from datetime import datetime, timezone
from pathlib import Path

import matplotlib
matplotlib.use("Agg")  # non-interactive backend
import matplotlib.pyplot as plt
import pandas as pd
from jinja2 import Environment, FileSystemLoader, select_autoescape

from reportmaker.shared.file_utils import ensure_directory
from reportmaker.shared.logging import get_logger
from reportmaker.features.report_generation.interfaces import Renderer
from reportmaker.features.report_generation.models import ReportConfig
from reportmaker.features.report_generation.exceptions import RenderingError

logger = get_logger(__name__)

TEMPLATE_DIR = Path(__file__).parent.parent / "templates"


class HTMLRenderer(Renderer):
    """Render data to a self-contained HTML file with inline CSS and base64 charts."""

    def __init__(self) -> None:
        self.env = Environment(
            loader=FileSystemLoader(str(TEMPLATE_DIR)),
            autoescape=select_autoescape(["html", "xml"]),
        )

    def render(self, df: pd.DataFrame, config: ReportConfig, output_path: str) -> str:
        try:
            ensure_directory(Path(output_path).parent)

            # Prepare table data as list of lists for the template
            table_headers = df.columns.tolist()
            table_rows = df.values.tolist()

            # Prepare chart as base64 PNG (if configured and data present)
            chart_data_uri = None
            if config.chart and not df.empty:
                chart_data_uri = self._render_chart_base64(df, config)

            # Load and render template
            template = self.env.get_template("html_report.j2")
            html = template.render(
                title=config.name,
                description=config.description or "",
                generated_at=datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC"),
                table_headers=table_headers,
                table_rows=table_rows,
                row_count=len(df),
                chart_data_uri=chart_data_uri,
                chart_title=(config.chart.title if config.chart else None) or "Chart",
            )

            with open(output_path, "w", encoding="utf-8") as f:
                f.write(html)

            logger.info(f"HTML rendered to {output_path}")
            return output_path

        except Exception as e:
            raise RenderingError(f"HTML rendering failed: {e}") from e

    @staticmethod
    def _render_chart_base64(df: pd.DataFrame, config: ReportConfig) -> str:
        """Return a data URI containing a base64-encoded PNG chart."""
        chart_config = config.chart
        fig, ax = plt.subplots(figsize=(8, 4.5))
        try:
            if chart_config.kind.value == "bar":
                df.plot(kind="bar", x=chart_config.x_column, y=chart_config.y_column,
                        ax=ax, legend=True, color="#2563EB")
            elif chart_config.kind.value == "line":
                df.plot(kind="line", x=chart_config.x_column, y=chart_config.y_column,
                        ax=ax, marker="o", legend=True, color="#2563EB")
            else:
                raise ValueError(f"Unsupported chart kind: {chart_config.kind}")

            ax.set_title(chart_config.title or "Chart")
            if chart_config.x_label:
                ax.set_xlabel(chart_config.x_label)
            if chart_config.y_label:
                ax.set_ylabel(chart_config.y_label)
            ax.grid(True, linestyle="--", alpha=0.4)
            fig.tight_layout()

            buf = io.BytesIO()
            fig.savefig(buf, format="png", dpi=110, bbox_inches="tight")
            buf.seek(0)
            encoded = base64.b64encode(buf.read()).decode("ascii")
            return f"data:image/png;base64,{encoded}"
        finally:
            plt.close(fig)
