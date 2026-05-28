"""Load and prepare the gold ML feature table for the default-prediction model.

Reads main_marts.feature_default_prediction from DuckDB (30k rows — small, so
pandas is memory-safe) and provides a deterministic train/test split plus a
scikit-learn preprocessor. train.py and evaluate.py both import from here so they
share one feature definition and one identical split.
"""

from __future__ import annotations

from pathlib import Path

import duckdb
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.impute import SimpleImputer
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

REPO_ROOT = Path(__file__).resolve().parent.parent
DUCKDB_PATH = REPO_ROOT / "warehouse" / "creditpulse.duckdb"
ARTIFACTS_DIR = REPO_ROOT / "ml" / "artifacts"
FEATURE_TABLE = "main_marts.feature_default_prediction"

TARGET = "is_default"
ID = "client_id"
RANDOM_STATE = 42
TEST_SIZE = 0.25

NUMERIC_FEATURES = [
    "credit_limit",
    "age",
    "avg_repay_status",
    "max_repay_status",
    "months_delinquent",
    "total_bill_amt",
    "total_pay_amt",
    "avg_utilization",
    "pay_to_bill_ratio",
]
CATEGORICAL_FEATURES = [
    "sex_code",
    "education_code",
    "marriage_code",
    "age_band",
    "credit_limit_band",
]
FEATURES = NUMERIC_FEATURES + CATEGORICAL_FEATURES

# Segments used for the per-segment risk-score report.
SEGMENT_FEATURES = ["credit_limit_band", "age_band"]


def load_features(duckdb_path: Path = DUCKDB_PATH) -> pd.DataFrame:
    """Load the full gold feature table into a DataFrame."""
    con = duckdb.connect(str(duckdb_path), read_only=True)
    try:
        return con.execute(f"select * from {FEATURE_TABLE}").df()
    finally:
        con.close()


def split(df: pd.DataFrame):
    """Deterministic stratified split. Identical in train.py and evaluate.py."""
    train_df, test_df = train_test_split(
        df,
        test_size=TEST_SIZE,
        random_state=RANDOM_STATE,
        stratify=df[TARGET],
    )
    return train_df, test_df


def make_preprocessor() -> ColumnTransformer:
    """Impute + scale numerics, one-hot encode categoricals.

    Scaling is neutral for tree models and necessary for logistic regression, so
    a single shared preprocessor serves both. Probabilities are left uncalibrated
    by design (no class rebalancing) so calibration can be evaluated honestly.
    """
    numeric = Pipeline(
        steps=[
            ("impute", SimpleImputer(strategy="median")),
            ("scale", StandardScaler()),
        ]
    )
    categorical = OneHotEncoder(handle_unknown="ignore")
    return ColumnTransformer(
        transformers=[
            ("num", numeric, NUMERIC_FEATURES),
            ("cat", categorical, CATEGORICAL_FEATURES),
        ]
    )
