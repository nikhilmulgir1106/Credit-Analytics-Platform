"""Publish data-quality results to the DuckDB META schema.

Writes one row per expectation to meta.dq_results (append-only, run-stamped) and
maintains meta.mart_data_quality, a per-run/table/severity summary view that the
Streamlit DQ dashboard reads. Idempotent per run_id.
"""

from __future__ import annotations

from pathlib import Path

import duckdb
import pandas as pd

REPO_ROOT = Path(__file__).resolve().parent.parent
DUCKDB_PATH = REPO_ROOT / "warehouse" / "creditpulse.duckdb"
META_SCHEMA = "meta"

_DDL = f"""
CREATE SCHEMA IF NOT EXISTS {META_SCHEMA};
CREATE TABLE IF NOT EXISTS {META_SCHEMA}.dq_results (
    run_id           VARCHAR,
    run_at           TIMESTAMP,
    suite_name       VARCHAR,
    target_table     VARCHAR,
    expectation_type VARCHAR,
    column_name      VARCHAR,
    severity         VARCHAR,
    success          BOOLEAN,
    observed_value   VARCHAR,
    unexpected_count BIGINT
);
"""

_SUMMARY_VIEW = f"""
CREATE OR REPLACE VIEW {META_SCHEMA}.mart_data_quality AS
WITH agg AS (
    SELECT
        run_id,
        run_at,
        target_table,
        severity,
        count(*)                                          AS checks,
        sum(CASE WHEN success THEN 1 ELSE 0 END)          AS passed,
        sum(CASE WHEN NOT success THEN 1 ELSE 0 END)      AS failed,
        round(avg(CASE WHEN success THEN 1.0 ELSE 0.0 END), 4) AS pass_rate
    FROM {META_SCHEMA}.dq_results
    GROUP BY 1, 2, 3, 4
)
SELECT
    *,
    run_id = (SELECT max(run_id) FROM {META_SCHEMA}.dq_results) AS is_latest
FROM agg
ORDER BY run_at DESC, target_table, severity;
"""


def publish(records: list[dict], duckdb_path: Path = DUCKDB_PATH) -> None:
    """Persist a run's expectation results and refresh the summary view."""
    if not records:
        return
    df = pd.DataFrame.from_records(records)
    run_id = df["run_id"].iloc[0]

    con = duckdb.connect(str(duckdb_path))
    try:
        con.execute(_DDL)
        con.execute(f"DELETE FROM {META_SCHEMA}.dq_results WHERE run_id = ?", [run_id])
        con.register("dq_df", df)
        con.execute(
            f"""INSERT INTO {META_SCHEMA}.dq_results
                SELECT run_id, run_at, suite_name, target_table, expectation_type,
                       column_name, severity, success, observed_value, unexpected_count
                FROM dq_df"""
        )
        con.unregister("dq_df")
        con.execute(_SUMMARY_VIEW)
    finally:
        con.close()
