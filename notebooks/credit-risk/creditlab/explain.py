"""SHAP reason codes in adverse-action-ready plain language (spike-frozen).

The mechanism is ``shap.TreeExplainer`` on the deployed gradient-boosting
model. SHAP values here are log-odds contributions; only their sign and
ranking feed the reason text, which is what an adverse-action notice needs.
A borderline flag can have fewer than 3 risk-raising features, so every
function emits *up to* ``config.TOP_REASONS`` reasons, never padded.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import shap

from . import config, features


def build_explainer(model) -> shap.TreeExplainer:
    """TreeExplainer on the fitted HistGradientBoosting model."""
    return shap.TreeExplainer(model)


def shap_matrix(explainer: shap.TreeExplainer, X: np.ndarray) -> np.ndarray:
    """Per-account, per-feature contributions (positive pushes risk up)."""
    values = explainer.shap_values(X)
    if isinstance(values, list):  # some shap versions return [class0, class1]
        values = values[1]
    return np.asarray(values)


def reason_text(feature: str, value: float) -> str:
    """Plain-language reason for one feature pushing risk UP."""
    if feature == "months_late_now":
        if value >= 1:
            return f"is currently {value:.0f} month{'s' if value >= 2 else ''} behind on payments"
        return "recent payment status raises risk"
    if feature == "worst_delay_6m":
        if value >= 1:
            return f"was up to {value:.0f} month{'s' if value >= 2 else ''} behind on payments in the last 6 months"
        return "past payment delays raise risk"
    if feature == "num_late_months_6m":
        if value >= 1:
            return f"paid late in {value:.0f} of the last 6 months"
        return "pattern of late months raises risk"
    if feature == "utilization":
        return f"is using {value * 100:.0f}% of the credit limit"
    if feature == "payment_ratio_6m":
        return f"paid only {value * 100:.0f}% of billed amounts over the last 6 months"
    if feature == "bill_trend_6m":
        if value > 0:
            return f"balance grew by {value * 100:.0f}% of the credit limit over 6 months"
        return "balance trend raises risk"
    if feature == "credit_limit":
        return f"credit limit of NT${value:,.0f} (lower limits go with higher risk)"
    return f"{feature} = {value:.2f}"


def top_reasons(contributions: np.ndarray, values: np.ndarray) -> list[dict]:
    """Up to 3 risk-raising reasons for ONE account, strongest first.

    Each reason carries the feature name, its display name, the direction
    ("raises risk"), and the SHAP contribution, ready for the app's JSON.
    """
    order = np.argsort(-contributions)[: config.TOP_REASONS]
    reasons = []
    for index in order:
        if contributions[index] <= 0:
            continue
        feature = features.ENGINEERED[index]
        reasons.append(
            {
                "feature": feature,
                "display_name": config.FEATURE_DISPLAY_NAMES[feature],
                "direction": "raises risk",
                "contribution": round(float(contributions[index]), 4),
                "text": reason_text(feature, float(values[index])),
            }
        )
    return reasons


def contribution_frame(contributions: np.ndarray, values: np.ndarray) -> pd.DataFrame:
    """All 7 contributions for ONE account, for the reason-code chart."""
    return pd.DataFrame(
        {
            "feature": features.ENGINEERED,
            "display_name": [config.FEATURE_DISPLAY_NAMES[f] for f in features.ENGINEERED],
            "value": values,
            "contribution": contributions,
        }
    ).sort_values("contribution")
