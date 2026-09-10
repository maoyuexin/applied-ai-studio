"""Accuracy, the per-team table, the confusion matrix, and the routing policy.

The policy arithmetic is copied from the spike unchanged: the model's highest
team probability is its **confidence**. At or above 0.55 the complaint is
auto-routed to that team; below it, the complaint goes to a human triage queue.

Two rates carry different denominators throughout and are never mixed:

- **coverage** = auto-routed complaints / all complaints in the split
- **accuracy among auto-routed** = correct auto-routes / auto-routed complaints
"""

from __future__ import annotations

import numpy as np
import pandas as pd
from sklearn.metrics import accuracy_score, confusion_matrix, f1_score, precision_recall_fscore_support

from . import config


# ── Overall quality ─────────────────────────────────────────────────────────

def classification_scores(y_true, y_pred) -> dict[str, float]:
    """Accuracy and macro-F1 for one set of predictions."""
    return {
        "accuracy": float(accuracy_score(y_true, y_pred)),
        "macro_f1": float(f1_score(y_true, y_pred, average="macro", zero_division=0)),
    }


def per_team_table(y_true, y_pred) -> pd.DataFrame:
    """Precision, recall, F1, and support for each of the eight teams."""
    precision, recall, f1, support = precision_recall_fscore_support(
        y_true, y_pred, labels=config.TEAMS, zero_division=0
    )
    frame = pd.DataFrame(
        {
            "Team": config.TEAMS,
            "Precision": precision,
            "Recall": recall,
            "F1": f1,
            "Complaints in the split": support,
        }
    )
    macro = {
        "Team": "macro average",
        "Precision": precision.mean(),
        "Recall": recall.mean(),
        "F1": f1.mean(),
        "Complaints in the split": support.sum(),
    }
    return pd.concat([frame, pd.DataFrame([macro])], ignore_index=True)


def confusion_frame(y_true, y_pred) -> pd.DataFrame:
    """Counts of true team (rows) against predicted team (columns)."""
    matrix = confusion_matrix(y_true, y_pred, labels=config.TEAMS)
    return pd.DataFrame(matrix, index=config.TEAMS, columns=config.TEAMS)


def top_confusions(y_true, y_pred, top: int = 5) -> pd.DataFrame:
    """The largest off-diagonal cells, in plain words."""
    frame = confusion_frame(y_true, y_pred)
    records = []
    for true_team in config.TEAMS:
        for predicted_team in config.TEAMS:
            if true_team == predicted_team:
                continue
            count = int(frame.loc[true_team, predicted_team])
            if count:
                records.append(
                    {
                        "Belonged to": true_team,
                        "Model sent it to": predicted_team,
                        "Complaints": count,
                        "Share of that team's complaints": count / frame.loc[true_team].sum(),
                    }
                )
    return (
        pd.DataFrame(records)
        .sort_values("Complaints", ascending=False)
        .head(top)
        .reset_index(drop=True)
    )


# ── The confidence policy ───────────────────────────────────────────────────

def routes(confidence: np.ndarray, threshold: float = config.CONFIDENCE_THRESHOLD) -> np.ndarray:
    """auto_route above the threshold, human_triage below it."""
    return np.where(
        np.asarray(confidence) >= threshold, config.ROUTE_AUTO, config.ROUTE_TRIAGE
    )


def policy_eval(
    y_true,
    y_pred,
    confidence: np.ndarray,
    threshold: float = config.CONFIDENCE_THRESHOLD,
) -> dict[str, float | int]:
    """Coverage, accuracy among auto-routed, and the triage workload."""
    y_true = np.asarray(y_true)
    y_pred = np.asarray(y_pred)
    auto = np.asarray(confidence) >= threshold
    correct = y_true == y_pred
    return {
        "threshold": round(float(threshold), 3),
        "complaints": int(len(y_true)),
        "auto_routed": int(auto.sum()),
        "coverage": float(auto.mean()),
        "accuracy_among_auto_routed": float(correct[auto].mean()) if auto.any() else 0.0,
        "triage_rows": int((~auto).sum()),
        "triage_share": float((~auto).mean()),
        "accuracy_among_triage": float(correct[~auto].mean()) if (~auto).any() else 0.0,
        "overall_accuracy": float(correct.mean()),
    }


def threshold_sweep(
    y_true, y_pred, confidence: np.ndarray, thresholds: list[float] | None = None
) -> pd.DataFrame:
    """The validation sweep the 0.55 choice was read off."""
    grid = config.THRESHOLD_SWEEP if thresholds is None else thresholds
    return pd.DataFrame([policy_eval(y_true, y_pred, confidence, t) for t in grid])


def confidence_bands(y_true, y_pred, confidence: np.ndarray) -> pd.DataFrame:
    """Accuracy inside fixed confidence bands: is the confidence honest?"""
    y_true = np.asarray(y_true)
    y_pred = np.asarray(y_pred)
    edges = [0.0, 0.4, 0.55, 0.7, 0.85, 1.01]
    labels = ["under 0.40", "0.40 - 0.55", "0.55 - 0.70", "0.70 - 0.85", "0.85 and up"]
    band = pd.cut(confidence, bins=edges, labels=labels, right=False)
    frame = pd.DataFrame({"band": band, "correct": y_true == y_pred})
    grouped = frame.groupby("band", observed=False)["correct"].agg(["size", "mean"])
    grouped = grouped.reindex(labels)
    return pd.DataFrame(
        {
            "Confidence band": labels,
            "Complaints": grouped["size"].to_numpy(),
            "Share of the split": (grouped["size"] / len(frame)).to_numpy(),
            "Accuracy in the band": grouped["mean"].to_numpy(),
        }
    )
