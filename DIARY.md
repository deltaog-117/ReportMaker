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
