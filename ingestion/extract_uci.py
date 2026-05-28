"""Extract the UCI 'Default of Credit Card Clients' dataset into the raw zone.

Downloads the source .xls (~5.5 MB, 30k rows) and lands it verbatim under
data/raw/uci/load_date=YYYY-MM-DD/ with a provenance sidecar. Idempotent:
re-running with the file already present is a no-op unless --force is passed.

The .xls is the immutable bronze artifact; type conversion happens later in
the DuckDB loader, not here.
"""

from __future__ import annotations

import argparse
import io
import sys
import zipfile

import requests

from common import raw_partition, today_load_date, write_sidecar

SOURCE = "uci"
URL = "https://archive.ics.uci.edu/static/public/350/default+of+credit+card+clients.zip"
MEMBER = "default of credit card clients.xls"
LANDED_NAME = "default_of_credit_card_clients.xls"


def extract(force: bool = False, load_date: str | None = None) -> None:
    load_date = load_date or today_load_date()
    part = raw_partition(SOURCE, load_date)
    target = part / LANDED_NAME

    if target.exists() and not force:
        print(f"[uci] already landed: {target} (use --force to re-download)")
        return

    print(f"[uci] downloading {URL}")
    resp = requests.get(URL, timeout=120)
    resp.raise_for_status()
    payload = resp.content
    print(f"[uci] downloaded {len(payload):,} bytes; extracting '{MEMBER}'")

    with zipfile.ZipFile(io.BytesIO(payload)) as zf:
        with zf.open(MEMBER) as member:
            target.write_bytes(member.read())

    sidecar = write_sidecar(target, source=SOURCE, row_count=None, origin=URL)
    print(f"[uci] landed -> {target} ({target.stat().st_size:,} bytes)")
    print(f"[uci] sidecar -> {sidecar}")


def main() -> int:
    ap = argparse.ArgumentParser(description="Extract UCI credit-default dataset to raw zone.")
    ap.add_argument("--force", action="store_true", help="re-download even if already landed")
    ap.add_argument("--load-date", default=None, help="override load_date partition (YYYY-MM-DD)")
    args = ap.parse_args()
    extract(force=args.force, load_date=args.load_date)
    return 0


if __name__ == "__main__":
    sys.exit(main())
