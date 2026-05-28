"""Run the Great Expectations gold-layer checkpoint and gate the pipeline.

Reads each target gold table from DuckDB into pandas (gold tables are small —
tens of thousands of rows — so this is memory-safe), validates it against its
suite, publishes results to the META schema, and exits non-zero if any BLOCKING
expectation fails. Warning failures are reported but do not gate.

Usage:
    python quality/run_quality_checks.py            # gate on blocking failures
    python quality/run_quality_checks.py --no-gate  # report only, never exit 1
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import warnings
from datetime import datetime, timezone
from pathlib import Path

# Silence GE's tqdm metric progress bars and noisy deprecation warnings.
os.environ.setdefault("TQDM_DISABLE", "1")
warnings.filterwarnings("ignore")

import duckdb  # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parent / "great_expectations"))
import suites as suite_defs  # noqa: E402

from publish_dq_results import DUCKDB_PATH, publish  # noqa: E402

import great_expectations as gx  # noqa: E402


def _flatten(result, *, run_id, run_at, suite_name, target_table) -> dict:
    cfg = result.expectation_config
    observed = result.result.get("observed_value")
    unexpected = result.result.get("unexpected_count")
    return {
        "run_id": run_id,
        "run_at": run_at,
        "suite_name": suite_name,
        "target_table": target_table,
        "expectation_type": cfg.type,
        "column_name": cfg.kwargs.get("column"),
        "severity": cfg.meta.get("severity", "blocking") if cfg.meta else "blocking",
        "success": bool(result.success),
        "observed_value": json.dumps(observed) if observed is not None else None,
        "unexpected_count": int(unexpected) if unexpected is not None else None,
    }


def run(gate: bool = True) -> int:
    run_at = datetime.now(timezone.utc)
    run_id = run_at.strftime("%Y%m%dT%H%M%SZ")

    con = duckdb.connect(str(DUCKDB_PATH), read_only=True)
    ctx = gx.get_context(mode="ephemeral")
    records: list[dict] = []

    for spec in suite_defs.get_suites():
        name, table = spec["name"], spec["table"]
        df = con.execute(f"select * from {table}").df()

        batch = (
            ctx.data_sources.add_pandas(f"src_{name}")
            .add_dataframe_asset(f"asset_{name}")
            .add_batch_definition_whole_dataframe(f"batch_{name}")
        )
        suite = ctx.suites.add(gx.ExpectationSuite(name=f"suite_{name}"))
        for exp in spec["expectations"]:
            suite.add_expectation(exp)
        vd = ctx.validation_definitions.add(
            gx.ValidationDefinition(name=f"vd_{name}", data=batch, suite=suite)
        )
        result = vd.run(batch_parameters={"dataframe": df}, result_format="SUMMARY")
        for r in result.results:
            records.append(
                _flatten(r, run_id=run_id, run_at=run_at, suite_name=name, target_table=table)
            )

    con.close()
    publish(records)

    # Report.
    blocking_failures = [r for r in records if not r["success"] and r["severity"] == "blocking"]
    warning_failures = [r for r in records if not r["success"] and r["severity"] == "warning"]
    passed = sum(1 for r in records if r["success"])

    print(f"\n[dq] run {run_id}: {passed}/{len(records)} expectations passed")
    for r in records:
        if not r["success"]:
            tag = r["severity"].upper()
            print(f"  [{tag}] {r['target_table']} :: {r['expectation_type']}"
                  f" ({r['column_name']}) observed={r['observed_value']}")
    print(f"[dq] results published to meta.dq_results / meta.mart_data_quality")

    if warning_failures:
        print(f"[dq] {len(warning_failures)} warning check(s) failed (non-blocking)")

    if blocking_failures:
        print(f"[dq] GATE FAILED: {len(blocking_failures)} blocking check(s) failed "
              f"— downstream consumers keep last-good gold.")
        if gate:
            return 1
    else:
        print("[dq] GATE PASSED: all blocking checks green.")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description="Run GE gold-layer quality gate.")
    ap.add_argument("--no-gate", action="store_true", help="report only; do not exit non-zero")
    args = ap.parse_args()
    return run(gate=not args.no_gate)


if __name__ == "__main__":
    sys.exit(main())
