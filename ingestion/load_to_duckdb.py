"""Load landed raw files into the DuckDB RAW (bronze) schema.

Bronze rules (ARCHITECTURE.md): append-only, verbatim, every row stamped with
load metadata (_source_file, _load_date, _loaded_at). Loads are idempotent —
re-running a partition deletes and re-inserts only that partition, so the step
is safe to repeat.

Sources:
  - uci          : legacy .xls read via pandas (small, 30k rows), registered to DuckDB.
  - transactions : parquet read natively by DuckDB.
  - lending_club : CSV/parquet streamed by DuckDB if a file is present; skipped otherwise
                   (never loaded into pandas — it can be multi-GB).
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import duckdb
import pandas as pd

from common import DATA_DIR, RAW_DIR, REPO_ROOT

DUCKDB_PATH = REPO_ROOT / "warehouse" / "creditpulse.duckdb"
RAW_SCHEMA = "raw"

META_COLS = """
  '{source_file}' AS _source_file,
  DATE '{load_date}' AS _load_date,
  now() AS _loaded_at
"""


def latest_partition(source: str) -> tuple[Path, str] | None:
    """Return (partition_dir, load_date) for the newest load_date of a source."""
    base = RAW_DIR / source
    parts = sorted(p for p in base.glob("load_date=*") if p.is_dir())
    if not parts:
        return None
    part = parts[-1]
    return part, part.name.split("=", 1)[1]


def idempotent_load(con: duckdb.DuckDBPyConnection, table: str, base_sql: str, where: str) -> int:
    """Create table if needed, replace the target partition, return row count loaded."""
    con.execute(f"CREATE TABLE IF NOT EXISTS {table} AS {base_sql} LIMIT 0")
    con.execute(f"DELETE FROM {table} WHERE {where}")
    con.execute(f"INSERT INTO {table} {base_sql}")
    return con.execute(f"SELECT count(*) FROM {table} WHERE {where}").fetchone()[0]


def load_uci(con: duckdb.DuckDBPyConnection) -> None:
    found = latest_partition("uci")
    if not found:
        print("[uci] no raw partition found — run extract_uci.py first; skipping")
        return
    part, load_date = found
    xls = part / "default_of_credit_card_clients.xls"
    # Row 2 of the sheet holds the real headers; row 1 is a column-group banner.
    df = pd.read_excel(xls, header=1)  # noqa: F841 — registered into DuckDB below
    con.register("uci_df", df)
    base = (
        "SELECT *, "
        + META_COLS.format(source_file=xls.name, load_date=load_date)
        + " FROM uci_df"
    )
    n = idempotent_load(con, f"{RAW_SCHEMA}.uci_credit_default", base, f"_load_date = DATE '{load_date}'")
    con.unregister("uci_df")
    print(f"[uci] loaded partition {load_date}: {n:,} rows -> {RAW_SCHEMA}.uci_credit_default")


def load_transactions(con: duckdb.DuckDBPyConnection) -> None:
    found = latest_partition("transactions")
    if not found:
        print("[txn] no raw partition found — run generate_transactions.py first; skipping")
        return
    part, load_date = found
    pq = part / "transactions.parquet"
    base = (
        "SELECT *, "
        + META_COLS.format(source_file=pq.name, load_date=load_date)
        + f" FROM read_parquet('{pq.as_posix()}')"
    )
    n = idempotent_load(con, f"{RAW_SCHEMA}.transactions", base, f"_load_date = DATE '{load_date}'")
    print(f"[txn] loaded partition {load_date}: {n:,} rows -> {RAW_SCHEMA}.transactions")


def load_lending_club(con: duckdb.DuckDBPyConnection) -> None:
    """Stream a Lending Club CSV/parquet via DuckDB if the user has provided one.

    Looks under data/raw/lending_club/ (or data/lending_club/). Never uses pandas
    — DuckDB reads the file directly so a multi-GB tape never lands in RAM.
    """
    search_dirs = [RAW_DIR / "lending_club", DATA_DIR / "lending_club"]
    files: list[Path] = []
    for d in search_dirs:
        if d.exists():
            files += sorted(d.rglob("*.parquet")) + sorted(d.rglob("*.csv"))
    if not files:
        print("[lc] no Lending Club file found under data/raw/lending_club/ — skipping "
              "(drop a .csv/.parquet there and re-run to load it)")
        return

    src = files[0]
    reader = "read_parquet" if src.suffix == ".parquet" else "read_csv_auto"
    load_date = "1970-01-01"  # provided-file load; partition keyed by _source_file
    base = (
        "SELECT *, "
        + META_COLS.format(source_file=src.name, load_date=load_date)
        + f" FROM {reader}('{src.as_posix()}')"
    )
    n = idempotent_load(
        con, f"{RAW_SCHEMA}.lending_club_loans", base, f"_source_file = '{src.name}'"
    )
    print(f"[lc] loaded {src.name}: {n:,} rows -> {RAW_SCHEMA}.lending_club_loans")


def main() -> int:
    ap = argparse.ArgumentParser(description="Load raw files into DuckDB RAW (bronze) schema.")
    ap.add_argument(
        "--sources",
        nargs="*",
        default=["uci", "transactions", "lending_club"],
        help="which sources to load",
    )
    args = ap.parse_args()

    DUCKDB_PATH.parent.mkdir(parents=True, exist_ok=True)
    con = duckdb.connect(str(DUCKDB_PATH))
    try:
        con.execute(f"CREATE SCHEMA IF NOT EXISTS {RAW_SCHEMA}")
        if "uci" in args.sources:
            load_uci(con)
        if "transactions" in args.sources:
            load_transactions(con)
        if "lending_club" in args.sources:
            load_lending_club(con)

        print("\n[raw] tables in schema:")
        names = [
            r[0]
            for r in con.execute(
                "SELECT table_name FROM duckdb_tables() "
                f"WHERE schema_name = '{RAW_SCHEMA}' ORDER BY table_name"
            ).fetchall()
        ]
        for name in names:
            count = con.execute(f"SELECT count(*) FROM {RAW_SCHEMA}.{name}").fetchone()[0]
            print(f"  {RAW_SCHEMA}.{name}: {count:,} rows")
    finally:
        con.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
