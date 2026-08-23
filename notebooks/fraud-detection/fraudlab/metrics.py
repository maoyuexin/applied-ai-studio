"""Scoring, read off a confusion matrix.

The 2x2 is the instrument here. Accuracy is the one reading off it that lies when
the interesting case is rare, and precision and recall are the readings that do
not -- both are confusion-matrix numbers.

Models are compared at the threshold that spends the same **review budget**, not
at a fixed 0.5 cutoff. Six models put their scores in six different places on the
0-1 line; at 0.5 one flags everything and another flags nothing, so a fixed
cutoff would measure score distribution rather than skill.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from . import config


def threshold_for_budget(scores: np.ndarray, budget: float = config.REVIEW_BUDGET) -> float:
    """The cutoff that sends roughly `budget` of transactions to a human."""
    return float(np.quantile(np.asarray(scores, dtype=float), 1.0 - budget))


def has_ranking(scores: np.ndarray) -> bool:
    """Whether the scores order anything at all.

    A constant scorer -- "never fraud" -- cannot spend a review budget, because
    there is no ranking to spend it on. Flagging an arbitrary 3% of identical
    scores would invent skill the model does not have.
    """
    scores = np.asarray(scores, dtype=float)
    return bool(scores.size and scores.max() > scores.min())


def flag_top_k(scores: np.ndarray, k: int) -> np.ndarray:
    """Flag the k highest-scoring transactions, breaking ties deterministically.

    Rank-based rather than threshold-based, so a model that piles thousands of
    transactions on the same score still spends exactly the agreed budget.
    """
    scores = np.asarray(scores, dtype=float)
    flags = np.zeros(scores.size, dtype=bool)
    k = int(min(max(k, 0), scores.size))
    if k == 0 or not has_ranking(scores):
        return flags
    flags[np.argsort(-scores, kind="stable")[:k]] = True
    return flags


def _summarise(y_true: np.ndarray, flagged: np.ndarray,
               amounts: np.ndarray | None, threshold: float) -> dict[str, float]:
    tp = int(np.sum(flagged & (y_true == 1)))
    fp = int(np.sum(flagged & (y_true == 0)))
    fn = int(np.sum(~flagged & (y_true == 1)))
    tn = int(np.sum(~flagged & (y_true == 0)))
    total = tp + fp + fn + tn

    precision = tp / (tp + fp) if (tp + fp) else 0.0
    recall = tp / (tp + fn) if (tp + fn) else 0.0
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) else 0.0

    review_hours = (tp + fp) * config.REVIEW_MINUTES_PER_TXN / 60.0
    result = {
        "threshold": float(threshold),
        "tp": tp, "fp": fp, "fn": fn, "tn": tn,
        "flagged": tp + fp,
        "review_rate": (tp + fp) / total if total else 0.0,
        "precision": precision,
        "recall": recall,
        "f1": f1,
        "accuracy": (tp + tn) / total if total else 0.0,
        "review_hours": review_hours,
        "review_cost": review_hours * config.ANALYST_HOURLY_RATE,
    }

    if amounts is not None:
        amounts = np.asarray(amounts, dtype=float)
        caught = float(np.sum(amounts[flagged & (y_true == 1)]))
        missed = float(np.sum(amounts[~flagged & (y_true == 1)]))
        result["dollars_caught"] = caught
        result["dollars_missed"] = missed
        result["net_benefit"] = caught - result["review_cost"]

    return result


def confusion_at_threshold(
    y_true: np.ndarray,
    scores: np.ndarray,
    threshold: float,
    amounts: np.ndarray | None = None,
) -> dict[str, float]:
    """Every number the leaderboard quotes, derived from four counts."""
    y_true = np.asarray(y_true).astype(int)
    flagged = np.asarray(scores, dtype=float) >= threshold
    return _summarise(y_true, flagged, amounts, threshold)


def confusion_frame(result: dict[str, float]) -> pd.DataFrame:
    """The four boxes, laid out the way they go on a slide."""
    return pd.DataFrame(
        {
            "Actually fraud": [result["tp"], result["fn"], result["tp"] + result["fn"]],
            "Actually clean": [result["fp"], result["tn"], result["fp"] + result["tn"]],
            "Row total": [
                result["tp"] + result["fp"],
                result["fn"] + result["tn"],
                result["tp"] + result["fp"] + result["fn"] + result["tn"],
            ],
        },
        index=["Model flagged it", "Model cleared it", "Column total"],
    )


def never_fraud_baseline(y_true: np.ndarray, amounts: np.ndarray | None = None) -> dict[str, float]:
    """One line of code that flags nothing -- and posts a very good accuracy."""
    y_true = np.asarray(y_true).astype(int)
    flagged = np.zeros(len(y_true), dtype=bool)
    return _summarise(y_true, flagged, amounts, threshold=float("inf"))


def threshold_sweep(
    y_true: np.ndarray,
    scores: np.ndarray,
    amounts: np.ndarray | None = None,
    n_points: int = 60,
) -> pd.DataFrame:
    """Walk the review budget from strict to permissive and record the trade at each stop."""
    y_true = np.asarray(y_true).astype(int)
    budgets = np.linspace(0.001, 0.35, n_points)
    rows = [evaluate_at_budget(y_true, scores, amounts, float(b)) for b in budgets]
    return pd.DataFrame(rows)


def evaluate_at_budget(
    y_true: np.ndarray,
    scores: np.ndarray,
    amounts: np.ndarray | None = None,
    budget: float = config.REVIEW_BUDGET,
) -> dict[str, float]:
    """Score a model at the threshold that spends the agreed review budget.

    This is what makes six models with six different score distributions
    comparable: they all get the same number of analyst-minutes to spend.
    """
    y_true = np.asarray(y_true).astype(int)
    scores = np.asarray(scores, dtype=float)
    flagged = flag_top_k(scores, int(round(budget * len(scores))))
    threshold = float(scores[flagged].min()) if flagged.any() else float("inf")
    return _summarise(y_true, flagged, amounts, threshold)


def weekly_performance(
    frame: pd.DataFrame, scores: np.ndarray, threshold: float
) -> pd.DataFrame:
    """Precision and recall week by week -- what monitoring actually watches."""
    work = frame[["trans_date_trans_time", "is_fraud", "amt"]].copy()
    work["flagged"] = np.asarray(scores, dtype=float) >= threshold

    weekly = (
        work.set_index("trans_date_trans_time")
        .resample("W")
        .apply(
            lambda g: pd.Series(
                {
                    "tp": int(((g["flagged"]) & (g["is_fraud"] == 1)).sum()),
                    "fp": int(((g["flagged"]) & (g["is_fraud"] == 0)).sum()),
                    "fn": int(((~g["flagged"]) & (g["is_fraud"] == 1)).sum()),
                }
            )
        )
        .reset_index()
    )
    weekly["precision"] = weekly["tp"] / (weekly["tp"] + weekly["fp"]).replace(0, np.nan)
    weekly["recall"] = weekly["tp"] / (weekly["tp"] + weekly["fn"]).replace(0, np.nan)
    return weekly
