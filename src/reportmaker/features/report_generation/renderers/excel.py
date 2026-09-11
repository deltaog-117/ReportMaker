"""Excel renderer using openpyxl with multi-sheet output."""

from pathlib import Path

import pandas as pd
from openpyxl import Workbook
from openpyxl.chart import BarChart, LineChart, Reference
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter

from reportmaker.shared.file_utils import ensure_directory
from reportmaker.shared.logging import get_logger
from reportmaker.features.report_generation.interfaces import Renderer
from reportmaker.features.report_generation.models import ReportConfig
from reportmaker.features.report_generation.exceptions import RenderingError

logger = get_logger(__name__)

# Style constants
HEADER_FILL = PatternFill(start_color="1E3A8A", end_color="1E3A8A", fill_type="solid")
HEADER_FONT = Font(color="FFFFFF", bold=True, size=11)
ALT_FILL = PatternFill(start_color="F1F5F9", end_color="F1F5F9", fill_type="solid")
BORDER = Border(
    left=Side(style="thin", color="E2E8F0"),
    right=Side(style="thin", color="E2E8F0"),
    top=Side(style="thin", color="E2E8F0"),
    bottom=Side(style="thin", color="E2E8F0"),
)


class ExcelRenderer(Renderer):
    """Render data to an XLSX workbook with Data, Summary, and Chart sheets."""

    def render(self, df: pd.DataFrame, config: ReportConfig, output_path: str) -> str:
        try:
            ensure_directory(Path(output_path).parent)
            wb = Workbook()
            wb.remove(wb.active)  # remove default sheet

            # --- Data sheet ---
            ws_data = wb.create_sheet("Data")
            self._write_data_sheet(ws_data, df)

            # --- Summary sheet ---
            ws_summary = wb.create_sheet("Summary")
            self._write_summary_sheet(ws_summary, df, config)

            # --- Chart sheet (only if chart is configured and data present) ---
            if config.chart and not df.empty:
                ws_chart = wb.create_sheet("Chart")
                self._write_chart_sheet(ws_chart, df, config)

            wb.save(output_path)
            logger.info(f"Excel rendered to {output_path}")
            return output_path
        except Exception as e:
            raise RenderingError(f"Excel rendering failed: {e}") from e

    # ---------- Sheet writers ----------

    @staticmethod
    def _write_data_sheet(ws, df: pd.DataFrame) -> None:
        """Write the raw DataFrame with styled header and frozen top row."""
        # Header row
        for col_idx, col_name in enumerate(df.columns, start=1):
            cell = ws.cell(row=1, column=col_idx, value=str(col_name))
            cell.fill = HEADER_FILL
            cell.font = HEADER_FONT
            cell.alignment = Alignment(horizontal="center", vertical="center")
            cell.border = BORDER

        # Data rows
        for row_idx, row in enumerate(df.itertuples(index=False), start=2):
            for col_idx, value in enumerate(row, start=1):
                cell = ws.cell(row=row_idx, column=col_idx, value=value)
                cell.border = BORDER
                if row_idx % 2 == 0:
                    cell.fill = ALT_FILL

        # Auto column widths
        for col_idx, col_name in enumerate(df.columns, start=1):
            max_len = max(
                [len(str(col_name))] + [len(str(v)) for v in df.iloc[:, col_idx - 1]]
            ) if not df.empty else len(str(col_name))
            ws.column_dimensions[get_column_letter(col_idx)].width = min(max_len + 4, 60)

        # Freeze top row and enable autofilter
        ws.freeze_panes = "A2"
        ws.auto_filter.ref = ws.dimensions

    @staticmethod
    def _write_summary_sheet(ws, df: pd.DataFrame, config: ReportConfig) -> None:
        """Write a summary: per-numeric-column total, plus row count."""
        ws.cell(row=1, column=1, value="Metric").font = HEADER_FONT
        ws.cell(row=1, column=2, value="Value").font = HEADER_FONT
        ws.cell(row=1, column=1).fill = HEADER_FILL
        ws.cell(row=1, column=2).fill = HEADER_FILL
        ws.cell(row=1, column=1).border = BORDER
        ws.cell(row=1, column=2).border = BORDER

        row = 2
        ws.cell(row=row, column=1, value="Rows").border = BORDER
        ws.cell(row=row, column=2, value=len(df)).border = BORDER
        row += 1

        ws.cell(row=row, column=1, value="Columns").border = BORDER
        ws.cell(row=row, column=2, value=len(df.columns)).border = BORDER
        row += 1

        # Numeric totals
        for col in df.columns:
            if pd.api.types.is_numeric_dtype(df[col]):
                ws.cell(row=row, column=1, value=f"Total {col}").border = BORDER
                ws.cell(row=row, column=2, value=float(df[col].sum())).border = BORDER
                row += 1

        ws.column_dimensions["A"].width = 30
        ws.column_dimensions["B"].width = 25

    @staticmethod
    def _write_chart_sheet(ws, df: pd.DataFrame, config: ReportConfig) -> None:
        """Write a native Excel chart that references the Data sheet."""
        chart_config = config.chart

        # Build a small helper range on the Chart sheet so the chart has data to plot.
        # We re-write the x and y columns here, then create the chart from this block.
        ws.cell(row=1, column=1, value=chart_config.x_column).font = HEADER_FONT
        ws.cell(row=1, column=2, value=chart_config.y_column).font = HEADER_FONT
        ws.cell(row=1, column=1).fill = HEADER_FILL
        ws.cell(row=1, column=2).fill = HEADER_FILL

        for i, (x_val, y_val) in enumerate(
            zip(df[chart_config.x_column], df[chart_config.y_column]), start=2
        ):
            ws.cell(row=i, column=1, value=x_val)
            ws.cell(row=i, column=2, value=y_val)

        n_rows = len(df) + 1  # include header

        if chart_config.kind.value == "bar":
            chart = BarChart()
        elif chart_config.kind.value == "line":
            chart = LineChart()
        else:
            raise ValueError(f"Unsupported chart kind: {chart_config.kind}")

        chart.title = chart_config.title or "Chart"
        chart.x_axis.title = chart_config.x_label or chart_config.x_column
        chart.y_axis.title = chart_config.y_label or chart_config.y_column
        chart.style = 11

        data_ref = Reference(ws, min_col=2, min_row=1, max_row=n_rows)
        cats_ref = Reference(ws, min_col=1, min_row=2, max_row=n_rows)
        chart.add_data(data_ref, titles_from_data=True)
        chart.set_categories(cats_ref)
        chart.height = 10
        chart.width = 20

        ws.add_chart(chart, "D2")
        ws.column_dimensions["A"].width = 25
        ws.column_dimensions["B"].width = 20
