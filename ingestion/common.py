"""Shared ingestion helpers: repo paths, load-date partitioning, metadata sidecars.

Bronze principle (see ARCHITECTURE.md): landed raw files are verbatim and
immutable, partitioned by source/load_date, with a metadata sidecar recording
provenance (row count, bytes, checksum, source, load timestamp).
"""

from __future__ import annotations

import hashlib
import json
from datetime import date, datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = REPO_ROOT / "data"
RAW_DIR = DATA_DIR / "raw"


def today_load_date() -> str:
    """Partition key for today's load (UTC), e.g. '2026-05-28'."""
    return date.today().isoformat()


def raw_partition(source: str, load_date: str | None = None) -> Path:
    """Return (and create) the raw landing dir for a source/load_date."""
    load_date = load_date or today_load_date()
    part = RAW_DIR / source / f"load_date={load_date}"
    part.mkdir(parents=True, exist_ok=True)
    return part


def sha256_of(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def write_sidecar(data_file: Path, *, source: str, row_count: int | None, origin: str) -> Path:
    """Write a <file>.meta.json sidecar describing a landed raw file."""
    meta = {
        "source": source,
        "data_file": data_file.name,
        "origin": origin,
        "row_count": row_count,
        "byte_size": data_file.stat().st_size,
        "sha256": sha256_of(data_file),
        "loaded_at": datetime.now(timezone.utc).isoformat(),
    }
    sidecar = data_file.with_suffix(data_file.suffix + ".meta.json")
    sidecar.write_text(json.dumps(meta, indent=2))
    return sidecar
