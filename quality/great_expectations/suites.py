"""Great Expectations suites for the gold layer (GE 1.x, code-defined).

Each suite targets one gold table and lists expectations tagged with a severity
in ``meta``:

  - "blocking" : a failure halts the pipeline (the data-quality gate).
  - "warning"  : a failure is logged/alerted but does not halt the pipeline.

GE 1.x removed the `great_expectations` CLI, so suites are defined in code and
executed by quality/run_quality_checks.py rather than a YAML checkpoint.
"""

from __future__ import annotations

import great_expectations as gx
from great_expectations import expectations as gxe

BLOCKING = {"severity": "blocking"}
WARNING = {"severity": "warning"}

# Known UCI category sets — used for category/schema-drift detection.
_SEGMENT_DIMENSIONS = ["age_band", "credit_limit_band", "education_level", "sex", "marital_status", "region"]


def get_suites() -> list[dict]:
    """Return suite specs: name, target DuckDB relation, and expectations."""
    return [
        {
            "name": "feature_default_prediction",
            "table": "main_marts.feature_default_prediction",
            "expectations": [
                # Volume.
                gxe.ExpectTableRowCountToBeBetween(min_value=25_000, max_value=35_000, meta=BLOCKING),
                # Key integrity.
                gxe.ExpectColumnValuesToNotBeNull(column="client_id", meta=BLOCKING),
                gxe.ExpectColumnValuesToBeUnique(column="client_id", meta=BLOCKING),
                # Label integrity.
                gxe.ExpectColumnValuesToNotBeNull(column="is_default", meta=BLOCKING),
                gxe.ExpectColumnValuesToBeInSet(column="is_default", value_set=[0, 1], meta=BLOCKING),
                # Value ranges.
                gxe.ExpectColumnValuesToBeBetween(column="credit_limit", min_value=0, max_value=2_000_000, meta=BLOCKING),
                gxe.ExpectColumnValuesToBeBetween(column="age", min_value=18, max_value=100, meta=BLOCKING),
                gxe.ExpectColumnValuesToBeBetween(column="months_delinquent", min_value=0, max_value=6, meta=BLOCKING),
                # Distributional (drift) — warn only.
                gxe.ExpectColumnMeanToBeBetween(column="is_default", min_value=0.15, max_value=0.30, meta=WARNING),
                gxe.ExpectColumnValuesToBeBetween(column="max_repay_status", min_value=-2, max_value=9, meta=WARNING),
            ],
        },
        {
            "name": "dim_borrower",
            "table": "main_marts.dim_borrower",
            "expectations": [
                gxe.ExpectTableRowCountToBeBetween(min_value=25_000, max_value=35_000, meta=BLOCKING),
                gxe.ExpectColumnValuesToNotBeNull(column="client_id", meta=BLOCKING),
                gxe.ExpectColumnValuesToBeUnique(column="client_id", meta=BLOCKING),
                gxe.ExpectColumnValuesToBeInSet(column="sex", value_set=["male", "female", "unknown"], meta=BLOCKING),
            ],
        },
        {
            "name": "mart_portfolio_risk",
            "table": "main_marts.mart_portfolio_risk",
            "expectations": [
                gxe.ExpectTableRowCountToBeBetween(min_value=1, max_value=100, meta=BLOCKING),
                gxe.ExpectColumnValuesToBeBetween(column="default_rate", min_value=0, max_value=1, meta=BLOCKING),
                gxe.ExpectColumnValuesToBeBetween(column="n_clients", min_value=1, meta=BLOCKING),
                # Category drift — warn if an unexpected segment dimension appears.
                gxe.ExpectColumnValuesToBeInSet(column="segment_dimension", value_set=_SEGMENT_DIMENSIONS, meta=WARNING),
            ],
        },
    ]


# Re-exported so the runner doesn't import gx directly just to build a context.
get_context = gx.get_context
ExpectationSuite = gx.ExpectationSuite
ValidationDefinition = gx.ValidationDefinition
