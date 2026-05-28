"""CreditPulse — Streamlit dashboard on the gold marts and operational tables.

Reads DuckDB read-only. All heavy work (180k-row payment history, 30k borrowers)
is aggregated in SQL so only small result sets reach pandas — memory-safe on the
8 GB target machine. Run:  streamlit run bi/streamlit_app.py
"""

from __future__ import annotations

from pathlib import Path

import duckdb
import pandas as pd
import streamlit as st

REPO_ROOT = Path(__file__).resolve().parent.parent
DUCKDB_PATH = REPO_ROOT / "warehouse" / "creditpulse.duckdb"

st.set_page_config(page_title="CreditPulse", page_icon="📊", layout="wide")


@st.cache_resource
def get_con() -> duckdb.DuckDBPyConnection:
    return duckdb.connect(str(DUCKDB_PATH), read_only=True)


@st.cache_data(ttl=300)
def q(sql: str) -> pd.DataFrame:
    return get_con().execute(sql).df()


@st.cache_data(ttl=300)
def table_exists(qualified: str) -> bool:
    schema, _, name = qualified.partition(".")
    df = get_con().execute(
        "select 1 from information_schema.tables where table_schema = ? and table_name = ?",
        [schema, name],
    ).df()
    return not df.empty


# ---------------------------------------------------------------- Portfolio ---
def render_portfolio() -> None:
    st.subheader("Portfolio overview")
    kpis = q(
        """
        select
            count(*)              as borrowers,
            sum(credit_limit)     as total_exposure,
            avg(credit_limit)     as avg_limit,
            avg(is_default)       as default_rate
        from main_marts.feature_default_prediction
        """
    ).iloc[0]

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Borrowers", f"{int(kpis.borrowers):,}")
    c2.metric("Total credit exposure", f"NT${kpis.total_exposure/1e6:,.1f}M")
    c3.metric("Avg credit limit", f"NT${kpis.avg_limit:,.0f}")
    c4.metric("Overall default rate", f"{kpis.default_rate:.1%}")

    st.divider()
    left, right = st.columns(2)
    with left:
        st.caption("Borrowers by credit-limit band")
        df = q(
            """
            select credit_limit_band as band, count(*) as borrowers
            from main_marts.dim_borrower
            group by 1
            order by min(credit_limit)
            """
        ).set_index("band")
        st.bar_chart(df, color="#4C78A8")
    with right:
        st.caption("Borrowers by region")
        df = q(
            "select region, count(*) as borrowers from main_marts.dim_borrower group by 1 order by 1"
        ).set_index("region")
        st.bar_chart(df, color="#54A24B")


# ----------------------------------------------------------- Risk & delinq ---
def render_risk() -> None:
    st.subheader("Risk & delinquency")
    dims = q(
        "select distinct segment_dimension from main_marts.mart_portfolio_risk order by 1"
    )["segment_dimension"].tolist()
    dim = st.selectbox("Segment dimension", dims, index=dims.index("credit_limit_band") if "credit_limit_band" in dims else 0)

    seg = q(
        f"""
        select segment_value, n_clients, n_default, default_rate, total_credit_limit_exposure
        from main_marts.mart_portfolio_risk
        where segment_dimension = '{dim}'
        order by default_rate desc
        """
    )
    left, right = st.columns([2, 3])
    with left:
        st.caption(f"Default rate by {dim}")
        st.bar_chart(seg.set_index("segment_value")[["default_rate"]], color="#E45756")
    with right:
        st.caption("Segment detail")
        st.dataframe(seg, width="stretch", hide_index=True)

    st.divider()
    st.caption("Delinquency rate by statement month (m1 = most recent)")
    delinq = q(
        """
        select 'm' || month_index as statement_month,
               avg(cast(is_delinquent as int)) as delinquency_rate,
               avg(utilization)                as avg_utilization
        from main_marts.fct_payment_history
        group by month_index
        order by month_index
        """
    ).set_index("statement_month")
    a, b = st.columns(2)
    a.line_chart(delinq[["delinquency_rate"]], color="#E45756")
    b.line_chart(delinq[["avg_utilization"]], color="#4C78A8")


