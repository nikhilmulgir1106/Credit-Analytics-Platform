"""Evaluate the default-prediction models and publish risk scores.

Metrics on the held-out test set, per model:
  - AUC        : ranking quality (roc_auc_score)
  - KS         : max separation between good/bad score CDFs = max(TPR - FPR)
  - Brier      : mean squared error of predicted PD (calibration quality)
  - calibration: predicted vs observed default rate by probability decile

Also reports per-segment predicted PD vs actual default rate and writes a PD per
borrower to meta.model_scores for the dashboard. No plotting dependency — tables
only; the Streamlit dashboard (phase 7) renders charts from these outputs.
"""

from __future__ import annotations

import json
import sys

import duckdb
import joblib
import numpy as np
import pandas as pd
from sklearn.calibration import calibration_curve
from sklearn.metrics import brier_score_loss, roc_auc_score, roc_curve

import features as ft

MODELS = ["logreg", "xgboost"]


def ks_statistic(y_true, y_score) -> float:
    fpr, tpr, _ = roc_curve(y_true, y_score)
    return float(np.max(tpr - fpr))


def calibration_table(y_true, y_score, n_bins: int = 10) -> pd.DataFrame:
    prob_true, prob_pred = calibration_curve(y_true, y_score, n_bins=n_bins, strategy="quantile")
    return pd.DataFrame(
        {"bin": range(1, len(prob_true) + 1),
         "predicted_pd": np.round(prob_pred, 4),
         "observed_default_rate": np.round(prob_true, 4)}
    )


def main() -> int:
    df = ft.load_features()
    _, test_df = ft.split(df)
    X_test, y_test = test_df[ft.FEATURES], test_df[ft.TARGET]

    models = {}
    for name in MODELS:
        path = ft.ARTIFACTS_DIR / f"{name}.joblib"
        if not path.exists():
            print(f"[eval] missing {path} — run ml/train.py first")
            return 1
        models[name] = joblib.load(path)

    metrics = {}
    print(f"\n[eval] held-out test set: {len(test_df):,} rows, "
          f"actual default rate {y_test.mean():.4f}\n")
    for name, model in models.items():
        pd_score = model.predict_proba(X_test)[:, 1]
        m = {
            "auc": round(roc_auc_score(y_test, pd_score), 4),
            "ks": round(ks_statistic(y_test, pd_score), 4),
            "brier": round(brier_score_loss(y_test, pd_score), 4),
        }
        metrics[name] = m
        print(f"=== {name} ===")
        print(f"  AUC={m['auc']}  KS={m['ks']}  Brier={m['brier']}")
        print("  calibration (predicted PD vs observed, by decile):")
        print(calibration_table(y_test, pd_score).to_string(index=False))
        print()

    # Champion = highest AUC.
    champion = max(metrics, key=lambda k: metrics[k]["auc"])
    print(f"[eval] champion model: {champion} (AUC={metrics[champion]['auc']})\n")

    # Per-segment predicted PD vs actual (champion model).
    champ = models[champion]
    seg = test_df[[*ft.SEGMENT_FEATURES, ft.TARGET]].copy()
    seg["pd"] = champ.predict_proba(X_test)[:, 1]
    print(f"[eval] {champion} predicted PD vs actual default rate by credit_limit_band:")
    by_band = (
        seg.groupby("credit_limit_band")
        .agg(n=("pd", "size"), predicted_pd=("pd", "mean"), actual_default_rate=(ft.TARGET, "mean"))
        .round(4)
        .sort_values("predicted_pd", ascending=False)
    )
    print(by_band.to_string())
    print()

    # Publish a PD per borrower for the dashboard (score the full table).
    X_all = df[ft.FEATURES]
    test_ids = set(test_df[ft.ID])
    scores = pd.DataFrame({
        ft.ID: df[ft.ID].values,
        "pd_logreg": models["logreg"].predict_proba(X_all)[:, 1],
        "pd_xgboost": models["xgboost"].predict_proba(X_all)[:, 1],
        "is_default": df[ft.TARGET].values,
        "is_test": df[ft.ID].isin(test_ids).values,
    })
    con = duckdb.connect(str(ft.DUCKDB_PATH))
    try:
        con.execute("CREATE SCHEMA IF NOT EXISTS meta")
        con.register("scores_df", scores)
        con.execute("CREATE OR REPLACE TABLE meta.model_scores AS SELECT * FROM scores_df")
        con.unregister("scores_df")
    finally:
        con.close()
    print(f"[eval] wrote {len(scores):,} PD scores -> meta.model_scores")

    # Persist metrics.
    metrics_path = ft.ARTIFACTS_DIR / "metrics.json"
    metrics_path.write_text(json.dumps({"champion": champion, "models": metrics}, indent=2))
    print(f"[eval] metrics -> {metrics_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
