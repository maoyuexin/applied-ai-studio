"""The three compared models and the final exported pipeline (spike-frozen)."""

from __future__ import annotations

import time
from dataclasses import dataclass

import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import FunctionTransformer, StandardScaler

from . import config, features, metrics


@dataclass
class FittedModel:
    """One fitted candidate with its validation evidence."""

    name: str
    estimator: object | None
    val_probabilities: np.ndarray
    fit_seconds: float
    predict_seconds: float


def majority_baseline(y_train: np.ndarray, n_validation: int) -> FittedModel:
    """Predict the training default rate for everyone. No ranking at all."""
    constant = float(np.mean(y_train))
    return FittedModel(
        name="Majority baseline (always predicts the average)",
        estimator=None,
        val_probabilities=np.full(n_validation, constant),
        fit_seconds=0.0,
        predict_seconds=0.0,
    )


def fit_logistic(X_train: np.ndarray, y_train: np.ndarray, X_val: np.ndarray) -> FittedModel:
    """Standard-scaled logistic regression: the credit-scorecard ancestor."""
    pipeline = Pipeline(
        [
            ("scale", StandardScaler()),
            ("clf", LogisticRegression(max_iter=5000, random_state=config.RANDOM_STATE)),
        ]
    )
    start = time.perf_counter()
    pipeline.fit(X_train, y_train)
    fit_seconds = time.perf_counter() - start
    start = time.perf_counter()
    probabilities = pipeline.predict_proba(X_val)[:, 1]
    predict_seconds = time.perf_counter() - start
    return FittedModel("Logistic regression", pipeline, probabilities, fit_seconds, predict_seconds)


def fit_gradient_boosting(
    X_train: np.ndarray, y_train: np.ndarray, X_val: np.ndarray
) -> FittedModel:
    """HistGradientBoostingClassifier with library defaults, seed 42."""
    model = HistGradientBoostingClassifier(random_state=config.RANDOM_STATE)
    start = time.perf_counter()
    model.fit(X_train, y_train)
    fit_seconds = time.perf_counter() - start
    start = time.perf_counter()
    probabilities = model.predict_proba(X_val)[:, 1]
    predict_seconds = time.perf_counter() - start
    return FittedModel("Gradient boosting", model, probabilities, fit_seconds, predict_seconds)


def fit_gradient_boosting_with_protected(
    X_train: np.ndarray,
    y_train: np.ndarray,
    X_val: np.ndarray,
    train_df: pd.DataFrame,
    val_df: pd.DataFrame,
) -> FittedModel:
    """The fairness experiment: same model, protected attributes added back."""
    extra_train = train_df[config.PROTECTED_ATTRIBUTES].to_numpy(np.float64)
    extra_val = val_df[config.PROTECTED_ATTRIBUTES].to_numpy(np.float64)
    model = HistGradientBoostingClassifier(random_state=config.RANDOM_STATE)
    start = time.perf_counter()
    model.fit(np.hstack([X_train, extra_train]), y_train)
    fit_seconds = time.perf_counter() - start
    probabilities = model.predict_proba(np.hstack([X_val, extra_val]))[:, 1]
    return FittedModel(
        "Gradient boosting + SEX/MARRIAGE/AGE", model, probabilities, fit_seconds, 0.0
    )


def leaderboard(candidates: list[FittedModel], y_val: np.ndarray) -> pd.DataFrame:
    """Validation comparison table; every model judged on the identical split."""
    rows = []
    for candidate in candidates:
        scores = metrics.ranking_metrics(y_val, candidate.val_probabilities)
        auc = 0.5 if candidate.estimator is None else scores["auc"]  # constant scores rank nothing
        rows.append(
            {
                "Model": candidate.name,
                "Validation AUC": auc,
                "Validation PR-AUC": scores["pr_auc"],
                "Fit seconds": candidate.fit_seconds,
                "Reason codes available?": {
                    "Majority baseline (always predicts the average)": "none to give",
                    "Logistic regression": "yes (coefficients)",
                    "Gradient boosting": "yes (SHAP)",
                }.get(candidate.name, "-"),
            }
        )
    return pd.DataFrame(rows)


def final_pipeline() -> Pipeline:
    """The exported object: raw account rows in, default probabilities out."""
    return Pipeline(
        [
            ("features", FunctionTransformer(features.build_features)),
            ("model", HistGradientBoostingClassifier(random_state=config.RANDOM_STATE)),
        ]
    )


def fit_final_pipeline(train_df: pd.DataFrame, y_train: np.ndarray) -> tuple[Pipeline, float]:
    """Fit the deployable pipeline on raw training rows."""
    pipeline = final_pipeline()
    start = time.perf_counter()
    pipeline.fit(train_df, y_train)
    return pipeline, time.perf_counter() - start
