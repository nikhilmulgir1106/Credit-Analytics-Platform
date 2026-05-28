"""Train the default-prediction models on the gold feature table.

Two models, both as full sklearn Pipelines (preprocessor + estimator):
  - logistic regression (interpretable baseline)
  - XGBoost (gradient-boosted trees)

Neither rebalances classes, so predicted probabilities stay calibrated as PD
estimates. Fitted pipelines are persisted to ml/artifacts/ for evaluate.py.
"""

from __future__ import annotations

import sys

import joblib
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import roc_auc_score
from sklearn.pipeline import Pipeline
from xgboost import XGBClassifier

import features as ft


def build_models() -> dict[str, Pipeline]:
    return {
        "logreg": Pipeline(
            steps=[
                ("prep", ft.make_preprocessor()),
                ("clf", LogisticRegression(max_iter=1000)),
            ]
        ),
        "xgboost": Pipeline(
            steps=[
                ("prep", ft.make_preprocessor()),
                (
                    "clf",
                    XGBClassifier(
                        n_estimators=300,
                        max_depth=4,
                        learning_rate=0.05,
                        subsample=0.9,
                        colsample_bytree=0.9,
                        eval_metric="logloss",
                        random_state=ft.RANDOM_STATE,
                        n_jobs=2,
                    ),
                ),
            ]
        ),
    }


def main() -> int:
    df = ft.load_features()
    train_df, test_df = ft.split(df)
    X_train, y_train = train_df[ft.FEATURES], train_df[ft.TARGET]
    X_test, y_test = test_df[ft.FEATURES], test_df[ft.TARGET]
    print(f"[train] {len(train_df):,} train / {len(test_df):,} test rows "
          f"(default rate {y_train.mean():.3f} / {y_test.mean():.3f})")

    ft.ARTIFACTS_DIR.mkdir(parents=True, exist_ok=True)
    for name, model in build_models().items():
        model.fit(X_train, y_train)
        train_auc = roc_auc_score(y_train, model.predict_proba(X_train)[:, 1])
        test_auc = roc_auc_score(y_test, model.predict_proba(X_test)[:, 1])
        path = ft.ARTIFACTS_DIR / f"{name}.joblib"
        joblib.dump(model, path)
        print(f"[train] {name:<8} train AUC={train_auc:.4f}  test AUC={test_auc:.4f}  -> {path.name}")

    print("[train] done. Run ml/evaluate.py for full metrics.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
