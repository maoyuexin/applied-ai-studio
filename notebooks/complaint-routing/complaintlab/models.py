"""The compared models and the deployed pipeline (spike-frozen).

Three things get fitted in this lab:

1. a majority-class baseline that always answers "Credit reporting",
2. the deployed **TF-IDF + logistic regression** pipeline, and
3. the same logistic regression on **MiniLM sentence embeddings**, fitted on
   exactly the same complaints so the comparison measures the representation.

The embeddings are read from a committed parquet. No model is downloaded while
the notebook runs.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field

import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline

from . import config, text_prep


@dataclass
class FittedModel:
    """One fitted candidate with the validation evidence it earned."""

    name: str
    estimator: object | None
    val_predictions: np.ndarray
    val_confidence: np.ndarray
    fit_seconds: float
    predict_seconds: float
    training_rows: int
    representation: str
    notes: str = ""
    val_probabilities: np.ndarray | None = field(default=None, repr=False)
    classes: np.ndarray | None = field(default=None, repr=False)


# ── Baseline ────────────────────────────────────────────────────────────────

def majority_baseline(y_train: pd.Series, n_validation: int) -> FittedModel:
    """Send every complaint to the biggest team. No reading involved."""
    majority = y_train.value_counts().idxmax()
    return FittedModel(
        name=f"Majority baseline (always {majority})",
        estimator=None,
        val_predictions=np.full(n_validation, majority, dtype=object),
        val_confidence=np.ones(n_validation),
        fit_seconds=0.0,
        predict_seconds=0.0,
        training_rows=len(y_train),
        representation="none - ignores the text",
        notes="no routing words, no confidence, nothing to explain",
    )


# ── The deployed model ──────────────────────────────────────────────────────

def build_pipeline(min_df: int | None = None) -> Pipeline:
    """TF-IDF then logistic regression: the object that ships."""
    return Pipeline(
        [
            ("tfidf", text_prep.build_vectorizer(min_df)),
            (
                "lr",
                LogisticRegression(
                    C=config.LR_C,
                    max_iter=config.LR_MAX_ITER,
                    random_state=config.RANDOM_STATE,
                ),
            ),
        ]
    )


def fit_tfidf(
    X_train: pd.Series,
    y_train: pd.Series,
    X_val: pd.Series,
    name: str = "TF-IDF + logistic regression",
    min_df: int | None = None,
) -> FittedModel:
    """Fit the deployable pipeline and score the validation split."""
    pipeline = build_pipeline(min_df)
    start = time.perf_counter()
    pipeline.fit(X_train, y_train)
    fit_seconds = time.perf_counter() - start

    start = time.perf_counter()
    probabilities = pipeline.predict_proba(X_val)
    predict_seconds = time.perf_counter() - start

    classes = pipeline.named_steps["lr"].classes_
    return FittedModel(
        name=name,
        estimator=pipeline,
        val_predictions=classes[np.argmax(probabilities, axis=1)],
        val_confidence=probabilities.max(axis=1),
        fit_seconds=fit_seconds,
        predict_seconds=predict_seconds,
        training_rows=len(X_train),
        representation=(
            f"{len(pipeline.named_steps['tfidf'].vocabulary_):,} word and phrase counts"
        ),
        notes="routing words readable straight off the coefficients",
        val_probabilities=probabilities,
        classes=classes,
    )


# ── The matched representation comparison ───────────────────────────────────

def comparison_subsample(train_df: pd.DataFrame) -> pd.DataFrame:
    """The fixed 15,000 training complaints both representations learn from.

    Stratified by team with seed 42, so the subsample keeps the training split's
    team mix and every run selects the identical complaint ids.
    """
    subsample, _ = train_test_split(
        train_df,
        train_size=config.COMPARE_TRAIN_ROWS,
        stratify=train_df[config.TARGET],
        random_state=config.RANDOM_STATE,
    )
    return subsample.sort_values("complaint_id").reset_index(drop=True)


def load_embeddings(path, complaint_ids: pd.Series) -> np.ndarray:
    """Read committed float16 embeddings and align them to the given ids.

    Raises if a complaint is missing, so a stale embedding file can never be
    silently paired with the wrong rows.
    """
    stored = pd.read_parquet(path).set_index("complaint_id")
    missing = set(complaint_ids) - set(stored.index)
    if missing:
        raise ValueError(
            f"{len(missing):,} complaints have no committed embedding. "
            "Re-run scripts/build_embeddings.py."
        )
    dimensions = [f"dim_{i:03d}" for i in range(config.EMBEDDING_DIM)]
    return stored.loc[complaint_ids, dimensions].to_numpy(np.float32)


def fit_embedding_model(
    E_train: np.ndarray,
    y_train: pd.Series,
    E_val: np.ndarray,
    name: str = "MiniLM embeddings + logistic regression",
) -> FittedModel:
    """The same logistic regression, reading 384 numbers instead of word counts."""
    classifier = LogisticRegression(
        C=config.LR_C, max_iter=config.LR_MAX_ITER, random_state=config.RANDOM_STATE
    )
    start = time.perf_counter()
    classifier.fit(E_train, y_train)
    fit_seconds = time.perf_counter() - start

    start = time.perf_counter()
    probabilities = classifier.predict_proba(E_val)
    predict_seconds = time.perf_counter() - start

    classes = classifier.classes_
    return FittedModel(
        name=name,
        estimator=classifier,
        val_predictions=classes[np.argmax(probabilities, axis=1)],
        val_confidence=probabilities.max(axis=1),
        fit_seconds=fit_seconds,
        predict_seconds=predict_seconds,
        training_rows=len(E_train),
        representation=f"{config.EMBEDDING_DIM} embedding numbers",
        notes="no word-level reason to show a triage clerk",
        val_probabilities=probabilities,
        classes=classes,
    )


# ── Leaderboards ────────────────────────────────────────────────────────────

def leaderboard(candidates: list[FittedModel], y_val: pd.Series) -> pd.DataFrame:
    """Validation comparison; every candidate judged on the identical split."""
    from . import metrics

    rows = []
    for candidate in candidates:
        scores = metrics.classification_scores(y_val, candidate.val_predictions)
        rows.append(
            {
                "Model": candidate.name,
                "Trained on": candidate.training_rows,
                "Representation": candidate.representation,
                "Validation accuracy": scores["accuracy"],
                "Validation macro-F1": scores["macro_f1"],
                "Fit seconds": round(candidate.fit_seconds, 1),
                "Explanation available": candidate.notes,
            }
        )
    return pd.DataFrame(rows)


def min_df_tuning(
    X_train: pd.Series, y_train: pd.Series, X_val: pd.Series, y_val: pd.Series
) -> pd.DataFrame:
    """The one hyper-parameter this lab tunes, and the evidence it barely matters."""
    from . import metrics

    rows = []
    for min_df in (2, 5, 10):
        fitted = fit_tfidf(X_train, y_train, X_val, min_df=min_df)
        scores = metrics.classification_scores(y_val, fitted.val_predictions)
        rows.append(
            {
                "min_df (times a word must appear to be kept)": min_df,
                "Columns kept": len(fitted.estimator.named_steps["tfidf"].vocabulary_),
                "Validation accuracy": scores["accuracy"],
                "Validation macro-F1": scores["macro_f1"],
                "Fit seconds": round(fitted.fit_seconds, 1),
            }
        )
    return pd.DataFrame(rows)
