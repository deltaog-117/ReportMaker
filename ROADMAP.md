# Roadmap

This document outlines the future direction of **ReportMaker**.  
Items are organized by priority, not by timeline.

---

## ✅ Completed (Milestones Achieved)

- ✅ Project scaffold with **feature‑first architecture** (five independent features: `report_generation`, `scheduling`, `delivery`, `data_sources`, `template_management`)
- ✅ Shared infrastructure folder (`shared/`) with stubs for database, logging, PDF generation, email, file utils, and validators
- ✅ Modern Python project setup with `pyproject.toml`, `src/` layout, and dependency management
- ✅ Test skeleton mirroring source (`tests/unit/`, `tests/integration/`)
- ✅ Linting and type‑checking configuration (`ruff`, `mypy`)

---

## 🔥 High Priority (Critical)

These features are **essential** for a minimum viable product that can generate a usable sales report.

- **Core Report Generation** – Implement the `report_generation` feature:
  - Define Pydantic models for `ReportRequest`, `ReportResult`, `DataSourceConfig`, and `ExportFormat` (PDF, HTML, Excel).
  - Build a service that executes a SQL query (against a configurable database), processes the result with pandas, and exports to PDF with a table and chart.
  - Provide a CLI command `reportmaker run --config config.yaml` to trigger a report.
  - Add structured logging and basic performance metrics (query duration, render time).

- **Configuration-Driven Report Definition** – Allow non‑coders to define reports via YAML/JSON:
  - Include query, output format, chart type, aggregation rules, and scheduling parameters.
  - Support dynamic parameters (e.g., `{{ yesterday }}`) for date‑based reports.

- **PDF Export with Table and Chart** – Implement the first output format:
  - Use `reportlab` to generate a PDF with a properly formatted table and a chart (bar or line) below it.
  - Include a title, date stamp, and totals row.

- **Basic Data Source Abstraction** – Create a simple interface in `data_sources` to connect to SQLite and PostgreSQL (or any SQLAlchemy‑supported DB). This allows the report generator to run queries without knowing the underlying DB type.

---

## 🟡 Medium Priority (Important)

These features make the tool more useful and professional.

- **Scheduling Engine** – Integrate with `cron` (or `schedule` library) to run reports automatically:
  - Support intervals (daily, weekly, monthly) and time‑of‑day.
  - Store execution logs and notify on failure.

- **Delivery Options** – Implement local file save and email delivery:
  - Save generated reports to a specified directory with naming conventions (e.g., `sales_report_2026-09-07.pdf`).
  - Send PDF as an email attachment (or embedded) via SMTP.

- **Multi‑Format Export** – Add HTML and Excel export:
  - HTML for embedding in email bodies or web previews.
  - Excel with multiple sheets (raw data + summary).

- **Template Management** – Store report templates (queries, formatting, schedule) in a database or file system, with versioning. This allows users to manage multiple reports and reuse components.

- **Configuration Validation** – Validate YAML files against a schema to prevent runtime errors.

---

## 🟢 Low Priority (Nice‑to‑Have)

Enhancements that add polish but are not required for the first release.

- **GUI Interface** – A simple desktop or web interface to:
  - Create, edit, and preview reports.
  - View history and logs.
  - Trigger manual runs.

- **Dashboard Integration** – Push report data to Power BI, Tableau, or other dashboards via APIs.

- **Alerting** – Send alerts if a metric (e.g., revenue) drops below a threshold.

- **More Chart Types** – Support for pie, scatter, and area charts.

- **Parameterised Reports** – Allow user‑provided parameters (e.g., date range, product category) at runtime.

- **Caching** – Cache query results for frequently run reports to reduce database load.

---

## 🚀 Long‑Term Vision (Ambitious / Experimental)

- **Natural Language Query** – Allow users to describe the report in plain English and auto‑generate the SQL via an LLM.
- **Interactive Report Preview** – A web‑based report viewer that allows drill‑down into data.
- **Data Quality Checks** – Automatically validate data completeness and flag outliers.
- **Versioned Report Runs** – Store every generated report with its parameters and output, enabling “time‑travel” comparison.
