# 📘 DIARY.md

## Architectural Decision Log

*This document serves as a chronological record of architectural decisions, trade-offs, and reasoning throughout the project's lifecycle. Just as Git tracks code changes, this diary tracks the **why** behind the code.*

---

## 📋 Decision Index

| Date | Decision Area | Choice | Status |
|------|---------------|--------|--------|
| 2026-09-07 | Language & Architecture | Python + Feature-First | ✅ Confirmed |
| 2026-09-07 | Core Report Generation | Pluggable Pipeline with Stages | ✅ Confirmed |
| 2026-09-08 | Dynamic Parameters | Jinja2 Templating with Validation | ✅ Confirmed |
| 2026-09-08 | Chart Rendering | Matplotlib + ReportLab | ✅ Confirmed |
| 2026-09-09 | Scheduling | APScheduler In-Process Daemon | ✅ Confirmed |
| 2026-09-09 | Schedule Storage | YAML File | ✅ Confirmed |
| 2026-09-10 | Template Management | Excel Spreadsheet ↔ YAML | ✅ Confirmed |
| 2026-09-11 | Multi-Format Export | One Renderer Per Format | ✅ Confirmed |
| 2026-09-15 | Configuration Validation | Pydantic + Semantic Pre-Flight Checks | ✅ Confirmed |
| 2026-09-15 | Delivery Options | Feature-First Channel Abstraction, Wired via `main.py` | ✅ Confirmed |
| 2026-09-19 | GUI Interface | NiceGUI Python-Only Web UI (`reportmaker gui`) | ✅ Confirmed |
| 2026-09-27 | Embedded Scheduler in the GUI | `BackgroundScheduler` Singleton on GUI Lifecycle Hooks | ✅ Confirmed |
| 2026-10-20 | Visual Template Editor | Form Dialog over a String-Typed Draft Model | ✅ Confirmed |

---

## 📝 Decision Entries

### Decision 1: Language & Architecture

**Date:** 2026-09-07  
**Status:** Confirmed

---

#### Context / Background

I needed to build a **dynamic report generator** that pulls data from SQL databases, transforms it, and exports to PDF (later HTML, Excel). The tool must be extensible, maintainable, and allow non-coders to add new reports via configuration files. The architecture must follow the "feature-first" principle where each business capability is independent and deletable without breaking the rest of the system.

**Key requirements:**
- Cross-platform (Linux/Windows)
- Easy for non-coders to add reports
- Observability (logs, metrics)
- Extensible (add new output formats, data sources, chart types)
- Type-safe (no silent failures)
- Property-tested (fuzz logic)

---

#### Options Considered

**Option A: Go (with Chi or similar)**

| Aspect | Assessment |
|--------|------------|
| **Advantages** | • Single binary distribution <br> • Excellent concurrency <br> • Fast compilation <br> • Strong standard library |
| **Disadvantages** | • Less mature data science ecosystem <br> • No pandas equivalent <br> • Fewer libraries for PDF/chart generation <br> • Manual YAML/JSON parsing |
| **Implementation Difficulty** | Hard |
| **Fit with Constraints** | Poor — reporting needs pandas/matplotlib-level tooling |

**Option B: Python (with Click for CLI)**

| Aspect | Assessment |
|--------|------------|
| **Advantages** | • Mature data science ecosystem (pandas, matplotlib, reportlab) <br> • Rapid prototyping <br> • Excellent YAML/JSON support (Pydantic) <br> • Rich CLI frameworks (click) <br> • Property-based testing (hypothesis) |
| **Disadvantages** | • Distribution complexity (needs venv/pip) <br> • Slower execution <br> • GIL limits concurrency |
| **Implementation Difficulty** | Easy-Medium |
| **Fit with Constraints** | Excellent — matches the reporting and data transformation needs |

**Option C: Rust (with Axum or similar)**

| Aspect | Assessment |
|--------|------------|
| **Advantages** | • Maximum type safety <br> • Zero-cost abstractions <br> • Single binary distribution <br> • Excellent performance |
| **Disadvantages** | • Steep learning curve <br> • Immature data science ecosystem <br> • Slow compile times <br> • Hard to iterate quickly |
| **Implementation Difficulty** | Extreme |
| **Fit with Constraints** | Poor — data transformation requires pandas-level tooling |

---

#### Decision & Rationale

**Chosen Option:** Python

**Reasoning:**

I chose Python for the following reasons:

1. **Data Science Ecosystem** — Pandas, matplotlib, and reportlab provide battle-tested solutions for data transformation, charting, and PDF generation. Writing equivalent functionality in Go or Rust would take months.

2. **Rapid Prototyping** — Python's dynamic nature and REPL allow quick iteration, essential for a "vibe coding" workflow.

3. **Type Hints** — Modern Python with Pydantic and mypy provides strong type safety, catching bugs at development time.

4. **Non-Coder Extensibility** — YAML configuration with Pydantic validation allows business users to add new reports without writing Python.

5. **Property-Based Testing** — Hypothesis integrates seamlessly with pytest, enabling fuzz testing of invariants.

**Trade-offs accepted:**
- **Distribution complexity** — Users must have Python 3.9+ and install dependencies via pip. Target audience (analysts, data teams) is comfortable with Python.
- **Performance** — Reports are not time-critical (sub-second to few seconds). Python's performance is more than adequate.
- **Concurrency** — GIL limits parallelism, but reports run sequentially. Acceptable.

---

#### Implementation Notes

- Use `src/` layout with `pyproject.toml` for modern Python packaging.
- Feature-first architecture: top-level directories under `src/reportmaker/features/` named after business capabilities (`report_generation`, `scheduling`, `delivery`, `data_sources`, `template_management`).
- Shared infrastructure in `src/reportmaker/shared/` (database, logging, config, file utils).
- Tests mirror source structure (`tests/unit/features/`).
- Use `ruff` for linting/formatting, `mypy` for type checking, `pytest` for testing, `hypothesis` for property-based tests.

---

#### References

