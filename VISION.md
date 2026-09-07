# Vision for ReportMaker

---

## The Problem

Every day, teams waste hours manually pulling data from databases, pasting it into spreadsheets, formatting tables, and creating charts. This process is repetitive, error‑prone, and scales poorly. When a stakeholder asks for a “quick update,” the analyst must re‑run queries, adjust formulas, and reformat—again. The frustration isn’t just lost time; it’s the lost opportunity to act on insights while they’re still fresh.

---

## The Solution

ReportMaker is a **dynamic report generator** that turns raw SQL data into polished, professional reports automatically. You define the query once, choose a template, and the system runs on‑demand or on a schedule—outputting PDFs (and soon HTML, Excel) that are ready to share. It’s built for **extensibility**: non‑coders can add new metrics or data sources through simple configuration files, without touching Python. ReportMaker doesn’t replace spreadsheets or BI dashboards—it bridges the gap between raw data and actionable insight, delivering the right format at the right time.

---

## Guiding Principles

1. **Automation First** – If a report can be run more than once, it should be automated. The system handles repetition so humans can focus on interpretation.

2. **Empower Non‑Coders** – Adding a new metric or data source should be as easy as editing a YAML file. Business users should never need to write Python or SQL to tweak a report.

3. **Correctness & Observability** – Every report run is logged, with input parameters and output hashes. If a number looks wrong, we can trace exactly which query and transformation produced it.

4. **Modular & Deletable** – Each feature (generation, scheduling, delivery) is independent. You can replace the PDF engine or switch email providers without touching core logic.

5. **Performance with Meaning** – We benchmark the critical path (query + render) and never sacrifice clarity for speed unless measurements prove the bottleneck.

---

## Who This Is For

- **Business Analysts** who need daily or weekly sales, marketing, or operational reports.
- **Data Teams** who want to offload recurring reporting requests and focus on deeper analysis.
- **Managers** who want to receive polished PDFs in their inbox every morning, without chasing for numbers.
- **Small to Medium Companies** that can’t afford a full‑time BI developer but still need reliable, professional reports.

---

## What This Is NOT

- **Not a BI dashboard** – We don’t offer real‑time interactive visualisations; we produce static, scheduled reports.
- **Not a data warehouse** – We don’t store or process large volumes of raw data; we query existing databases and generate outputs.
- **Not a replacement for Excel** – For ad‑hoc analysis or complex manual modelling, Excel is still the right tool. ReportMaker is for *recurring* tasks.
- **Not a general‑purpose ETL tool** – We don’t perform heavy transformations or data cleaning; we assume the data is already structured in the database.
- **Not a code‑generator for arbitrary Python** – We keep the logic declarative (queries + templates) and avoid exposing the entire Python ecosystem to non‑coders.

---

## Why This Matters

In a world drowning in data, the ability to consistently and reliably turn that data into information is a competitive advantage. ReportMaker frees analysts from the drudgery of copy‑paste‑format, letting them spend time on what really matters: asking better questions, interpreting trends, and driving decisions. It’s a small tool with a big purpose: making data‑driven culture practical, not just aspirational.
