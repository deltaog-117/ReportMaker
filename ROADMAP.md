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
- ✅ GUI Interface – embedded scheduler – `reportmaker gui` now runs a `BackgroundScheduler` inside its own process, so schedules fire without a separate `reportmaker schedule start`; a schedule added, removed, or toggled from the GUI takes effect on that same running scheduler immediately. The Schedules tab gained an enable/disable toggle per schedule and a "view run history" dialog backed by a new bounded run-history log

- ✅ GUI Interface – visual template editor – the Templates tab has a "New template" button and a per-row "Edit" action opening a form dialog for every report setting (name, output format, database URL, SQL, chart, grouping/aggregations/pivot, run-time parameters). A "Test query" button runs the SQL with the parameter defaults and shows the first 20 rows, rolled back so it can never write. Edits save in place and keep sections the form has no field for (e.g. `delivery:`)
- ✅ Core report generation, config-driven YAML reports with dynamic parameters, PDF export (table + chart), SQLAlchemy data-source abstraction, scheduling engine, HTML and multi-sheet Excel export, template management, and runtime-parameterised reports
- ✅ HTML email body – `body_format: html` in the email delivery config inlines an HTML report as the message body while still attaching it

---

## 🟡 Medium Priority (Important)

These features make the tool more useful and professional.

- **Template Versioning** – Templates are stored and editable already (Excel/YAML, GUI editor); add version history so users can compare and roll back edits.
- **Multi-format runs** – Let one report produce several formats (`output: [pdf, html, excel]`) in a single run and deliver them together.

---

## 🟢 Low Priority (Nice‑to‑Have)

Enhancements that add polish but are not required for the first release.

- **Dashboard Integration** – Push report data to Power BI, Tableau, or other dashboards via APIs.

- **Alerting** – Send alerts if a metric (e.g., revenue) drops below a threshold.

- **More Chart Types** – Support for pie, scatter, and area charts.

- **Caching** – Cache query results for frequently run reports to reduce database load.

---

## 🚀 Long‑Term Vision (Ambitious / Experimental)

- **Natural Language Query** – Allow users to describe the report in plain English and auto‑generate the SQL via an LLM.
- **Interactive Report Preview** – A web‑based report viewer that allows drill‑down into data.
- **Data Quality Checks** – Automatically validate data completeness and flag outliers.
- **Versioned Report Runs** – Store every generated report with its parameters and output, enabling “time‑travel” comparison.
