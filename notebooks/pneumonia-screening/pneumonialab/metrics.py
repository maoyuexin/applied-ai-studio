"""Classification metrics and validation-selected operating policy."""

from __future__ import annotations

import numpy as np
import pandas as pd
from sklearn.metrics import average_precision_score, roc_auc_score


def evaluate(labels: np.ndarray, scores: np.ndarray, threshold: float) -> dict[str, float | int]:
    """Evaluate one operating cutoff from a complete confusion matrix."""
    truth = np.asarray(labels, dtype=int).reshape(-1)
    estimates = np.asarray(scores, dtype=float).reshape(-1)
    if len(truth) != len(estimates):
        raise ValueError("labels and scores must have the same length.")
    predicted = estimates >= threshold
    positive = truth == 1
    tp = int(np.count_nonzero(predicted & positive))
    fp = int(np.count_nonzero(predicted & ~positive))
    fn = int(np.count_nonzero(~predicted & positive))
    tn = int(np.count_nonzero(~predicted & ~positive))

    def ratio(numerator: int, denominator: int) -> float:
        return numerator / denominator if denominator else 0.0

    sensitivity = ratio(tp, tp + fn)
    specificity = ratio(tn, tn + fp)
    precision = ratio(tp, tp + fp)
    accuracy = ratio(tp + tn, len(truth))
    return {
        "threshold": float(threshold),
        "tp": tp,
        "fp": fp,
        "fn": fn,
        "tn": tn,
        "sensitivity": sensitivity,
        "specificity": specificity,
        "precision": precision,
        "accuracy": accuracy,
        "balanced_accuracy": (sensitivity + specificity) / 2,
        "review_rate": ratio(tp + fp, len(truth)),
        "roc_auc": float(roc_auc_score(truth, estimates)),
        "average_precision": float(average_precision_score(truth, estimates)),
    }


def select_threshold(
    labels: np.ndarray,
    scores: np.ndarray,
    target_sensitivity: float,
) -> dict[str, float | int]:
    """Choose the highest validation cutoff that meets the sensitivity objective."""
    if not 0 < target_sensitivity <= 1:
        raise ValueError("target_sensitivity must be in (0, 1].")
    for threshold in np.sort(np.unique(np.asarray(scores, dtype=float)))[::-1]:
        result = evaluate(labels, scores, float(threshold))
        if result["sensitivity"] >= target_sensitivity:
            return result
    return evaluate(labels, scores, float("-inf"))


def threshold_sweep(
    labels: np.ndarray,
    scores: np.ndarray,
    selected_threshold: float | None = None,
) -> pd.DataFrame:
    """Return a compact threshold-policy table for teaching and plotting."""
    quantiles = np.linspace(0.0, 1.0, 41)
    thresholds = np.quantile(np.asarray(scores, dtype=float), quantiles)
    if selected_threshold is not None:
        thresholds = np.append(thresholds, selected_threshold)
    rows = [evaluate(labels, scores, float(value)) for value in np.unique(thresholds)]
    frame = pd.DataFrame(rows).sort_values("threshold", ascending=False).reset_index(drop=True)
    return frame


def majority_baseline(labels: np.ndarray) -> dict[str, float | int]:
    """Show why accuracy alone rewards an always-pneumonia prediction."""
    truth = np.asarray(labels, dtype=int).reshape(-1)
    scores = np.ones(len(truth), dtype=float)
    return evaluate(truth, scores, 0.5)


def policy_summary(
    result: dict[str, float | int],
    target_sensitivity: float,
) -> pd.DataFrame:
    """Present a selected validation policy in beginner-friendly language."""
    tp, fp = int(result["tp"]), int(result["fp"])
    fn, tn = int(result["fn"]), int(result["tn"])
    total = tp + fp + fn + tn
    return pd.DataFrame(
        [
            {
                "Policy item": "Sensitivity target",
                "Value": f"{target_sensitivity:.1%}",
                "Plain meaning": "Prioritize at least this share of pneumonia-labeled validation images.",
            },
            {
                "Policy item": "Selected cutoff",
                "Value": f"{float(result['threshold']):.3f}",
                "Plain meaning": "Scores at or above this value enter priority review.",
            },
            {
                "Policy item": "Sensitivity at cutoff",
                "Value": f"{tp} / {tp + fn} = {float(result['sensitivity']):.1%}",
                "Plain meaning": "Of all pneumonia-labeled validation images, this many enter priority review.",
            },
            {
                "Policy item": "Specificity at cutoff",
                "Value": f"{tn} / {tn + fp} = {float(result['specificity']):.1%}",
                "Plain meaning": "Of all normal-labeled validation images, this many remain in standard review.",
            },
            {
                "Policy item": "Priority-review percentage (workload)",
                "Value": f"{tp + fp} / {total} = {float(result['review_rate']):.1%}",
                "Plain meaning": "Of every validation image, this many enter the priority queue; all others still receive standard review.",
            },
        ]
    )


def metric_summary(result: dict[str, float | int]) -> pd.DataFrame:
    """Show measured metrics with their confusion-matrix calculations and questions."""
    tp, fp = int(result["tp"]), int(result["fp"])
    fn, tn = int(result["fn"]), int(result["tn"])
    total = tp + fp + fn + tn
    rows = [
        (
            "Sensitivity (recall)",
            f"{tp} / ({tp} + {fn})",
            f"{float(result['sensitivity']):.1%}",
            "Of pneumonia-labeled images, how many entered priority review?",
        ),
        (
            "Specificity",
            f"{tn} / ({tn} + {fp})",
            f"{float(result['specificity']):.1%}",
            "Of normal-labeled images, how many stayed in standard review?",
        ),
        (
            "Precision",
            f"{tp} / ({tp} + {fp})",
            f"{float(result['precision']):.1%}",
            "Of priority-review images, how many had a pneumonia label?",
        ),
        (
            "Accuracy",
            f"({tp} + {tn}) / {total}",
            f"{float(result['accuracy']):.1%}",
            "What share of all routes matched the retrospective labels?",
        ),
        (
            "Balanced accuracy",
            "(sensitivity + specificity) / 2",
            f"{float(result['balanced_accuracy']):.1%}",
            "How well did the policy treat both labels with equal weight?",
        ),
        (
            "Priority-review share (workload)",
            f"({tp} + {fp}) / {total}",
            f"{float(result['review_rate']):.1%}",
            "Of all test images, how many entered priority review?",
        ),
        (
            "ROC AUC",
            "ranking across all cutoffs",
            f"{float(result['roc_auc']):.3f}",
            "How well did scores rank pneumonia labels above normal labels?",
        ),
        (
            "Average precision",
            "precision-recall across cutoffs",
            f"{float(result['average_precision']):.3f}",
            "How strong was positive-class retrieval across possible cutoffs?",
        ),
    ]
    return pd.DataFrame(rows, columns=["Metric", "Calculation", "Measured value", "Question answered"])