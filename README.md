# ReportMaker

Dynamic Report Generator – automatically produces PDF, HTML, and Excel reports from SQL data.

## Features
- **Report Generation** – Build reports with custom queries and transformations.
- **Scheduling** – Run reports on a schedule (cron‑compatible).
- **Delivery** – Save locally, email, or push to dashboards.
- **Data Sources** – Connect to multiple databases (PostgreSQL, SQLite, etc.).
- **Template Management** – Store and reuse query templates.

## Installation
```bash
pip install -e ".[dev]"

Usage
bash
Copy
Download

reportmaker run --config config.yaml

