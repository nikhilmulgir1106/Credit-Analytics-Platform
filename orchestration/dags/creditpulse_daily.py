"""CreditPulse daily DAG (PRODUCTION TARGET: Airflow).

NOT run in local mode — the local equivalent is orchestration/run_pipeline.py,
which chains the same steps as a plain Python process. This file documents how
the pipeline maps onto Airflow for the production deployment: richer dependency
graph, retries with backoff on transient steps, and a quality gate that halts
serving (gold left untouched) on a blocking data-quality failure.
"""

from __future__ import annotations

from datetime import datetime, timedelta

from airflow import DAG
from airflow.operators.bash import BashOperator

default_args = {
    "owner": "creditpulse",
    "retries": 2,
    "retry_delay": timedelta(minutes=2),
    "retry_exponential_backoff": True,
}

with DAG(
    dag_id="creditpulse_daily",
    schedule="0 2 * * *",            # 02:00 daily
    start_date=datetime(2026, 1, 1),
    catchup=False,
    default_args=default_args,
    tags=["creditpulse", "elt"],
) as dag:

    extract = BashOperator(task_id="extract", bash_command="python ingestion/extract_uci.py")
    generate = BashOperator(task_id="generate_txns", bash_command="python ingestion/generate_transactions.py")
    load = BashOperator(task_id="load_raw", bash_command="python ingestion/load_to_duckdb.py")
    dbt_build = BashOperator(task_id="dbt_build", bash_command="cd dbt && dbt build")
    freshness = BashOperator(task_id="source_freshness", bash_command="cd dbt && dbt source freshness")

    # Quality gate: a non-zero exit halts the DAG before serving. No retries —
    # a failed gate is a data issue, not a transient error.
    quality_gate = BashOperator(
        task_id="quality_gate",
        bash_command="python quality/run_quality_checks.py",
        retries=0,
    )

    train = BashOperator(task_id="ml_train", bash_command="python ml/train.py")
    evaluate = BashOperator(task_id="ml_evaluate", bash_command="python ml/evaluate.py")

    extract >> generate >> load >> dbt_build >> freshness >> quality_gate >> train >> evaluate
