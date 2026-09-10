"""Feature engineering frozen by the Module 4 spike.

Kept in its own module because the joblib-exported pipeline stores a reference
to ``creditlab.features.build_features`` (pickle saves the reference, not a
copy), so the service that reloads ``model.joblib`` imports this exact code.
Do not change the feature definitions or their order without re-running the
spike evidence: the exported model, the SHAP reason codes, and the sample
manifest all rely on this order.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

PAY_COLS = ["PAY_0", "PAY_2", "PAY_3", "PAY_4", "PAY_5", "PAY_6"]
BILL_COLS = [f"BILL_AMT{i}" for i in range(1, 7)]
PAYAMT_COLS = [f"PAY_AMT{i}" for i in range(1, 7)]

# Engineered feature order (must stay stable: pipeline + reason codes rely on it)
ENGINEERED = [
    "months_late_now",
    "worst_delay_6m",
    "num_late_months_6m",
    "utilization",
    "payment_ratio_6m",
    "bill_trend_6m",
    "credit_limit",
]


def consolidate_codes(df: pd.DataFrame) -> pd.DataFrame:
    """Map undocumented EDUCATION/MARRIAGE codes to 'other', and disclose it.

    The codebook defines EDUCATION 1-4 and MARRIAGE 1-3, but the file also
    contains EDUCATION {0, 5, 6} (345 rows) and MARRIAGE {0} (54 rows).
    Standard practice: collapse undocumented codes into the documented
    'other' category rather than guessing what they meant.
    """
    out = df.copy()
    out["EDUCATION"] = out["EDUCATION"].replace({0: 4, 5: 4, 6: 4})  # 4 = other
    out["MARRIAGE"] = out["MARRIAGE"].replace({0: 3})  # 3 = other
    return out


def build_features(df: pd.DataFrame) -> np.ndarray:
    """Raw account dataframe (original column names) -> engineered matrix.

    PAY_* code policy: -2 (no consumption), -1 (paid in full) and 0 (revolving
    credit used, minimum paid) are all treated as NOT delinquent -> clipped to
    0. Only values >= 1 (months of payment delay) count as delinquency. The
    three non-positive codes describe *how* the customer paid on time, not
    lateness; collapsing them makes "months behind" literally true in
    reason-code text.
    """
    pay = df[PAY_COLS].to_numpy(dtype=np.float64)
    bills = df[BILL_COLS].to_numpy(dtype=np.float64)
    payamt = df[PAYAMT_COLS].to_numpy(dtype=np.float64)
    limit = df["LIMIT_BAL"].to_numpy(dtype=np.float64)

    pay_clipped = np.clip(pay, 0, None)
    months_late_now = pay_clipped[:, 0]
    worst_delay_6m = pay_clipped.max(axis=1)
    num_late_months_6m = (pay >= 1).sum(axis=1).astype(np.float64)

    utilization = np.clip(bills[:, 0] / limit, 0.0, 2.0)

    billed_pos = np.clip(bills, 0, None).sum(axis=1)
    paid = payamt.sum(axis=1)
    payment_ratio_6m = np.where(billed_pos > 0, paid / np.where(billed_pos > 0, billed_pos, 1.0), 1.0)
    payment_ratio_6m = np.clip(payment_ratio_6m, 0.0, 2.0)

    bill_trend_6m = np.clip((bills[:, 0] - bills[:, 5]) / limit, -2.0, 2.0)

    X = np.column_stack([
        months_late_now,
        worst_delay_6m,
        num_late_months_6m,
        utilization,
        payment_ratio_6m,
        bill_trend_6m,
        limit,
    ])
    return X


def feature_frame(df: pd.DataFrame) -> pd.DataFrame:
    """The engineered matrix with named columns, for EDA tables and manifests."""
    return pd.DataFrame(build_features(df), columns=ENGINEERED, index=df.index)
