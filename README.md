# ReportMaker

Dynamic Report Generator – automatically produces PDF, HTML, and Excel reports from SQL data.

## Features
- **Report Generation** – Build reports with custom queries and transformations.
- **Scheduling** – Run reports on a schedule (cron‑compatible).
- **Delivery** – Save locally, email, or push to dashboards.
- **Data Sources** – Connect to multiple databases (PostgreSQL, SQLite, etc.).
- **Template Management** – Store and reuse query templates.
- **Browser Interface** – Run reports, browse results, and manage schedules and templates without the command line.

## Installation
```bash
pip install -e ".[dev]"
```

To use the browser interface as well (requires Python 3.10+):
```bash
pip install -e ".[gui]"
```

## Usage
Command line:
```bash
reportmaker run --config config.yaml
```

Browser interface (no command line knowledge needed after launch):
```bash
reportmaker gui
```
Your browser opens at `http://127.0.0.1:8080`. Download the blank Excel template from the **Templates** tab, fill it in, upload it, then pick it on the **Run a report** tab.

The interface only listens on your own computer by default. Schedules added in the interface fire only while the scheduler is running (`reportmaker schedule start`).
