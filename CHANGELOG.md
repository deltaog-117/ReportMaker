# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- `reportmaker validate --config <path>` command to check a report configuration without generating a report.
- Semantic configuration validation beyond Pydantic's structural checks: database URL, Jinja2 syntax, cron expression, and chart column validity, wired into `run` and `schedule add` so invalid configs fail fast with actionable messages.
- `delivery` feature: reports can be delivered via a `delivery:` section in the report YAML — copied to a local directory (`channel: local`) or sent as an SMTP email attachment (`channel: email`) — triggered automatically after `run` and after each successful scheduled run.
- `.gitignore` for the Python project (was previously missing, resulting in `__pycache__` and compiled `.pyc` files being tracked).

### Fixed
- `schedule start` now raises a clear error message for an invalid cron expression in `schedules.yaml` instead of letting a raw APScheduler exception surface.

---

## [0.1.0] - 2026-09-07

### Added
- Initial project scaffold with feature-first architecture (`report_generation`, `scheduling`, `delivery`, `data_sources`, `template_management`).
- Core report generation pipeline: SQL extraction, pandas transformation, PDF rendering with `reportlab`.
- HTML and Excel export renderers.
- Scheduling engine using APScheduler (cron and interval triggers).
- Template management via Excel spreadsheets (import/export/validate).
