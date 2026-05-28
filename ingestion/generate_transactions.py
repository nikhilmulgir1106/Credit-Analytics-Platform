"""Generate a synthetic daily payment-events feed and land it to the raw zone.

Demonstrates an incremental/streaming-style source (one partition per load_date)
and carries synthetic PII (email, IP) purely to exercise masking in the
governance phase. Deterministic per (load_date, n) so re-runs are idempotent.

Borrower IDs are drawn from the UCI client ID range (1..30000) so the feed can
join to the credit-default borrowers downstream.
"""

from __future__ import annotations

import argparse
import sys
from datetime import datetime, time, timezone

import numpy as np
import pandas as pd
from faker import Faker

from common import raw_partition, today_load_date, write_sidecar

SOURCE = "transactions"
UCI_ID_MAX = 30000
CHANNELS = ["ACH", "CARD", "WIRE", "CHECK"]
TXN_TYPES = ["PAYMENT", "FEE", "ADJUSTMENT"]
STATUSES = ["POSTED", "PENDING", "FAILED"]
STATUS_WEIGHTS = [0.90, 0.07, 0.03]


def generate(n: int, load_date: str) -> pd.DataFrame:
    seed = int(load_date.replace("-", "")) % (2**31)
    rng = np.random.default_rng(seed)
    fake = Faker()
    Faker.seed(seed)

    day = datetime.combine(datetime.fromisoformat(load_date).date(), time(), tzinfo=timezone.utc)
    offsets = rng.integers(0, 86400, size=n)

    return pd.DataFrame(
        {
            "txn_id": [fake.uuid4() for _ in range(n)],
            "borrower_id": rng.integers(1, UCI_ID_MAX + 1, size=n),
            "txn_ts": [day + pd.Timedelta(seconds=int(s)) for s in offsets],
            "amount": np.round(rng.gamma(shape=2.0, scale=120.0, size=n), 2),
            "channel": rng.choice(CHANNELS, size=n),
            "txn_type": rng.choice(TXN_TYPES, size=n, p=[0.85, 0.10, 0.05]),
            "status": rng.choice(STATUSES, size=n, p=STATUS_WEIGHTS),
            # Synthetic PII — exists only to demonstrate masking. Not real.
            "borrower_email": [fake.email() for _ in range(n)],
            "borrower_ip": [fake.ipv4() for _ in range(n)],
        }
    )


def main() -> int:
    ap = argparse.ArgumentParser(description="Generate synthetic transactions feed to raw zone.")
    ap.add_argument("--rows", type=int, default=5000, help="number of events to generate")
    ap.add_argument("--load-date", default=None, help="load_date partition (YYYY-MM-DD)")
    args = ap.parse_args()

    load_date = args.load_date or today_load_date()
    df = generate(args.rows, load_date)

    part = raw_partition(SOURCE, load_date)
    target = part / "transactions.parquet"
    df.to_parquet(target, index=False)
    sidecar = write_sidecar(target, source=SOURCE, row_count=len(df), origin="synthetic:faker")
    print(f"[txn] generated {len(df):,} events -> {target}")
    print(f"[txn] sidecar -> {sidecar}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
