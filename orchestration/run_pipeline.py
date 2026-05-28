"""CreditPulse pipeline runner — chains the full local ELT + quality + ML flow.

    extract_uci -> generate_transactions -> load_to_duckdb
        -> dbt build (models + tests) -> dbt source freshness
        -> quality gate (Great Expectations) -> ml train -> ml evaluate

Each step is idempotent and safe to re-run. Transient steps (network/IO) retry
with backoff. A failed step aborts the run — in particular a failed quality gate
halts before ML/serving, so consumers keep the last-good gold. This mirrors the
production Airflow DAG (orchestration/dags/) and the scheduled GitHub Actions
workflow.

Usage:
    python orchestration/run_pipeline.py                 # full pipeline
    python orchestration/run_pipeline.py --skip-ml       # ELT + quality only (CI)
    python orchestration/run_pipeline.py --skip ingest   # skip a stage by tag
"""

from __future__ import annotations

import argparse
import subprocess
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
PY = sys.executable
DBT = str(Path(PY).parent / "dbt")


@dataclass
class Step:
    name: str
    tag: str               # coarse stage tag for --skip (ingest/build/quality/ml)
    argv: list[str]
    cwd: Path
    retries: int = 0       # extra attempts for transient failures
    backoff: float = 2.0


def steps() -> list[Step]:
    ing, dbt_dir, ml = REPO_ROOT / "ingestion", REPO_ROOT / "dbt", REPO_ROOT / "ml"
    return [
        Step("extract_uci", "ingest", [PY, "extract_uci.py"], ing, retries=2),
        Step("generate_transactions", "ingest", [PY, "generate_transactions.py"], ing),
        Step("load_to_duckdb", "ingest", [PY, "load_to_duckdb.py"], ing, retries=2),
        Step("dbt_build", "build", [DBT, "build"], dbt_dir),
        Step("dbt_source_freshness", "build", [DBT, "source", "freshness"], dbt_dir),
        Step("quality_gate", "quality", [PY, "quality/run_quality_checks.py"], REPO_ROOT),
        Step("ml_train", "ml", [PY, "train.py"], ml),
        Step("ml_evaluate", "ml", [PY, "evaluate.py"], ml),
    ]


def run_step(step: Step) -> bool:
    attempts = step.retries + 1
    for attempt in range(1, attempts + 1):
        suffix = "" if attempts == 1 else f" (attempt {attempt}/{attempts})"
        print(f"\n{'='*70}\n▶ {step.name}{suffix}\n{'='*70}", flush=True)
        result = subprocess.run(step.argv, cwd=step.cwd)
        if result.returncode == 0:
            return True
        if attempt < attempts:
            wait = step.backoff * attempt
            print(f"✗ {step.name} failed (exit {result.returncode}); retrying in {wait:.0f}s", flush=True)
            time.sleep(wait)
    print(f"✗ {step.name} failed (exit {result.returncode})", flush=True)
    return False


def main() -> int:
    ap = argparse.ArgumentParser(description="Run the CreditPulse pipeline.")
    ap.add_argument("--skip-ml", action="store_true", help="skip ML train/evaluate (ELT + quality only)")
    ap.add_argument("--skip", nargs="*", default=[], metavar="TAG",
                    help="skip stages by tag: ingest build quality ml")
    args = ap.parse_args()

    skip = set(args.skip) | ({"ml"} if args.skip_ml else set())
    plan = [s for s in steps() if s.tag not in skip]

    print(f"CreditPulse pipeline — {len(plan)} steps"
          + (f" (skipping: {', '.join(sorted(skip))})" if skip else ""))
    started = time.time()
    timings: list[tuple[str, float, str]] = []

    for step in plan:
        t0 = time.time()
        ok = run_step(step)
        timings.append((step.name, time.time() - t0, "ok" if ok else "FAILED"))
        if not ok:
            if step.tag == "quality":
                print("\n⛔ Quality gate failed — pipeline halted before serving. "
                      "Gold tables retain their last-good state.")
            else:
                print(f"\n⛔ Pipeline aborted at '{step.name}'.")
            _summary(timings, time.time() - started, aborted=True)
            return 1

    _summary(timings, time.time() - started, aborted=False)
    return 0


def _summary(timings, total: float, *, aborted: bool) -> None:
    print(f"\n{'─'*70}\nPipeline summary{' (ABORTED)' if aborted else ''}:")
    for name, secs, status in timings:
        mark = "✓" if status == "ok" else "✗"
        print(f"  {mark} {name:<24} {secs:6.1f}s  {status}")
    print(f"  {'total':<26} {total:6.1f}s")


if __name__ == "__main__":
    sys.exit(main())
