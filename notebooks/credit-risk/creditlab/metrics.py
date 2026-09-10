"""Ranking metrics, the reliability table, and the expected-cost policy math.

The policy arithmetic is copied from the spike unchanged: flag an account when
``p(default) x exposure x LGD > review_cost``, where exposure is BILL_AMT1
clipped to [0, LIMIT_BAL]. Reviewing an account that would have defaulted is
assumed to prevent its loss (exposure x LGD); every review costs review_cost.
All dollar values are synthetic classroom assumptions in NT$.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
from sklearn.metrics import average_precision_score, brier_score_loss, roc_auc_score

from . import config


# ── Ranking and probability-quality metrics ─────────────────────────────────

def ranking_metrics(y: np.ndarray, p: np.ndarray) -> dict[str, float]:
    """AUC, PR-AUC, and Brier score for one set of probabilities."""
    return {
        "auc": float(roc_auc_score(y, p)),
        "pr_auc": float(average_precision_score(y, p)),
        "brier": float(brier_score_loss(y, p)),
    }


def reliability_table(y: np.ndarray, p: np.ndarray, bins: int = 10) -> pd.DataFrame:
    """10-bin comparison of mean predicted probability vs observed default rate."""
    edges = np.linspace(0, 1, bins + 1)
    index = np.clip(np.digitize(p, edges[1:-1]), 0, bins - 1)
    rows = []
    for b in range(bins):
        mask = index == b
        rows.append(
            {
                "Predicted probability bin": f"{edges[b]:.1f}-{edges[b + 1]:.1f}",
                "Accounts": int(mask.sum()),
                "Mean predicted": float(p[mask].mean()) if mask.any() else np.nan,
                "Observed default rate": float(y[mask].mean()) if mask.any() else np.nan,
            }
        )
    return pd.DataFrame(rows)


# ── The expected-cost operating policy ──────────────────────────────────────

def exposure(df: pd.DataFrame) -> np.ndarray:
    """Money at risk if this account defaults: BILL_AMT1 clipped to [0, LIMIT_BAL]."""
    return np.clip(
        df["BILL_AMT1"].to_numpy(np.float64),
        0,
        df["LIMIT_BAL"].to_numpy(np.float64),
    )


def policy_flags(p: np.ndarray, expo: np.ndarray, review_cost: float) -> np.ndarray:
    """Boolean flag per account under the expected-cost rule."""
    return p * expo * config.LOSS_GIVEN_DEFAULT > review_cost


def policy_eval(
    p: np.ndarray, y: np.ndarray, expo: np.ndarray, review_cost: float
) -> dict[str, float | int]:
    """Flag counts, precision, recall, and net savings at one review cost."""
    flag = policy_flags(p, expo, review_cost)
    n_flagged = int(flag.sum())
    precision = float(y[flag].mean()) if n_flagged else 0.0
    recall = float(y[flag].sum() / y.sum()) if n_flagged else 0.0
    savings = float((y[flag] * expo[flag] * config.LOSS_GIVEN_DEFAULT - review_cost).sum())
    return {
        "review_cost_NT": int(review_cost),
        "flagged": n_flagged,
        "flagged_share": n_flagged / len(y),
        "precision": precision,
        "recall": recall,
        "net_savings_NT": round(savings),
    }


def policy_sweep(
    p: np.ndarray,
    y: np.ndarray,
    expo: np.ndarray,
    review_costs: list[int] | None = None,
) -> pd.DataFrame:
    """The validation sweep over candidate review costs."""
    costs = review_costs if review_costs is not None else config.REVIEW_COST_SWEEP_NT
    return pd.DataFrame([policy_eval(p, y, expo, cost) for cost in costs])


def review_everybody_savings(y: np.ndarray, expo: np.ndarray, review_cost: float) -> float:
    """Net savings of reviewing every account (no model needed)."""
    return round(float((y * expo * config.LOSS_GIVEN_DEFAULT - review_cost).sum()))


def confusion(flag: np.ndarray, y: np.ndarray) -> dict[str, int]:
    """Flag-vs-default counts: TP, FP, FN, TN."""
    flag = np.asarray(flag, bool)
    y = np.asarray(y)
    return {
        "TP": int((flag & (y == 1)).sum()),
        "FP": int((flag & (y == 0)).sum()),
        "FN": int((~flag & (y == 1)).sum()),
        "TN": int((~flag & (y == 0)).sum()),
    }


def confusion_table(counts: dict[str, int]) -> pd.DataFrame:
    """Confusion counts as a 2x2 display table (rows = later outcome)."""
    return pd.DataFrame(
        {
            "Flagged for review": [counts["TP"], counts["FP"]],
            "Not flagged": [counts["FN"], counts["TN"]],
        },
        index=["Later missed the payment", "Later paid"],
    )


# ── Fairness slice audit (computed from withheld columns) ───────────────────

def slice_audit(
    frame: pd.DataFrame, p: np.ndarray, flag: np.ndarray, group: pd.Series, group_name: str
) -> pd.DataFrame:
    """Score and flag behavior by demographic group the model never saw."""
    audit = pd.DataFrame(
        {
            group_name: group.to_numpy(),
            "p": p,
            "flag": np.asarray(flag, bool),
            "y": frame[config.TARGET].to_numpy(),
        }
    )
    grouped = audit.groupby(group_name, observed=True)
    out = grouped.agg(
        accounts=("y", "size"),
        mean_score=("p", "mean"),
        flagged_share=("flag", "mean"),
        actual_default_rate=("y", "mean"),
    ).reset_index()
    return out
