# ADR-006 — Great Expectations 1.x: code-defined suites (no CLI)

**Status:** accepted

**Context.** The installed Great Expectations is 1.17. GE **1.0 removed the
`great_expectations` CLI** and the YAML-checkpoint workflow that older docs
(including this project's early README/CLAUDE.md) reference. No SQLAlchemy or
`duckdb-engine` is installed.

**Decision.** Define expectation suites in code ([`quality/great_expectations/suites.py`](../../quality/great_expectations/suites.py))
and run them with a Python runner ([`quality/run_quality_checks.py`](../../quality/run_quality_checks.py))
using an **ephemeral** GE context and a **pandas datasource** — the gold tables
are small (≤30k rows), so reading them from DuckDB into pandas is memory-safe and
avoids adding a SQL adapter dependency.

**Consequences.** No on-disk GE project scaffolding to maintain or commit.
Severity (`blocking`/`warning`) is carried in each expectation's `meta`; the
runner exits non-zero on any blocking failure (the gate). Results are published
to `meta.dq_results` ourselves rather than via a GE store.
