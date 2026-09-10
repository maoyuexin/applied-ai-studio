"""The detector, and the three fancier models it was measured against.

Four documented failures cannot train a supervised model - there is nothing to
learn a decision boundary from. So the question is not "what does a failure
look like" but "what does normal look like, and how far from it is this hour".
That is anomaly detection, and it is fit on the quiet months only.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from . import config


class RobustZDetector:
    """One-sided robust z-score over the six features, averaged.

    Fit: for each feature, take the MEDIAN of the training hours as 'normal'
    and the MAD (median absolute deviation, times 1.4826 so it is on the same
    scale as a standard deviation) as 'how much normal varies'.

    Score: for each hour, (value - median) / scale, flipped so that the
    direction that means trouble is always positive, clipped at zero so that a
    feature which is BETTER than normal contributes nothing, then averaged over
    the six. A score of 6 means the average feature sits six robust standard
    deviations into the failure direction.

    The whole fitted model is twelve numbers - six medians and six scales.
    """

    name = config.MODEL_TYPE

    def __init__(self, features: list[str] | None = None, one_sided: bool = True):
        self.features = list(features or config.MODEL_FEATURES)
        self.one_sided = one_sided
        self.median_: pd.Series | None = None
        self.scale_: pd.Series | None = None

    def fit(self, matrix: pd.DataFrame) -> "RobustZDetector":
        matrix = matrix[self.features]
        self.median_ = matrix.median()
        mad = (matrix - self.median_).abs().median() * config.MAD_CONSTANT
        sd = matrix.std()
        # A feature with zero spread in training would divide by zero; fall
        # back to the standard deviation, then to 1.0.
        self.scale_ = mad.where(mad > 1e-6, sd.where(sd > 1e-6, 1.0))
        return self

    def score_frame(self, matrix: pd.DataFrame) -> pd.DataFrame:
        """Per-feature contributions, before averaging. Used to say WHY."""
        matrix = matrix[self.features]
        z = (matrix - self.median_) / self.scale_
        if self.one_sided:
            sign = pd.Series({c: config.FEATURE_DIRECTION[c] for c in self.features})
            z = (z * sign).clip(lower=0.0)
        else:
            z = z.abs()
        return z

    def score(self, matrix: pd.DataFrame) -> pd.Series:
        return self.score_frame(matrix).mean(axis=1)

    def state(self) -> dict:
        """The twelve numbers, for the model card and for reading by eye."""
        return {
            "features": self.features,
            "one_sided": self.one_sided,
            "median": {k: float(v) for k, v in self.median_.items()},
            "scale": {k: float(v) for k, v in self.scale_.items()},
        }


def fit_detector(matrix: pd.DataFrame, training_window=None, one_sided: bool = True) -> RobustZDetector:
    """Fit on the training window only. Nothing after March is ever seen."""
    start, end = training_window or (config.TRAIN_START, config.TRAIN_END)
    training = matrix[(matrix.index >= start) & (matrix.index < end)]
    return RobustZDetector(one_sided=one_sided).fit(training)


def training_slice(matrix: pd.DataFrame) -> pd.DataFrame:
    return matrix[(matrix.index >= config.TRAIN_START) & (matrix.index < config.TRAIN_END)]


# ── The comparison models ───────────────────────────────────────────────────

def candidate_scores(matrix: pd.DataFrame) -> dict[str, pd.Series]:
    """Score the same hours with four model families, fit on the same window.

    Every candidate sees exactly the same six features and exactly the same
    training months, so the comparison is about the model and nothing else.
    """
    from sklearn.covariance import EllipticEnvelope
    from sklearn.decomposition import PCA
    from sklearn.ensemble import IsolationForest
    from sklearn.preprocessing import StandardScaler

    training = training_slice(matrix)
    scaler = StandardScaler().fit(training)
    z_train = scaler.transform(training)
    z_all = scaler.transform(matrix)

    scores: dict[str, pd.Series] = {}

    median = training.median()
    mad = (training - median).abs().median() * config.MAD_CONSTANT
    mad = mad.where(mad > 1e-6, training.std().where(training.std() > 1e-6, 1.0))
    robust = (matrix - median).abs() / mad
    scores["Robust z, mean of six"] = robust.mean(axis=1)
    scores["Robust z, worst of six"] = robust.max(axis=1)

    forest = IsolationForest(
        n_estimators=300, max_samples=256,
        random_state=config.RANDOM_STATE, contamination="auto",
    ).fit(z_train)
    scores["IsolationForest"] = pd.Series(-forest.score_samples(z_all), index=matrix.index)

    pca = PCA(n_components=3, random_state=config.RANDOM_STATE).fit(z_train)
    rebuilt = pca.inverse_transform(pca.transform(z_all))
    scores["PCA reconstruction error"] = pd.Series(((z_all - rebuilt) ** 2).sum(axis=1), index=matrix.index)

    envelope = EllipticEnvelope(support_fraction=0.9, random_state=config.RANDOM_STATE).fit(z_train)
    scores["Robust Mahalanobis"] = pd.Series(envelope.mahalanobis(z_all), index=matrix.index)

    return scores


def scaling_variants(matrix: pd.DataFrame) -> dict[str, pd.Series]:
    """Same features, same direction, different definitions of 'how far'.

    MAD keeps a wide band of usable thresholds. A standard deviation does not,
    because the compressor idles most nights: the spread it measures is
    dominated by the machine's normal on/off swing.
    """
    training = training_slice(matrix)
    sign = pd.Series({c: config.FEATURE_DIRECTION[c] for c in matrix.columns})
    mad = (training - training.median()).abs().median() * config.MAD_CONSTANT
    mad = mad.where(mad > 1e-6, training.std())
    variants = {
        "MAD scale (median center)": (((matrix - training.median()) / mad) * sign).clip(lower=0),
        "SD scale (mean center)": (((matrix - training.mean()) / training.std()) * sign).clip(lower=0),
        "SD scale (median center)": (((matrix - training.median()) / training.std()) * sign).clip(lower=0),
    }
    return {name: frame.mean(axis=1) for name, frame in variants.items()}


def rolling_baseline_score(matrix: pd.DataFrame, window_days: int = 14) -> pd.Series:
    """The mitigation: re-learn 'normal' from the last N days, every hour.

    ``shift(1)`` keeps the current hour out of its own baseline. This cuts
    false callouts sharply and is still rejected as an automatic default -
    see the measurement in Stage 4.
    """
    hours = f"{window_days * 24}h"
    center = matrix.rolling(hours, min_periods=72).median().shift(1)
    spread = (matrix - center).abs().rolling(hours, min_periods=72).median().shift(1) * config.MAD_CONSTANT
    spread = spread.where(spread > 1e-6, np.nan)
    sign = pd.Series({c: config.FEATURE_DIRECTION[c] for c in matrix.columns})
    return (((matrix - center) / spread) * sign).clip(lower=0).mean(axis=1)


def top_driver(frame: pd.DataFrame, stamp: pd.Timestamp) -> tuple[str, float]:
    """Which feature contributed most to one hour's score."""
    row = frame.loc[stamp]
    return str(row.idxmax()), round(float(row.max()), 1)