# ----------------------------------------------------------------- Model -----
def render_model() -> None:
    st.subheader("Default-prediction model")
    if not table_exists("meta.model_scores"):
        st.info("No model scores yet. Run `python ml/train.py && python ml/evaluate.py`.")
        return

    from sklearn.metrics import roc_auc_score, roc_curve  # local import; only this tab needs it

    test = q("select pd_logreg, pd_xgboost, is_default from meta.model_scores where is_test")
    cols = st.columns(2)
    for col, model, score_col in [(cols[0], "Logistic regression", "pd_logreg"),
                                  (cols[1], "XGBoost", "pd_xgboost")]:
        auc = roc_auc_score(test["is_default"], test[score_col])
        fpr, tpr, _ = roc_curve(test["is_default"], test[score_col])
        ks = float((tpr - fpr).max())
        col.metric(model, f"AUC {auc:.3f}", f"KS {ks:.3f}")

    st.divider()
    left, right = st.columns(2)
    with left:
        st.caption("Predicted PD distribution (XGBoost, all borrowers)")
        hist = q(
            """
            select cast(pd_xgboost*10 as int)/10.0 as pd_bucket, count(*) as borrowers
            from meta.model_scores group by 1 order by 1
            """
        ).set_index("pd_bucket")
        st.bar_chart(hist, color="#B279A2")
    with right:
        st.caption("Predicted PD vs actual default rate by credit-limit band")
        cal = q(
            """
            select b.credit_limit_band as band,
                   avg(s.pd_xgboost)   as predicted_pd,
                   avg(s.is_default)   as actual_rate
            from meta.model_scores s
            join main_marts.dim_borrower b using (client_id)
            group by 1 order by predicted_pd desc
            """
        ).set_index("band")
        st.bar_chart(cal, color=["#B279A2", "#E45756"])

    st.caption("Highest-risk borrowers (XGBoost PD)")
    st.dataframe(
        q(
            """
            select s.client_id, round(s.pd_xgboost, 4) as pd, s.is_default,
                   b.credit_limit_band, b.age_band, b.region
            from meta.model_scores s
            join main_marts.dim_borrower b using (client_id)
            order by s.pd_xgboost desc limit 15
            """
        ),
        width="stretch", hide_index=True,
    )


# ------------------------------------------------------------ Data quality ---
def render_quality() -> None:
    st.subheader("Data quality")
    if not table_exists("meta.mart_data_quality"):
        st.info("No DQ results yet. Run `python quality/run_quality_checks.py`.")
        return

    latest = q("select * from meta.mart_data_quality where is_latest order by target_table, severity")
    run_id = latest["run_id"].iloc[0] if not latest.empty else "—"
    total = int(latest["checks"].sum())
    passed = int(latest["passed"].sum())
    c1, c2, c3 = st.columns(3)
    c1.metric("Latest run", run_id)
    c2.metric("Checks passed", f"{passed}/{total}")
    c3.metric("Pass rate", f"{(passed/total if total else 0):.0%}")

    st.divider()
    st.caption("Pass rate by table & severity (latest run)")
    st.dataframe(
        latest[["target_table", "severity", "checks", "passed", "failed", "pass_rate"]],
        width="stretch", hide_index=True,
    )
    st.caption("Expectation detail (latest run)")
    st.dataframe(
        q(
            f"""
            select target_table, expectation_type, column_name, severity, success, observed_value
            from meta.dq_results
            where run_id = (select max(run_id) from meta.dq_results)
            order by target_table, severity, expectation_type
            """
        ),
        width="stretch", hide_index=True,
    )


def main() -> None:
    st.title("📊 CreditPulse — Credit Portfolio Analytics")
    st.caption("Local DuckDB build · gold marts, risk model, and data quality")
    if not DUCKDB_PATH.exists():
        st.error(f"Warehouse not found at {DUCKDB_PATH}. Build it with the ingestion scripts + dbt.")
        return

    tabs = st.tabs(["Portfolio", "Risk & delinquency", "Model", "Data quality"])
    with tabs[0]:
        render_portfolio()
    with tabs[1]:
        render_risk()
    with tabs[2]:
        render_model()
    with tabs[3]:
        render_quality()


main()
