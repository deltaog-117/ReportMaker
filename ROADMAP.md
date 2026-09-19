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
- ✅ Configuration Validation – `reportmaker validate` command plus semantic pre‑flight checks (cron syntax, Jinja2 syntax, database URL, chart columns) wired into `run` and `schedule add`, so bad configs fail fast with actionable messages instead of a raw traceback or a silent scheduled failure
- ✅ GUI Interface (MVP) – `reportmaker gui` opens a NiceGUI web app in the browser so non-technical users never need the CLI: run a report from an auto-generated parameter form, preview/download it, browse past reports, add/remove schedules in plain language (no cron required), and import/export Excel templates by upload/download. Optional install: `pip install -e ".[gui]"`
- ✅ Delivery Options – `delivery` feature with a channel abstraction (`local`, `email`); reports can be copied to a directory or sent as an SMTP email attachment via an optional `delivery:` section in the report YAML, triggered automatically after `run` and after each successful scheduled run

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

- **Multi‑Format Export** – Add HTML and Excel export:
  - HTML for embedding in email bodies or web previews.
  - Excel with multiple sheets (raw data + summary).

- **Template Management** – Store report templates (queries, formatting, schedule) in a database or file system, with versioning. This allows users to manage multiple reports and reuse components.

---

## 🟢 Low Priority (Nice‑to‑Have)

Enhancements that add polish but are not required for the first release.

- **GUI Interface – follow-ups** – The MVP shipped (see Completed). Remaining:
  - Create and edit report definitions visually (today: fill in the Excel template and upload it).
  - Run the scheduler inside the GUI process, so schedules fire without a separate `reportmaker schedule start`.
  - View run logs and enable/disable existing schedules.

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
