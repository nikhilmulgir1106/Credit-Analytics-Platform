# CLAUDE.md — CreditPulse

This file gives you persistent context for this repository. Read it fully before acting, and follow it in every session.

## What this project is

CreditPulse is a personal portfolio project I'm building to deepen my hands-on skills with the modern data stack. It's an end-to-end credit/lending analytics platform: it ingests raw loan data, builds a layered warehouse with dbt, enforces automated data-quality checks, applies governance and PII masking, and serves portfolio-risk insights through a dashboard and a default-prediction model.

The goal is learning by building something production-shaped — clean architecture, real tooling, good engineering habits — not a throwaway notebook.

## Hardware constraints (important — optimize for this)

I'm developing on a MacBook Air M2 with **8 GB RAM** and a 256 GB SSD. This is the binding constraint. Always make memory- and disk-conscious choices:

- Default to DuckDB for everything; it streams larger-than-RAM data well.
- NEVER load the full Lending Club dataset into pandas. Use DuckDB to read it, or work on a sampled subset.
- Keep PySpark usage to a small sample only — it's there to demonstrate the skill, not to do heavy lifting. DuckDB does the real work.
- Prefer dbt incremental models for large tables over full rebuilds.
- Don't suggest running Spark, a heavy IDE, and the full pipeline simultaneously.
- Flag disk usage before downloading large datasets.

## Tech stack (local-first, zero-cost)

- Language: Python 3.11
- Warehouse: **DuckDB** (a local file — this is the default and primary path)
- Transformation: **dbt-core** with `dbt-duckdb`
- Data quality: **Great Expectations** + dbt tests
- ML: scikit-learn (logistic regression baseline) + XGBoost
- Dashboard: **Streamlit** (local) — primary. Tableau Public optional.
- Distributed processing demo: PySpark in local mode (sampled data only)
- Orchestration: a Python runner script first; GitHub Actions scheduled workflow later
- CI: GitHub Actions + sqlfluff
- Version control: Git

Cloud equivalents (Snowflake, S3, Airflow) are documented in ARCHITECTURE.md as the "production target" but are NOT required to build or run this project. Do not introduce cloud dependencies unless I explicitly ask.

## Architecture (medallion / ELT)

Raw files -> DuckDB RAW (bronze, append-only, immutable) -> dbt STAGING (silver: typed, deduped, conformed, PII-tagged) -> dbt MARTS (gold: dims/facts, risk marts, ML feature table). Quality checks gate the pipeline before anything reaches the serving layer. See README.md and ARCHITECTURE.md for full detail.

Three layers, strict separation:
- **bronze / RAW**: verbatim source, no logic, never edited.
- **silver / STAGING**: one model per source, cleaning only, no business logic, no joins.
- **gold / MARTS**: dimensional models + risk marts + the single ML feature table.

## Conventions

- dbt naming: stg_<source>__<entity>, int_<concept>, dim_<entity>, fct_<event>, mart_<subject>.
- Every model has a description and declared grain in its YAML.
- Quality is a **blocking gate**: a failed critical test stops the pipeline; the previous good gold tables stay in place.
- Data: only public or synthetic data. Any PII-shaped columns are synthetic and exist solely to demonstrate masking. Never fabricate or hardcode real personal data.
- Secrets: never commit credentials. Use a gitignored .env. There are no real secrets in local mode.
- Idempotency: every pipeline step must be safe to re-run.
- Commit messages: imperative mood, concise.

## Repository layout (target)

```
ingestion/      extractors, spark sample cleaner, duckdb loader, synthetic feed
dbt/            dbt project: models/{staging,intermediate,marts}, tests, macros, snapshots
quality/        great_expectations suites + checkpoints, dq results publisher
governance/     masking + row-access logic (as DuckDB views in local mode)
ml/             feature build, train, evaluate
bi/             streamlit_app.py
orchestration/  python runner + github actions workflow
docs/           data_dictionary.md, data_contracts.md, adr/
```

## Build phases (work in this order, one phase at a time)

1. **Scaffold + environment**: repo structure, venv, requirements, dbt + duckdb profile, .env.example, .gitignore. Verify `dbt debug` passes against DuckDB.
2. **Ingest + bronze**: load the UCI default set first (small), then Lending Club via DuckDB. Land to RAW with load metadata.
3. **Silver + gold**: staging models with tests, then dims/facts, risk marts, and the ML feature table.
4. **Data quality**: dbt tests + Great Expectations checkpoint; publish results to a DQ mart.
5. **Governance**: masking + row-access demonstrated via DuckDB views/roles.
6. **ML**: baseline + XGBoost default-prediction model; evaluate (AUC, KS, calibration).
7. **Dashboard**: Streamlit app on gold marts (portfolio, risk/delinquency, data-quality views).
8. **Orchestration + CI**: python runner that chains the steps; GitHub Actions for lint + dbt build on PR.

## How to work with me

- Before starting a phase, briefly state the plan and what files you'll create, then proceed.
- Build the smallest working slice first, run it, confirm it works, then expand.
- Run commands and show output rather than assuming success.
- After each phase, update README.md / docs so the code and docs stay in sync.
- If a choice has a meaningful tradeoff (especially memory/disk), tell me and recommend the lighter option.
- Keep dependencies minimal; justify any new library.

## Common commands

```bash
# environment
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# ingestion -> bronze (DuckDB RAW)
python ingestion/extract_uci.py            # download UCI default set
python ingestion/generate_transactions.py  # synthetic Faker feed
python ingestion/load_to_duckdb.py         # land all sources to raw.* (LC if present)

# warehouse build (run dbt from the ./dbt dir)
cd dbt && dbt debug && dbt build
dbt source freshness                  # freshness SLAs
dbt docs generate && dbt docs serve   # lineage

# quality gate (Great Expectations 1.x is Python-API only — the old
# `great_expectations checkpoint run ...` CLI was removed in GE 1.0)
python quality/run_quality_checks.py        # gate: exits non-zero on blocking failure
python quality/run_quality_checks.py --no-gate

# governance (local mode = role-scoped views in the dbt `governance` schema)
cd dbt && dbt build --select governance
dbt build --select gov_dim_borrower_regional --vars '{access_region: north}'

# ml + dashboard
python ml/train.py && python ml/evaluate.py
streamlit run bi/streamlit_app.py

# full pipeline
python orchestration/run_pipeline.py
```

Note: the venv runs **Python 3.12** (3.11 from the stack table wasn't installed
locally; 3.12 is fully supported by every dependency).