- [Python Packaging User Guide](https://packaging.python.org/)
- [Pydantic Documentation](https://docs.pydantic.dev/)
- [Ruff Documentation](https://docs.astral.sh/ruff/)

---

#### Review / Update Log

| Date | Update | Author |
|------|--------|--------|
| 2026-09-07 | Initial decision | deltaog-117 |
| 2026-09-09 | Confirmed after successful MVP | deltaog-117 |

---

### Decision 2: Core Report Generation

**Date:** 2026-09-07  
**Status:** Confirmed

---

#### Context / Background

Implement the core report generation feature: read a YAML config, execute a SQL query, transform the data (groupby, pivot, aggregations), and export to PDF with a table and chart. The implementation must be extensible (support HTML, Excel later) and testable.

**Key requirements:**
- Extensible — new output formats/chart types should be easy to add
- Testable — each stage (extract, transform, render) independently testable
- Observability — logs and metrics for each stage
- No hardcoded logic — configuration-driven

---

#### Options Considered

**Option A: Monolithic Pipeline**

| Aspect | Assessment |
|--------|------------|
| **Advantages** | • Simplest to implement <br> • Single code path <br> • Low overhead |
| **Disadvantages** | • Brittle — adding new format requires modifying core function <br> • Hard to test <br> • Violates Open/Closed principle <br> • Fails the "Delete Test" |
| **Implementation Difficulty** | Low |
| **Fit with Constraints** | Poor — not extensible or testable |

**Option B: Pluggable Pipeline with Stages**

| Aspect | Assessment |
|--------|------------|
| **Advantages** | • Modular — each stage independent <br> • Extensible — add new Extractors, Transformers, Renderers <br> • Testable — unit test each stage <br> • Passes the "Delete Test" <br> • Clear separation of concerns |
| **Disadvantages** | • More upfront design <br> • More classes/interfaces <br> • Slightly higher complexity |
| **Implementation Difficulty** | Medium |
| **Fit with Constraints** | Excellent — matches all requirements |

**Option C: Template-Driven (HTML + WeasyPrint)**

| Aspect | Assessment |
|--------|------------|
| **Advantages** | • Rich styling via HTML/CSS <br> • Reuse templates for HTML output <br> • Better for charts (Plotly) |
| **Disadvantages** | • External dependency (WeasyPrint/wkhtmltopdf) <br> • Slower rendering <br> • More complex setup <br> • Less control over PDF output |
| **Implementation Difficulty** | Medium-High |
| **Fit with Constraints** | Partial — good for styling but introduces external dependencies |

---

#### Decision & Rationale

**Chosen Option:** Pluggable Pipeline with Stages

**Reasoning:**

I chose the pluggable pipeline because:

1. **Extensibility** — Adding a new output format (HTML, Excel) is just adding a new Renderer class. Adding a new chart type is just adding logic to the PDFRenderer. No changes to core orchestration.

2. **Testability** — Each stage can be unit-tested in isolation. Property-based tests can verify invariants (e.g., "groupby+sum preserves total sum").

3. **Delete Test** — You can delete the entire `report_generation` feature, and the rest of the app still compiles (minus that feature). The pipeline stages are independent of other features.

4. **Clear separation** — The Extractor handles database queries, Transformer handles data manipulation, Renderer handles output. This aligns with the Single Responsibility Principle.

**Trade-offs accepted:**
- **More classes** — Yes, but each class is small and focused. The overhead is acceptable.
- **Design complexity** — The pipeline abstraction is well-understood and documented.

---

#### Implementation Notes

- Define abstract interfaces: `Extractor`, `Transformer`, `Renderer`.
- Concrete implementations: `SQLAlchemyExtractor` (uses config URL), `PandasTransformer` (groupby/pivot/aggregations), `PDFRenderer` (reportlab + matplotlib).
- Orchestrator: `ReportPipeline` runs stages sequentially, collects metrics, logs each step.
- Factory: `create_default_pipeline()` for convenience.
- PDF includes a table and a bar/line chart (matplotlib rendered to PNG, embedded via reportlab).

---

#### References

- [ReportLab Documentation](https://www.reportlab.com/docs/reportlab-userguide.pdf)
- [Matplotlib Documentation](https://matplotlib.org/stable/contents.html)
- [Pandas Documentation](https://pandas.pydata.org/docs/)

---

#### Review / Update Log

| Date | Update | Author |
|------|--------|--------|
| 2026-09-07 | Initial decision | deltaog-117 |
| 2026-09-07 | Fixed chart embedding (BytesIO -> Image) | deltaog-117 |
| 2026-09-11 | Moved ABCs to interfaces.py for multi-format support | deltaog-117 |

---

### Decision 3: Dynamic Parameters

**Date:** 2026-09-08  
**Status:** Confirmed

---

#### Context / Background

Allow users to pass parameters at runtime (e.g., date ranges, product names) without editing the YAML configuration file. The system should validate parameter types (string, integer, date, boolean) and provide defaults.

**Key requirements:**
- Safe (no SQL injection)
- Type validation
- Support for defaults and required parameters
- CLI and file-based parameter passing
- Conditional logic in queries (e.g., `{% if product %}`)

---

#### Options Considered

**Option A: Simple String Replacement**

| Aspect | Assessment |
|--------|------------|
| **Advantages** | • Trivial to implement <br> • No dependencies <br> • Flexible |
| **Disadvantages** | • SQL injection risk <br> • No type validation <br> • Errors surface at runtime <br> • Cannot handle complex cases |
| **Implementation Difficulty** | Low |
| **Fit with Constraints** | Poor — security risk is unacceptable |

**Option B: Jinja2 Templating with Validation**

| Aspect | Assessment |
|--------|------------|
| **Advantages** | • Safe (controlled rendering) <br> • Type validation via schema <br> • Supports conditionals, loops, filters <br> • Declarative schema <br> • Already have Jinja2 in dependencies |
| **Disadvantages** | • Adds complexity <br> • Slightly slower (negligible) |
| **Implementation Difficulty** | Medium |
| **Fit with Constraints** | Excellent — balances security, flexibility, and maintainability |

**Option C: SQLAlchemy Bound Parameters**

| Aspect | Assessment |
|--------|------------|
| **Advantages** | • Maximum security (immune to injection) <br> • Database-optimised <br> • Already have SQLAlchemy |
| **Disadvantages** | • Cannot use conditional logic (e.g., `WHERE product IN ({{ products }})`) <br> • Cannot handle dynamic column names <br> • Requires SQL syntax changes (`:name` instead of `{{}}`) |
| **Implementation Difficulty** | Low-Medium |
| **Fit with Constraints** | Partial — secure but inflexible |

---

#### Decision & Rationale

**Chosen Option:** Jinja2 Templating with Validation

**Reasoning:**

I chose Jinja2 because:

1. **Security** — We control the rendering environment and validate all inputs against a schema. SQL injection is prevented because we only substitute validated values.

2. **Flexibility** — Supports conditional logic (`{% if product %}`), loops, filters, and complex expressions.

3. **User-Friendly** — Non-coders can understand `{{ start_date }}` in the query. The schema is declarative and self-documenting.

4. **Already in Stack** — Jinja2 was already a dependency (used for HTML templates).

**Trade-offs accepted:**
- **Additional complexity** — Need to define schema, write renderer, integrate with CLI. The effort is justified.
- **Slight performance overhead** — Jinja2 rendering adds microseconds, negligible compared to SQL query execution.

---

#### Implementation Notes

- Add `parameters` section to `ReportConfig` with `ParameterSchema` (name, type, required, default, description).
- Types: `string`, `integer`, `float`, `date`, `boolean`.
- `process_parameters()` validates and casts inputs, merges with defaults.
- `render_sql_query()` uses Jinja2 to substitute placeholders in the SQL.
- CLI: `--param key=value` (multiple) and `--params-file file.json`.
- Report title can also contain placeholders (e.g., `"Sales Report for {{ product }}"`).
- **Fix (2026-09-11):** DATE parameters cast to `datetime.date` (not `datetime.datetime`) so templates render `2026-09-05` instead of `2026-09-05 00:00:00`.

---

#### References

- [Jinja2 Documentation](https://jinja.palletsprojects.com/)
- [Pydantic Documentation](https://docs.pydantic.dev/latest/)

---

#### Review / Update Log

| Date | Update | Author |
|------|--------|--------|
| 2026-09-08 | Initial decision | deltaog-117 |
| 2026-09-08 | Implemented and tested | deltaog-117 |
| 2026-09-11 | Cast DATE params to date for cleaner titles | deltaog-117 |

---

### Decision 4: Chart Rendering

**Date:** 2026-09-08  
**Status:** Confirmed

---

#### Context / Background

The PDFRenderer needs to include a chart (bar or line) in the PDF. The chart should be generated from the processed data and embedded in the PDF document.

**Key requirements:**
- Work with ReportLab's document model
- Support bar and line charts
- Clean visual appearance
- Handle missing data gracefully
- No external dependencies (beyond matplotlib)

---

#### Options Considered

**Option A: ReportLab's Built-in Charting**

| Aspect | Assessment |
|--------|------------|
| **Advantages** | • No extra dependencies <br> • Native integration with ReportLab <br> • Good performance |
| **Disadvantages** | • Limited chart types <br> • Ugly default styling <br> • Complex API <br> • Poor documentation |
| **Implementation Difficulty** | Medium-Hard |
| **Fit with Constraints** | Poor — charts would look dated |

**Option B: Matplotlib + PIL/ReportLab Image**

| Aspect | Assessment |
|--------|------------|
| **Advantages** | • Rich chart types and styling <br> • Matplotlib has excellent defaults <br> • Well-documented <br> • Can embed as PNG via ReportLab Image |
| **Disadvantages** | • Adds matplotlib dependency (already in stack) <br> • Slightly larger PDF size (PNG compression) <br> • Need to manage PIL/bytes IO |
| **Implementation Difficulty** | Easy |
| **Fit with Constraints** | Excellent — professional-looking charts with minimal effort |

**Option C: Plotly + Static Image**

| Aspect | Assessment |
|--------|------------|
| **Advantages** | • Interactive charts <br> • Beautiful defaults <br> • Export to PNG/PDF |
| **Disadvantages** | • Heavy dependency <br> • Requires Kaleido for static export <br> • Overkill for v1.0 |
| **Implementation Difficulty** | Medium |
| **Fit with Constraints** | Overkill — would complicate deployment |

---

#### Decision & Rationale

**Chosen Option:** Matplotlib + PIL/ReportLab Image

**Reasoning:**

I chose Matplotlib because:

1. **Already in Stack** — Matplotlib was already a dependency for data visualisation. No new dependencies.

2. **Professional Output** — Matplotlib produces publication-quality charts with minimal configuration.

3. **Simplicity** — Generating a chart is 5 lines of code: create figure, plot data, save to BytesIO, embed via ReportLab Image.

4. **Flexibility** — Matplotlib supports many chart types (bar, line, pie, scatter, area) and customisation options.

**Trade-offs accepted:**
- **PNG embedding** — The chart is a raster image in the PDF. For v1.0, this is acceptable. Future versions could use SVG for vector quality.
- **Matplotlib debug noise** — The font manager logs are verbose; we suppress them with `logging.getLogger("matplotlib.font_manager").setLevel(logging.WARNING)`.

---

#### Implementation Notes

- Use `plt.subplots(figsize=(6, 4))` for a reasonable size.
- Save to `io.BytesIO` with `plt.savefig(..., format='png', dpi=100, bbox_inches='tight')`.
- Embed with `reportlab.platypus.Image(img_buf, width=6*inch, height=4*inch)`.
- Suppress matplotlib debug logs to keep console clean.
- **Critical fix:** ReportLab's `Image` flowable expects a file-like object, not an `ImageReader`. Pass the `BytesIO` buffer directly (after `seek(0)`).

---

#### References

- [Matplotlib Documentation](https://matplotlib.org/stable/contents.html)
- [ReportLab Platypus Image](https://www.reportlab.com/docs/reportlab-userguide.pdf)

---

#### Review / Update Log

| Date | Update | Author |
|------|--------|--------|
| 2026-09-08 | Initial decision | deltaog-117 |
| 2026-09-08 | Fixed chart embedding (BytesIO -> Image) | deltaog-117 |

---

### Decision 5: Scheduling Implementation

**Date:** 2026-09-09  
**Status:** Confirmed

---

#### Context / Background

Add the ability to run reports automatically on a schedule (daily, weekly, monthly, or custom intervals). The scheduler should be cross-platform (Linux/Windows) and store schedules in a configuration file.

**Key requirements:**
- Cross-platform (Linux, Windows, macOS)
- Schedules stored in config (not OS-specific crontabs)
- CLI commands: add, list, remove, start
- Integration with existing `reportmaker run` logic
- Logging and observability for each run

---

#### Options Considered

**Option A: System Scheduler (cron / Task Scheduler)**

| Aspect | Assessment |
|--------|------------|
| **Advantages** | • Zero overhead (OS handles it) <br> • Reliable and battle-tested <br> • Persists across reboots <br> • No new dependencies |
| **Disadvantages** | • Platform-specific instructions <br> • User-managed (crontab -e) <br> • No central management <br> • Hard to list/remove from within app |
| **Implementation Difficulty** | Low |
| **Fit with Constraints** | Poor — user experience is fragmented |

**Option B: In-process Scheduler (APScheduler)**

| Aspect | Assessment |
|--------|------------|
| **Advantages** | • Cross-platform (Linux, Windows, macOS) <br> • Schedules stored in config (YAML) <br> • CLI commands for management <br> • Rich triggers (cron, interval, calendar) <br> • Logging and metrics built-in <br> • Extensible (add email alerts later) |
| **Disadvantages** | • Requires a running daemon <br> • Added dependency (APScheduler) <br> • Need to handle daemonisation |
| **Implementation Difficulty** | Medium |
| **Fit with Constraints** | Excellent — professional and user-friendly |

**Option C: Hybrid (Cron + Config Checker)**

| Aspect | Assessment |
|--------|------------|
| **Advantages** | • Simple daemon (run once per minute) <br> • Config stored in YAML <br> • No extra dependencies <br> • Works with a single cron job |
| **Disadvantages** | • Overhead (checking every minute) <br> • Timing latency (up to 1 minute) <br> • Still requires OS scheduler for the checker |
| **Implementation Difficulty** | Low-Medium |
| **Fit with Constraints** | Partial — functional but not elegant |

---

#### Decision & Rationale

**Chosen Option:** In-process Scheduler (APScheduler)

**Reasoning:**

I chose APScheduler because:

1. **Professional User Experience** — Users can manage schedules from within the app: `reportmaker schedule add`, `schedule list`, `schedule remove`. Cleaner than editing crontab files.

2. **Cross-Platform** — APScheduler works the same on Linux, Windows, and macOS. No platform-specific instructions.

3. **Rich Triggers** — Supports cron expressions (`0 9 * * *`) and interval triggers (`--interval 3600` for hourly).

4. **Observability** — We can log every run, capture errors, and store last_run timestamps.

5. **Extensibility** — Later we can add email notifications on success/failure, retries, and a web dashboard.

**Trade-offs accepted:**
- **Daemon Requirement** — Users must keep the scheduler running (foreground or via systemd).
- **Dependency** — APScheduler is well-maintained and widely used. Low-risk addition.

---

#### Implementation Notes

- Use `BlockingScheduler` for foreground mode.
- Store schedules in `schedules.yaml` for simplicity (see Decision 6).
- Each schedule has: name, trigger (cron or interval), report_config path, parameters, enabled flag, last_run.
- `SchedulerService` manages loading/saving schedules and adding/removing jobs.
- The `_job_function()` calls `generate_report()` with the stored parameters.
- Event listeners log job execution and errors.
- CLI commands: `schedule add`, `schedule list`, `schedule remove`, `schedule start`.

---

#### References

- [APScheduler Documentation](https://apscheduler.readthedocs.io/)
- [Cron Expression Format](https://en.wikipedia.org/wiki/Cron)

---

#### Review / Update Log

| Date | Update | Author |
|------|--------|--------|
| 2026-09-09 | Initial decision and implementation | deltaog-117 |

---

### Decision 6: Schedule Storage

**Date:** 2026-09-09  
**Status:** Confirmed

---

#### Context / Background

Schedules created via `reportmaker schedule add` need to be persisted somewhere, so they survive process restarts and can be listed/edited later.

**Key requirements:**
- Simple to inspect and edit by hand
- Git-friendly (so schedules can be version-controlled)
- No additional dependencies
- Can grow to dozens of schedules without performance issues

---

#### Options Considered

**Option A: YAML File (`schedules.yaml`)**

| Aspect | Assessment |
|--------|------------|
| **Advantages** | • Human-readable <br> • Git-friendly (nice diffs) <br> • Already using YAML for report configs <br> • No new dependencies <br> • Easy to edit by hand |
| **Disadvantages** | • Not suitable for thousands of schedules <br> • No concurrent-write safety (fine for single-user) |
| **Implementation Difficulty** | Easy |
| **Fit with Constraints** | Excellent — matches existing conventions |

**Option B: SQLite Database**

| Aspect | Assessment |
|--------|------------|
| **Advantages** | • Concurrent-safe <br> • Query-able <br> • Scales to many schedules |
| **Disadvantages** | • Binary format — harder to inspect <br> • Not Git-friendly <br> • More code (schema, migrations) <br> • Overkill for typical use |
| **Implementation Difficulty** | Medium |
| **Fit with Constraints** | Overkill |

**Option C: JSON File**

| Aspect | Assessment |
|--------|------------|
| **Advantages** | • Standard library support <br> • Human-readable |
| **Disadvantages** | • No comments <br> • No multi-line strings <br> • Less pleasant to edit than YAML |
| **Implementation Difficulty** | Easy |
| **Fit with Constraints** | Acceptable but inferior to YAML |

---

#### Decision & Rationale

**Chosen Option:** YAML File

**Reasoning:**

1. **Consistency** — Report configs are already YAML. Using YAML for schedules keeps the project coherent.
2. **Human-readable** — Users can inspect and edit schedules directly.
3. **Git-friendly** — Schedules can be version-controlled alongside report configs.
4. **No new dependencies** — PyYAML is already in the stack.
5. **Good enough for scale** — Typical usage is dozens of schedules, not thousands.

**Trade-offs accepted:**
- **No concurrent-write safety** — Two `schedule add` commands running simultaneously could clobber each other. Acceptable for single-user CLI usage.
- **Not query-able** — Listing requires loading the whole file. Fine at this scale.

---

#### Implementation Notes

- Default path: `./schedules.yaml` (configurable via `--schedules-file`).
- Format:
  ```yaml
  daily_sales:
    name: daily_sales
    cron: "0 9 * * *"
    report_config: templates/daily_sales.yaml
    parameters:
      start_date: "2026-09-01"
    enabled: true
    last_run: 2026-09-11T09:00:00
  ```
- `SchedulerService._load_schedules()` reads the file on startup; `_save_schedules()` writes back after every mutation.

---

#### References

- [PyYAML Documentation](https://pyyaml.org/wiki/PyYAMLDocumentation)

---

#### Review / Update Log

| Date | Update | Author |
|------|--------|--------|
| 2026-09-09 | Initial decision | deltaog-117 |

---

### Decision 7: Template Management

**Date:** 2026-09-10  
**Status:** Confirmed

---

#### Context / Background

Non-coders (business analysts) need to create and edit report templates without touching YAML or the terminal. They are comfortable with Excel but not with code, Git, or command-line flags.

**Key requirements:**
- Analysts must be able to define reports using Excel
- Zero YAML syntax exposure
- Validation before the template is stored
- Round-trip: edit in Excel → import → run → export back for editing
- No new heavy dependencies

---

#### Options Considered

**Option A: Interactive Terminal Wizard**

| Aspect | Assessment |
|--------|------------|
| **Advantages** | • Zero syntax — user answers questions <br> • No new dependencies (uses `click.prompt`) <br> • Cross-platform <br> • Self-documenting |
| **Disadvantages** | • Still requires opening a terminal <br> • Rigid — only pre-approved query patterns <br> • No live preview |
| **Implementation Difficulty** | Low |
| **Fit with Constraints** | Good — but analysts still fear the terminal |

**Option B: Excel Spreadsheet ↔ YAML**

| Aspect | Assessment |
|--------|------------|
| **Advantages** | • Familiar tool (Excel/LibreOffice Calc) <br> • Shareable via email/SharePoint <br> • Reviewable by managers <br> • Versionable in OneDrive/SharePoint <br> • Extensible with new sheets/columns <br> • No new dependencies (openpyxl already in stack) |
| **Disadvantages** | • One terminal command required to import <br> • No live preview <br> • SQL still exposed (but with example rows) <br> • Awkward for very complex conditional logic |
| **Implementation Difficulty** | Low-Medium |
| **Fit with Constraints** | Excellent — matches analyst workflow |

**Option C: Local Web UI (Point-and-Click Builder)**

| Aspect | Assessment |
|--------|------------|
| **Advantages** | • Truly no-coder friendly <br> • Live preview <br> • Dashboard of existing reports <br> • Extensible to team sharing |
| **Disadvantages** | • Requires FastAPI + uvicorn (new dependencies) <br> • More code (routes, templates, static assets) <br> • Security considerations <br> • 1–2 weeks for v1 |
| **Implementation Difficulty** | High |
| **Fit with Constraints** | Good long-term, but premature for v1 |

---

#### Decision & Rationale

**Chosen Option:** Excel Spreadsheet ↔ YAML

**Reasoning:**

1. **Familiar tool** — Analysts live in Excel. Zero learning curve.
2. **Shareable and reviewable** — A spreadsheet can be emailed, stored in SharePoint, and reviewed by managers.
3. **Guided structure** — The 5-sheet layout (Report, Chart, Transform, Aggregations, Parameters) walks the analyst through every option without requiring them to remember syntax.
4. **No new dependencies** — openpyxl is already used elsewhere.
5. **Bridges to the GUI later** — The wizard's questions become form fields in the eventual web UI. Building the Excel layout now informs that design.

**Trade-offs accepted:**
- **SQL still exposed** — The `SQL Query` cell is raw SQL. Analysts will need a developer to help write the first query. This is acceptable; the alternative (visual query builder) is out of scope for v1.
- **Import step required** — The analyst runs one command (`reportmaker template import file.xlsx`). We'll document this clearly.
- **No live preview** — They see the report only after running it. Acceptable; the wizard offers to run immediately after import in a future iteration.

---

#### Implementation Notes

- **Layout:** 5 sheets in the Excel file:
  - **Report** — name, description, database URL, SQL query, output format, schedule.
  - **Chart** — kind (bar/line), X column, Y column, title, axis labels.
  - **Transform** — group by, pivot config.
  - **Aggregations** — column → function (sum, mean, count, min, max, std).
  - **Parameters** — name, type, required, default, description.
- **CLI commands:**
  - `template init <file.xlsx>` — create a blank template with example rows.
  - `template import <file.xlsx> [--force] [--name NAME]` — parse, validate, save YAML.
  - `template export <name> <file.xlsx>` — write back a stored YAML as a spreadsheet.
  - `template list` — list all stored templates.
  - `template validate <name>` — validate against the schema.
  - `template delete <name>` — delete a stored template.
- **Storage:** Templates are stored as YAML files under `./templates/` (configurable via `--templates-dir`).
- **Naming:** Filenames are slugified (`Sales Report` → `sales_report.yaml`).

---

#### References

- [openpyxl Documentation](https://openpyxl.readthedocs.io/)
- Related decision: Decision 8 (Multi-Format Export) — Excel is also an output format

---

#### Review / Update Log

| Date | Update | Author |
|------|--------|--------|
| 2026-09-10 | Initial decision and implementation | deltaog-117 |

---

### Decision 8: Multi-Format Export

**Date:** 2026-09-11  
**Status:** Confirmed

---

#### Context / Background

The report generation pipeline already produced PDFs, but users needed additional formats for different audiences: HTML for embedding in emails and web previews, and Excel for analysts who want to pivot, filter, and manipulate the data themselves. Adding these formats had to respect the existing architecture: the `Renderer` interface, the feature-first layout, and the "Delete Test" (each renderer must be independently deletable without breaking the others).

**Key requirements:**
- Share the same extract → transform pipeline (no duplication of data logic)
- HTML output must be self-contained (no external assets — works as email attachment)
- Excel output must leverage native spreadsheet features (styled headers, autofilter, native charts — not just a CSV dump)
- Zero changes to the pipeline orchestrator
- Each renderer must be independently testable

---

#### Options Considered

**Option A: One Renderer Class Per Format**

| Aspect | Assessment |
|--------|------------|
| **Advantages** | • Fits the existing `Renderer` interface — pure addition, no refactor <br> • Passes the Delete Test (each renderer independently removable) <br> • No new heavy dependencies (Jinja2 and openpyxl already in stack) <br> • Excel gets native multi-sheet, styling, and charts <br> • Each renderer is small (~100–150 lines) and independently testable |
| **Disadvantages** | • Layout logic duplicated across renderers (branding changes must be applied in 3 places) <br> • Visual output across formats may drift without a shared theme <br> • Chart handling differs per format (PNG for PDF/HTML, native chart for XLSX) |
| **Implementation Difficulty** | Low-Medium |
| **Fit with Constraints** | Excellent — matches the architecture and delivers v1 quickly |

**Option B: HTML-First with Format Adapters**

| Aspect | Assessment |
|--------|------------|
| **Advantages** | • Single source of truth for layout (HTML/CSS) <br> • CSS gives richer styling than ReportLab platypus <br> • Vector charts (SVG) crisp at any zoom <br> • Future-proof for web-based workflows |
| **Disadvantages** | • New heavy dependency: WeasyPrint requires Cairo, Pango, GDK-Pixbuf (painful on Arch and Windows) <br> • Replaces a working PDF renderer <br> • Excel path awkward: extracting tables from HTML loses multi-sheet and native formatting <br> • Slower PDF generation (~2–3x) <br> • Larger PDF files from embedded CSS and fonts |
| **Implementation Difficulty** | High |
| **Fit with Constraints** | Poor — introduces platform risk and discards working code |

**Option C: Unified Document Model + Format Backends**

| Aspect | Assessment |
|--------|------------|
| **Advantages** | • Ultimate flexibility — one canonical representation drives all formats <br> • Consistent theming at the model level <br> • Extensible to any future format (Markdown, CSV, PowerPoint) <br> • How Pandoc, Sphinx, and Quarto work |
| **Disadvantages** | • Over-engineering for a project with one report layout <br> • Requires designing an intermediate model and refactoring the existing PDF renderer <br> • Risk of premature abstraction <br> • Multi-week effort instead of a few days |
| **Implementation Difficulty** | High |
| **Fit with Constraints** | Poor — premature complexity without evidence it's needed |

---

#### Decision & Rationale

**Chosen Option:** One Renderer Class Per Format

**Reasoning:**

1. **The Renderer interface already exists for exactly this purpose.** Adding `HTMLRenderer` and `ExcelRenderer` is the natural, small, incremental step. The pipeline orchestrator is untouched.

2. **No new dependencies and no platform risk.** Jinja2 (already used for SQL templating) and openpyxl (already used for template management) cover both new formats. WeasyPrint's system libraries would have been a constant source of friction on Arch Linux and Windows.

3. **Excel deserves a native renderer.** Extracting tables from HTML would lose multiple sheets, formatting, freeze panes, autofilter, and native charts — exactly the features Excel users want.

4. **The working PDF renderer stays intact.** Approaches B and C would replace it, with all the risk that entails. Approach A is purely additive.

5. **We can adopt Approach C later if the pain is real.** If we end up with 5+ formats and heavy layout duplication, we'll build the document model then — with concrete evidence of what it needs to express.

**Trade-offs accepted:**
- **Layout duplication** — Branding colours and typography are re-specified per renderer. We'll mitigate by sharing a small `Theme` object from config in a future iteration.
- **Chart rendering differences** — PDF and HTML embed a matplotlib-rendered PNG (via `BytesIO` and base64 respectively); Excel uses a native chart object. This is intentional — each format gets the best of its ecosystem.
- **No cross-format visual consistency guarantee** — Acceptable for v1. Most users pick one format and stick with it.

---

#### Implementation Notes

**Files added:**
- `src/reportmaker/features/report_generation/interfaces.py` — moved `Extractor`, `Transformer`, `Renderer` ABCs here to avoid a circular import between `services.py` and the new `renderers/` subpackage.
- `src/reportmaker/features/report_generation/renderers/__init__.py` — exports `HTMLRenderer` and `ExcelRenderer`.
- `src/reportmaker/features/report_generation/renderers/html.py` — `HTMLRenderer` using Jinja2 with a self-contained inline-CSS template; charts rendered as base64 PNG data URIs.
- `src/reportmaker/features/report_generation/renderers/excel.py` — `ExcelRenderer` using openpyxl with three sheets:
  - **Data** — styled header (dark blue fill, white bold font), alternating row fills, borders, auto column widths, frozen top row, autofilter.
  - **Summary** — row/column counts plus per-numeric-column totals.
  - **Chart** — native Excel `BarChart`/`LineChart` referencing a helper data block.
- `src/reportmaker/features/report_generation/templates/html_report.j2` — Jinja2 HTML template with a modern look (CSS variables, rounded container, alternating table rows, embedded chart image).
- `tests/unit/features/report_generation/test_renderers.py` — 6 unit tests covering HTML/Excel with and without charts, and empty data.

**Files modified:**
- `src/reportmaker/features/report_generation/services.py` — added `create_renderer()` factory; `generate_report()` dispatches by `config.output`; added `OUTPUT_EXTENSIONS` mapping so Excel saves as `.xlsx` (not `.excel`).

**Additional fixes:**
- Cast `DATE` parameters to `datetime.date` so that `{{ start_date }}` renders as `2026-09-05` rather than `2026-09-05 00:00:00`.
- Replaced `datetime.utcnow()` with `datetime.now(timezone.utc)` in the HTML renderer to silence a Python 3.14 deprecation warning.

---

#### References

- [openpyxl charts documentation](https://openpyxl.readthedocs.io/en/stable/charts/introduction.html)
- [Jinja2 templates](https://jinja.palletsprojects.com/en/3.1.x/templates/)
- Related decisions: Decision 2 (Core Report Generation), Decision 3 (Dynamic Parameters)

---

#### Review / Update Log

| Date | Update | Author |
|------|--------|--------|
| 2026-09-11 | Initial decision and implementation | deltaog-117 |
| 2026-09-11 | Added `.xlsx` extension mapping and date-cast fix | deltaog-117 |

---

### Configuration Validation

**Date:** 2026-09-15
**Status:** ✅ Confirmed

---

#### Context / Background

`ReportConfig` and `ScheduleConfig` were already Pydantic models, so structurally malformed YAML (missing fields, wrong types) failed loudly. But a *structurally valid* config could still fail at runtime in ways Pydantic can't catch: a `data_source.url` that isn't a real SQLAlchemy URL, a `data_source.query` with broken Jinja2 syntax, a schedule's `cron` string that APScheduler rejects, or a chart referencing an empty column name. None of these were caught before `reportmaker run` or `reportmaker schedule add`, so they surfaced as a raw traceback mid-run, or — worse — as a silent failure the next time a scheduled job fired.

#### Options Considered

**Option A: Pydantic + wrap exceptions**

| Aspect | Assessment |
|--------|------------|
| **Advantages** | Minimal new code; catches `ValidationError` and re-raises as the existing `ConfigError`; no new dependencies |
| **Disadvantages** | Misses everything Pydantic's structural validation can't see — bad cron, broken Jinja2, unparseable DB URL — so those still fail at runtime |
| **Implementation Difficulty** | Easy |

**Option B: Pydantic + semantic pre-flight checks**

| Aspect | Assessment |
|--------|------------|
| **Advantages** | Catches cron syntax (`CronTrigger.from_crontab`), Jinja2 syntax (`Environment().parse()`), and DB URL validity (`sqlalchemy.engine.url.make_url`) before anything runs; batches every issue into one readable error instead of failing on the first one; reuses dependencies already installed (jinja2, apscheduler, sqlalchemy) |
| **Disadvantages** | More code than Option A; each new config field ideally gets a matching semantic check |
| **Implementation Difficulty** | Medium |

**Option C: JSON Schema validation layer**

| Aspect | Assessment |
|--------|------------|
| **Advantages** | Schema is a portable, language-independent artifact |
| **Disadvantages** | Duplicates validation logic the Pydantic models already express — two sources of truth to keep in sync; adds a new dependency (`jsonschema`) |
| **Implementation Difficulty** | Medium-Hard |

#### Decision & Rationale

**Chosen Option:** B — Pydantic + semantic pre-flight checks

> Option B is the direct extension of the type-driven design already in place (Pillar 1: illegal states unrepresentable), and it's what the roadmap literally asked for — "prevent runtime errors." Every check it needs (`jinja2.Environment`, `apscheduler.CronTrigger`, `sqlalchemy.make_url`) is a dependency the project already has, so there's no new attack surface or supply-chain cost. Option C would have meant maintaining the same rules twice (once as Pydantic types, once as a JSON Schema document), which fights the project's own "make illegal states unrepresentable" pillar rather than serving it.
>
> **Trade-offs accepted:**
> - Semantic checks live in `report_generation/services.py` rather than inside the Pydantic model's own validators, specifically so existing tests that construct `ReportConfig(data_source=DataSourceConfig(url="", query=""))` directly (bypassing config loading) keep working unmodified — semantic validation only runs through the new `load_and_validate_config()` entry point, not on every model construction.
> - The chart-column check (`x_column`/`y_column` must be non-empty) is a hand-written rule rather than a general schema constraint; acceptable since it's the only place today that needs it.

#### Implementation Notes

**Files added:**
- `src/reportmaker/shared/validators.py` — `validate_cron_expression`, `validate_jinja2_syntax`, `validate_database_url`, `validate_email_address`, and `collect_errors` (runs zero-arg checks, gathers `ValueError` messages instead of raising on the first one). Shared because both `report_generation` and `delivery` need email/URL/template checks, and `scheduling` needs the cron check.
- `tests/unit/shared/test_validators.py`, `tests/unit/features/report_generation/test_config_validation.py`

**Files modified:**
- `src/reportmaker/features/report_generation/services.py` — added `validate_report_config_semantics()` and `load_and_validate_config()`; `generate_report()` now calls the latter instead of constructing `ReportConfig` directly.
- `src/reportmaker/features/scheduling/services.py` — `_get_trigger()` now wraps `CronTrigger.from_crontab()` and raises `SchedulingError` with a clear message instead of letting a raw APScheduler exception surface when `schedule start` loads a hand-edited `schedules.yaml`.
- `src/reportmaker/main.py` — added `reportmaker validate --config <path>` (mirrors `template validate`'s output); `run` and `schedule add` now validate before doing anything else and print a clean `❌ ...` message instead of a traceback.

#### References

- Related decision: Delivery Options (below) — reuses the same `ConfigError` / `ValidationError` handling pattern at the CLI boundary.

---

### Delivery Options

**Date:** 2026-09-15
**Status:** ✅ Confirmed

---

#### Context / Background

The roadmap's Medium Priority "Delivery Options" item asked for local file save (already effectively covered by `--output-dir`) and email delivery via SMTP. The `delivery/` feature folder and `shared/email.py` existed as empty scaffold stubs — including `tests/unit/features/delivery/test_models.py` and `test_services.py`, both empty — clearly placeholders for exactly this.

#### Options Considered

**Option A: Bolt email sending into `report_generation`'s `run` CLI command**

| Aspect | Assessment |
|--------|------------|
| **Advantages** | Fastest to ship |
| **Disadvantages** | Violates the Delete Test — deleting `delivery/` wouldn't remove delivery functionality, because there'd be none in `delivery/` to delete; no reuse from `schedule start` |
| **Implementation Difficulty** | Easy |

**Option B: Real `delivery` feature with a channel abstraction**

| Aspect | Assessment |
|--------|------------|
| **Advantages** | Passes the Delete Test — `report_generation` and `scheduling` never import `delivery`; mirrors the existing `Extractor`/`Transformer`/`Renderer` interface pattern in `report_generation/interfaces.py`; fills the already-scaffolded empty test stubs |
| **Disadvantages** | More surface area: new `DeliveryConfig`/`DeliveryResult` models, a `DeliveryHandler` interface, a new `exceptions.py` |
| **Implementation Difficulty** | Medium |

**Option C: Out-of-process delivery worker**

| Aspect | Assessment |
|--------|------------|
| **Advantages** | Decouples delivery timing/retries from report generation |
| **Disadvantages** | Requires message-queue infrastructure this single-user CLI tool has no other need for — pure over-engineering at this stage |
| **Implementation Difficulty** | Hard |

#### Decision & Rationale

**Chosen Option:** B — Real `delivery` feature with a channel abstraction

> Option B was the only one that didn't violate the architecture's own Delete Test. The harder design question was *where the wiring lives*: `ReportConfig` could not gain a `delivery: DeliveryConfig` field, because `report_generation/models.py` importing from `features/delivery/models.py` would mean deleting `delivery/` breaks `report_generation` — exactly the dependency direction the Delete Test forbids. Same problem for `scheduling` calling into `delivery` directly.
>
> The resolution: `delivery:` is a YAML key `ReportConfig` ignores (Pydantic v2 ignores unknown fields by default), and only `main.py` — the composition root, which architecture rule 5 explicitly allows to "inject dependencies into the features" — reads that section and calls `deliver_report()`. For the scheduled path, `SchedulerService` gained a constructor-injected `on_report_generated` callback (plain `Callable`, no import of anything `delivery`-related), and `main.py` wires `_deliver_from_schedule` into it. `scheduling` stays exactly as deletable as it was before this feature existed.
>
> **Trade-offs accepted:**
> - Email addresses are validated with a hand-rolled regex (`shared/validators.validate_email_address`) rather than pulling in `pydantic[email]`/`email-validator`, to avoid a new dependency for a single-purpose syntax check.
> - `DeliveryConfig.local_dir` is deliberately separate from `--output-dir` — it's for delivering a *copy* to a different destination (e.g., a shared drive) after generation, not a replacement for where the report is generated.

#### Implementation Notes

**Files added:**
- `src/reportmaker/features/delivery/models.py` — `DeliveryChannel` enum (`none`/`local`/`email`), `EmailDeliveryConfig`, `DeliveryConfig` (model-validated: `email` required when channel is `email`, `local_dir` required when channel is `local`), `DeliveryResult`.
- `src/reportmaker/features/delivery/exceptions.py` — `DeliveryError`, `EmailDeliveryError`.
- `src/reportmaker/features/delivery/services.py` — `DeliveryHandler` ABC, `LocalDeliveryHandler` (copies via `shutil.copy2` into `local_dir`), `EmailDeliveryHandler` (builds an `email.message.EmailMessage` with the report as an attachment, sends via stdlib `smtplib.SMTP`; SMTP host/port/user/password/TLS read from env vars via `shared/config.get_env`), `create_delivery_handler()` factory, `deliver_report()` entry point.
- `tests/unit/features/delivery/test_models.py`, `test_services.py` — filled in the previously-empty stubs.

**Files modified:**
- `src/reportmaker/main.py` — added `_maybe_deliver()` (reads the `delivery:` section from the report YAML, validates it, calls `deliver_report()`) and `_deliver_from_schedule()`; wired into `run` after a successful generation and into `schedule start` via `SchedulerService`'s new callback hook.
- `src/reportmaker/features/scheduling/services.py` — `SchedulerService.__init__` accepts an optional `on_report_generated: Callable[[ScheduleConfig, ReportResult], None]`, invoked from `_job_function()` after a successful run.

**No new dependencies** — `smtplib` and `email.message` are stdlib; SMTP credentials come from environment variables (`SMTP_HOST`, `SMTP_PORT`, `SMTP_USER`, `SMTP_PASSWORD`, `SMTP_FROM`, `SMTP_USE_TLS`), never committed to a config file.

#### References

- [Python `smtplib` documentation](https://docs.python.org/3/library/smtplib.html)
- [Python `email.message.EmailMessage`](https://docs.python.org/3/library/email.message.html)
- Related decision: Configuration Validation (above)

---

#### Review / Update Log

| Date | Update | Author |
|------|--------|--------|
| 2026-09-15 | Initial decision and implementation for both Configuration Validation and Delivery Options | deltaog-117 |


---

### GUI Interface

**Date:** 2026-09-19
**Status:** ✅ Confirmed

---

#### Context / Background

ReportMaker was CLI-only, which keeps less technically inclined users away even though the people who most need reports are often exactly those users. The goal was a front-end that lets someone run a report, see the result, schedule it, and manage templates without touching a terminal, while keeping the CLI fully functional and the feature-first architecture intact (deleting the new folder must leave everything else working).

---

#### Options Considered

**Option A: Native desktop app (PySide6 / Qt)**

| Aspect | Assessment |
|--------|------------|
| **Advantages** | • Feels like a real application (native file pickers, tray notifications) <br> • Works offline with no browser <br> • Packageable as a single executable |
| **Disadvantages** | • Heavy dependency (~100 MB+) <br> • Fiddly packaging on Windows/macOS <br> • Harder to test <br> • UI cannot be reused for a team-hosted version |
| **Implementation Difficulty** | Hard |

**Option B: Local web UI (FastAPI + Jinja2 + HTMX)**

| Aspect | Assessment |
|--------|------------|
| **Advantages** | • Reuses Jinja2, already a dependency <br> • Full control over layout <br> • Easy to test with `TestClient` <br> • Same code can later be hosted for a team |
| **Disadvantages** | • More code: routes, templates, and HTMX wiring all hand-written <br> • Still needs a running process, so users must launch something |
| **Implementation Difficulty** | Medium |

**Option C: Python-only web framework (NiceGUI)**

| Aspect | Assessment |
|--------|------------|
| **Advantages** | • Fastest to a working MVP <br> • Forms, tables, dialogs, and file upload built in <br> • No HTML/JS to write, and a simulated-browser test fixture ships with it |
| **Disadvantages** | • Less control over layout <br> • Adds a framework dependency and ties the UI code to it <br> • Requires Python 3.10+ (the project declares 3.9+) |
| **Implementation Difficulty** | Easy |

---

#### Decision & Rationale

**Chosen Option:** C — NiceGUI

> The maintainer selected Option C; the recommendation offered alongside it had been Option B. The trade-offs accepted with C are the layout control given up and the framework coupling.
>
> The coupling is contained rather than spread: everything that decides anything (parameter coercion, cron building, running and delivering, listing outputs, template import/export) lives in NiceGUI-free modules (`parameters.py`, `services.py`) that are unit- and property-tested directly. Only `pages.py` imports NiceGUI, so swapping the front-end later means rewriting one file. The new `gui` feature is a leaf: nothing imports it, and `main.py` imports it lazily inside the `gui` command, so deleting `features/gui/` (or not installing the extra) leaves every other command working.
>
> **Design choices made along the way:**
> - **Forms are generated from the YAML `parameters:` block** (name, type, required, default, description), so a new report needs no GUI code.
> - **Plain-language schedules** (daily / weekly / monthly / every N minutes) are translated to cron in `build_cron()`; raw cron remains available under "Advanced". Weekdays are emitted as names (`mon`…`sun`) because APScheduler numbers days from Monday while classic cron starts on Sunday. Day-of-month is capped at 28 so a monthly schedule fires every month.
> - **Localhost only by default.** The app can run arbitrary report SQL, so `--host` defaults to `127.0.0.1` and a warning is logged if it is changed.
> - **Browser input is never trusted as a path.** Row actions look the clicked name up in the list the server itself produced, uploads are written to a fixed temp filename, and the static route for previews is served by Starlette's `StaticFiles` (a `../` traversal attempt returns 404).
> - **Reports run on a worker thread** (`run.io_bound`) so the page stays responsive, and the launcher forces matplotlib's `Agg` backend, because `report_generation/services.py` imports `pyplot` without pinning a backend and a desktop GUI backend would try to open a window from the wrong thread.
> - **`deliver_if_configured()` was added to `delivery`** rather than copying `main._maybe_deliver()` into the GUI. `main.py`'s own helper is unchanged and can adopt it in a later cleanup.
>
> **Trade-offs accepted:**
> - Schedules created in the GUI only fire while `reportmaker schedule start` is running. `SchedulerService` uses a `BlockingScheduler`; hosting it inside the GUI process needs a `BackgroundScheduler` change, deliberately left out of this iteration. The Schedules tab says so.
> - "Past reports" is a listing of the output directory, not a run-history database. That belongs to the roadmap's "Versioned Report Runs".
> - There is no visual report editor; the Excel template is the authoring tool.

#### Implementation Notes

**Files added:**
- `src/reportmaker/features/gui/` — `models.py` (`GuiSettings`, `OutputFile`, `RunOutcome`, `ScheduleRequest`, `Frequency`, `Weekday`), `exceptions.py` (`GuiError`, `ParameterInputError`, which carries every field problem at once), `parameters.py` (form input → typed parameters), `services.py` (run + deliver, list outputs, build cron, create schedule, template import/export bytes), `pages.py` (the only NiceGUI-dependent module).
- Tests: `tests/unit/features/gui/` (property tests with Hypothesis for parameter coercion, cron generation against APScheduler's real next-fire-time, time parsing), `tests/unit/features/delivery/test_deliver_if_configured.py`, `tests/unit/shared/test_config.py`, `tests/unit/test_main_gui.py`, `tests/integration/features/test_gui.py` (drives the real pages with NiceGUI's simulated browser), `tests/conftest.py`.

**Files modified:**
- `src/reportmaker/main.py` — new `gui` command (`--host`, `--port`, `--templates-dir`, `--output-dir`, `--schedules-file`, `--no-browser`) with a friendly message if the extra is missing.
- `src/reportmaker/features/delivery/services.py` — added `deliver_if_configured()`.
- `src/reportmaker/shared/config.py` — enum normalisation in `save_yaml_config` (see Problems Found).
- `pyproject.toml` — `gui` extra (`nicegui>=3.0,<4; python_version >= "3.10"`), `pytest-asyncio` in `dev`, `asyncio_mode = "auto"` and `main_file = ""` for pytest.

**Problems found while building it:**
- **Template import produced unusable YAML** (pre-existing, reproduced on the unmodified commit): `model_dump()` keeps enums as enum objects and `yaml.dump` wrote them as `!!python/object/apply:` tags, which `yaml.safe_load` rejects, so any template imported from Excel failed validation and could not be run. This broke the GUI's main flow, so it was fixed in `_normalize_for_yaml`. Templates imported before the fix must be re-imported.
- **Excel reports are saved with an `.excel` extension** (pre-existing: the pipeline names files after the format value). The GUI recognises the extension, but the file will not open by double-click. Not changed here.
- **Python version mismatch:** NiceGUI 3.x needs Python 3.10+, `pyproject.toml` declares `>=3.9`, and `shared/config.py` already uses `str | Path` at definition time, which only works on 3.10+. The extra carries an environment marker.
- **Four unit tests fail on the unmodified commit** (`test_pandas_transformer_invalid_aggregation`, `test_sqlalchemy_extractor_success`, `test_process_parameters_defaults`, `test_process_parameters_override`); they are unrelated to this change and were left alone.

**Deployment note (rollback):** the GUI is opt-in twice over — it is only installed with the `gui` extra and only started by `reportmaker gui`. Rolling back means not running that command (or uninstalling the extra); nothing else depends on it.

#### References

- [NiceGUI documentation](https://nicegui.io/documentation)
- [NiceGUI testing (User fixture)](https://nicegui.io/documentation/user)
- Related decisions: Template Management (Decision 7), Delivery Options (above)

---

#### Review / Update Log

| Date | Update | Author |
|------|--------|--------|
| 2026-09-19 | Initial decision and implementation | deltaog-117 |

---

### Embedded Scheduler in the GUI

**Date:** 2026-09-27
**Status:** ✅ Confirmed

---

#### Context / Background

The GUI Interface decision (above) shipped with two documented gaps: schedules created in the GUI only fired while `reportmaker schedule start` ran as a separate process, and — not documented at the time, but true of the same code — even that daemon wouldn't have learned about a schedule added through the GUI while it was already running, because `create_schedule()` built a throwaway `SchedulerService` per call. Closing the ROADMAP's "GUI Interface – follow-ups" item meant running the scheduler inside the GUI process itself, plus adding enable/disable and a run-history view to the Schedules tab, so schedules actually fire without any second command.

---

#### Options Considered

**Option A: `BackgroundScheduler` singleton, started/stopped on the GUI's lifecycle hooks**

| Aspect | Assessment |
|--------|------------|
| **Advantages** | Near drop-in swap in `SchedulerService` (same `.start()`/`.add_job()`/`.shutdown()` API as `BlockingScheduler`); fully decoupled from NiceGUI's asyncio loop; easy to unit-test in isolation |
| **Disadvantages** | One extra dedicated thread just for the scheduler's own wakeup timer |
| **Implementation Difficulty** | Small |

**Option B: `AsyncIOScheduler` tied to NiceGUI's own event loop**

| Aspect | Assessment |
|--------|------------|
| **Advantages** | One fewer thread; "native" fit since NiceGUI runs on FastAPI/uvicorn's asyncio loop |
| **Disadvantages** | Diverges from the CLI daemon's `BlockingScheduler` code path; trickier lifecycle/loop-ownership; harder to unit-test outside a running loop |
| **Implementation Difficulty** | Medium |

**Option C: Keep `BlockingScheduler`, spawn it manually in a daemon `threading.Thread`**

| Aspect | Assessment |
|--------|------------|
| **Advantages** | No change to the scheduler class itself |
| **Disadvantages** | Re-implements by hand what APScheduler already ships as `BackgroundScheduler` |
| **Implementation Difficulty** | Small |

---

#### Decision & Rationale

**Chosen Option:** A — `BackgroundScheduler` singleton

> APScheduler ships `BackgroundScheduler` specifically for "run inside a host app, don't block, don't own the app's own loop" — exactly this case. Both A and B dispatch actual job execution to a worker-thread executor regardless of scheduler type, so B's "one fewer thread" saving buys nothing here, only more coupling to NiceGUI's lifecycle.
>
> **Design choices made along the way:**
> - **`SchedulerService` gained `start_background()` and `stop()`** alongside the existing `start(foreground=True)`, sharing a new `_populate_jobs()` helper. The CLI daemon (`reportmaker schedule start`) is untouched — it still uses `start()`/`BlockingScheduler`.
> - **`register_pages()` now owns one `SchedulerService` for the whole GUI process**, started via `start_background()` and stopped via `app.on_shutdown`. It's threaded through to every `_Dashboard` instance (one per browser tab) instead of each tab constructing its own. This is what actually closes the gap above: `create_schedule()` was changed to take that live `SchedulerService` instead of a `schedules_file` path, so a schedule added from the GUI is registered on the *same* running scheduler immediately, not just written to disk for a future restart to pick up.
> - **Run history lives in a new bounded YAML file (`run_history.yaml`)**, next to `schedules.yaml`, via a new `RunHistoryStore` (capped at 200 records, newest first). It's deliberately not stored through `shared/db.py`'s SQLAlchemy engine: that engine's `DATABASE_URL` is reserved for whatever external database a *report's own query* targets, so writing our own bookkeeping through it would mix user-owned data with app state and risk touching a read-only or production DB the user pointed a report at.
> - **Enable/disable reaches the live scheduler too**: `SchedulerService.set_enabled()` adds or removes the APScheduler job immediately when the scheduler is running, not just on the next restart. The Schedules tab's per-row toggle calls it directly.
> - **Scheduled runs deliver, same as the CLI daemon.** `gui.services.deliver_after_schedule_run()` is wired as `SchedulerService`'s `on_report_generated` hook, mirroring what `main.py` already does for `schedule start`, so a `delivery:` section in a report's YAML is honoured regardless of which process is running the scheduler.
>
> **Trade-offs accepted:**
> - Run history is one flat, capped file — a log for a human to skim in a dialog, not a queryable audit trail. A future "Versioned Report Runs" feature (see ROADMAP's long-term vision) would need a real store if that ever matters at scale.
> - A history-write failure is caught and logged rather than raised, so a bug in the history path can never take down a scheduled report; this is a deliberate, narrow exception-swallowing spot, not a general pattern.

#### Implementation Notes

**Files added:**
- `src/reportmaker/features/scheduling/repositories.py` — `RunHistoryStore` (bounded, file-backed run log; was an empty stub before this).
- `tests/unit/features/scheduling/test_repositories.py`, `test_services.py`, `test_models.py` — filled in the previously-empty stubs.

**Files modified:**
- `src/reportmaker/features/scheduling/models.py` — added `RunRecord`.
- `src/reportmaker/features/scheduling/services.py` — added `start_background()`, `stop()`, `set_enabled()`, `list_run_history()`, `_populate_jobs()`, `_record_run()`; `_job_function()` now times each run and appends a `RunRecord` on every outcome (success, failure, or exception); removed dead code in the old `start()` (a `foreground` ternary that always built the same `BlockingScheduler`, and an unreachable `self.scheduler._thread.join()` — `BlockingScheduler.start()` already blocks the calling thread, so that line could never run).
- `src/reportmaker/features/gui/services.py` — `create_schedule()` now takes a `SchedulerService` instead of a `schedules_file` path; added `deliver_after_schedule_run()`.
- `src/reportmaker/features/gui/pages.py` — `register_pages()` builds and starts the shared scheduler; `_Dashboard` takes it as a constructor argument; Schedules tab gained an "Enabled" toggle column and a "View run history" action/dialog; the old "start it from a terminal" banner was replaced.

**Problems found while building it:**
- **Four unit tests were failing on the unmodified commit** (`test_pandas_transformer_invalid_aggregation`, `test_sqlalchemy_extractor_success`, `test_process_parameters_defaults`, `test_process_parameters_override`) — flagged as pre-existing and left alone in the GUI Interface decision (above). They blocked adopting `scripts/check` (see below), so they were fixed here: two had assertions that contradicted their own sibling tests or the implementation's documented contract (a `.date()` vs `datetime` mismatch, and a call that expected both success and failure from identical arguments), and two referenced a `get_engine` name `report_generation/services.py` never had (it calls `create_engine` directly) and a stale `.extract()` call missing its `parameters` argument. No production code changed for these.
- **`scripts/check` did not exist yet.** Created it as `pytest -q` only; `ruff check`'s configured ruleset (`E,F,W,I,N,D,S`) currently flags roughly 600 pre-existing findings across the codebase (mostly `D103`/`S101` on ordinary pytest asserts and undocumented test functions), and `mypy`'s `python_version = "3.9"` is no longer supported by the installed `mypy`, on top of missing `yaml`/`apscheduler` stubs. Both are left for a dedicated cleanup pass rather than folded into this feature.

**Deployment note (rollback):** the embedded scheduler is inseparable from `reportmaker gui` itself — it starts and stops with that command's process. The CLI daemon (`reportmaker schedule start`) is unchanged and still works as its own, separate way to run schedules without the GUI at all.

#### References

- [APScheduler: choosing the right scheduler](https://apscheduler.readthedocs.io/en/3.x/userguide.html#choosing-the-right-scheduler-job-store-s-executor-s-and-trigger-s)
- Related decisions: Scheduling Implementation (Decision 5), GUI Interface (above)

---

#### Review / Update Log

| Date | Update | Author |
|------|--------|--------|
| 2026-09-27 | Initial decision and implementation | deltaog-117 |

### Visual Template Editor

**Date:** 2026-10-20
**Status:** ✅ Confirmed

---

#### Context / Background

After the GUI shipped, the only way to define a report was to download the Excel template, fill it in, and upload it. The ROADMAP's remaining "GUI Interface – follow-ups" item was to create and edit report definitions visually. The editor had to cover every `ReportConfig` section, work for both creating and editing, and let a non-coder check their SQL before saving.

---

#### Options Considered

**Option A: One form dialog with a collapsible section per config area**

| Aspect | Assessment |
|--------|------------|
| **Advantages** | Matches the existing dialogs and Schedules form; works for create and edit alike; all sections visible and editable at once |
| **Disadvantages** | Many fields; aggregations and parameters need dynamic row lists |
| **Implementation Difficulty** | Medium |

**Option B: Step-by-step wizard (`ui.stepper`)**

| Aspect | Assessment |
|--------|------------|
| **Advantages** | Friendliest for first-time users; per-step validation |
| **Disadvantages** | Most UI code; awkward for editing an existing template |
| **Implementation Difficulty** | High |

**Option C: Raw YAML editor with live validation**

| Aspect | Assessment |
|--------|------------|
| **Advantages** | Smallest change; full flexibility |
| **Disadvantages** | Not visual, and not friendly to the non-technical users the GUI exists for |
| **Implementation Difficulty** | Small |

---

#### Decision & Rationale

**Chosen Option:** A — form dialog, plus a "Test query" button

> The form gives create and edit one code path and reuses the same validation the Excel importer relies on (`ReportConfig` plus the semantic pre-flight checks), so the three ways of defining a report cannot drift apart.
>
> **Design choices made along the way:**
> - **A string-typed `TemplateDraft` model holds the form state.** Every widget binds straight to a field; `build_report_config()` is the single place text becomes typed values and where all problems are collected and reported at once. An empty `chart_kind` means "no chart". All of this lives in `gui/services.py` with no NiceGUI import, so it is unit- and property-tested without a browser.
> - **`TemplateManager.save_config()` is the new storage entry point.** It takes an optional pinned `name`, so renaming the report inside the form while editing does not orphan the file or create a duplicate.
> - **Editing preserves what the form cannot show.** `data_source.parameters` and `schedule` are carried over from the config being edited (`base`), and unknown top-level YAML keys, notably `delivery:`, are re-read from the file being replaced. Without this, one edit would silently turn off a report's delivery.
> - **"Test query" never writes.** It executes the SQL on a connection that is closed without committing, so even a mistyped `DELETE` is rolled back, and it reads only the first 20 rows. Parameters take their default values; a required one with no default is reported rather than guessed.
>
> **Trade-offs accepted:**
> - The query preview has no timeout, so a slow query holds a worker thread until it finishes; reports have the same property today.
> - A report that is open in the Run tab keeps showing its old parameter form after being edited, until another report is chosen and the first is re-selected.
> - The pivot's index, columns and values are plain text fields; they are not validated against the query's real columns.

#### Implementation Notes

**Files modified:**
- `src/reportmaker/features/template_management/services.py` — `TemplateManager.save_config()`.
- `src/reportmaker/features/gui/models.py` — `TemplateDraft`, `AggregationRow`, `ParameterRow`, `QueryPreview`.
- `src/reportmaker/features/gui/services.py` — `build_report_config()`, `draft_from_config()`, `load_template_draft()`, `save_template_draft()`, `preview_query()`.
- `src/reportmaker/features/gui/pages.py` — "New template" button, per-row "Edit" action, editor dialog and query-preview table.

**Tests added:** `tests/unit/features/gui/test_template_editor.py` (including a property test that draft → config → draft → config is stable and one that a preview never exceeds its row limit), `TestSaveConfig` in the previously empty `tests/unit/features/template_management/test_services.py`, and five simulated-browser tests in `tests/integration/features/test_gui.py`.

**Problems found while building it:**
- `save_config(name="")` first fell back to the report's name because of an `or` instead of an `is None` check; caught by its own test.
- Table cell text is rendered client-side, so NiceGUI's `should_see` cannot find it; the integration tests poll the table's rows instead.

**Deployment note (rollback):** the editor is purely additive UI plus one new storage method; nothing existing changed behaviour. To roll back, remove the "New template" button and the "edit" action. Stored templates stay valid, as they are ordinary YAML.

#### References

- Related decisions: GUI Interface, Template Management (Excel ↔ YAML)

---

#### Review / Update Log

| Date | Update | Author |
|------|--------|--------|
| 2026-10-20 | Initial decision and implementation | deltaog-117 |

---
