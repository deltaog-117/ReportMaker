# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- Email delivery option `body_format: html`: inlines an HTML report as the message body (with a plain-text fallback), while still attaching the file. The default stays `text`; a non-HTML report with `body_format: html` is reported as a failed delivery.
- Visual template editor in the GUI's Templates tab: "New template" and a per-row "Edit" action open a dialog covering every report setting (name, description, output format, database URL, SQL, chart, group-by, aggregations, pivot, and run-time parameters), with every problem reported at once on save. A "Test query" button runs the SQL with the parameters' default values and shows the first 20 rows; the connection is never committed, so a mistyped `UPDATE`/`DELETE` is rolled back.
- `TemplateManager.save_config()`: stores a validated `ReportConfig` as a YAML template, refusing to overwrite unless forced and carrying over top-level sections the model does not know (such as `delivery:`) from the file it replaces.
- The GUI's scheduler now runs inside the `reportmaker gui` process itself (an APScheduler `BackgroundScheduler`, started and stopped with the app), so schedules fire without a separate `reportmaker schedule start`. A schedule added, removed, or toggled from the Schedules tab takes effect on that same running scheduler immediately, instead of only after a restart.
- Enable/disable toggle per schedule in the Schedules tab, backed by `SchedulerService.set_enabled()`.
- A bounded run-history log (`run_history.yaml`, `RunHistoryStore`, capped at 200 records) and a "view run history" dialog per schedule, showing each run's outcome, duration, and output path or error.
- Scheduled reports run from the GUI are now delivered the same way as the CLI daemon's: `gui.services.deliver_after_schedule_run()` honours a report's `delivery:` section.
- `scripts/check` (currently `pytest -q`; lint/type checks are pending a separate cleanup of pre-existing `ruff`/`mypy` debt — see Fixed).
- `gui` feature and `reportmaker gui` command: a browser-based interface (NiceGUI) for non-technical users. Run a report from an auto-generated parameter form, preview or download the result, browse past reports, add and remove schedules using plain-language choices (daily/weekly/monthly/every N minutes) instead of cron, and import, export, or delete Excel templates. Serves on `127.0.0.1` only by default. Install with `pip install -e ".[gui]"` (requires Python 3.10+); the CLI is unaffected when the extra is not installed.
- `deliver_if_configured()` in the `delivery` feature: delivers a report when its YAML has a `delivery:` section, returning `None` when it doesn't and a failed result (instead of raising) when the section is malformed.
- `pytest-asyncio` dev dependency and `tests/conftest.py` so the GUI pages can be tested with NiceGUI's simulated browser.
- `reportmaker validate --config <path>` command to check a report configuration without generating a report.
- Semantic configuration validation beyond Pydantic's structural checks: database URL, Jinja2 syntax, cron expression, and chart column validity, wired into `run` and `schedule add` so invalid configs fail fast with actionable messages.
- `delivery` feature: reports can be delivered via a `delivery:` section in the report YAML — copied to a local directory (`channel: local`) or sent as an SMTP email attachment (`channel: email`) — triggered automatically after `run` and after each successful scheduled run.
- `.gitignore` for the Python project (was previously missing, resulting in `__pycache__` and compiled `.pyc` files being tracked).

### Fixed
- Four pre-existing, unrelated test failures blocking the new `scripts/check` (`test_pandas_transformer_invalid_aggregation`, `test_sqlalchemy_extractor_success`, `test_process_parameters_defaults`, `test_process_parameters_override`): two asserted outcomes that contradicted their own sibling tests or the implementation's contract, and two referenced a `get_engine` name `report_generation/services.py` never had and an outdated `.extract()` call signature. No production code changed.
- Templates imported from Excel (`reportmaker template import`) could not be validated, exported, or run: enum values (`output`, parameter `type`) were written to YAML as `!!python/object` tags that `yaml.safe_load` refuses to read. `save_yaml_config` now writes enums as plain values. Templates imported before this fix must be re-imported.
- `schedule start` now raises a clear error message for an invalid cron expression in `schedules.yaml` instead of letting a raw APScheduler exception surface.

---

## [0.1.0] - 2026-09-07

### Added
- Initial project scaffold with feature-first architecture (`report_generation`, `scheduling`, `delivery`, `data_sources`, `template_management`).
- Core report generation pipeline: SQL extraction, pandas transformation, PDF rendering with `reportlab`.
- HTML and Excel export renderers.
- Scheduling engine using APScheduler (cron and interval triggers).
- Template management via Excel spreadsheets (import/export/validate).
