"""Model candidates, the class-balancing bake-off, and the sweep.

Two of the six candidates are not machine learning at all. That is deliberate:
"never fraud" is what makes the accuracy trap visible, and a written amount rule
is what makes "is this actually an AI problem?" an empirical question rather than
an assumption.
"""

from __future__ import annotations

import time

import numpy as np
import pandas as pd
from imblearn.over_sampling import RandomOverSampler, SMOTE
from imblearn.pipeline import Pipeline as ImbPipeline
from imblearn.under_sampling import RandomUnderSampler
from sklearn.base import BaseEstimator, ClassifierMixin
from sklearn.dummy import DummyClassifier
from sklearn.ensemble import HistGradientBoostingClassifier, RandomForestClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import TimeSeriesSplit
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.tree import DecisionTreeClassifier

from . import config, metrics


class AmountRule(BaseEstimator, ClassifierMixin):
    """"Flag anything over $X." A written rule, not a learned model.

    Included so the room can see what the rule actually scores before anyone
    argues about whether the problem needs AI.
    """

    def __init__(self, amount_column: int = 0):
        self.amount_column = amount_column

    def fit(self, x, y=None):
        col = np.asarray(x)[:, self.amount_column].astype(float)
        self.scale_ = float(np.percentile(col, 99)) or 1.0
        self.classes_ = np.array([0, 1])
        return self

    def predict_proba(self, x):
        col = np.asarray(x)[:, self.amount_column].astype(float)
        p = np.clip(col / self.scale_, 0, 1)
        return np.column_stack([1 - p, p])

    def predict(self, x):
        return (self.predict_proba(x)[:, 1] >= 0.5).astype(int)


def candidate_models() -> dict[str, dict]:
    """The six candidates, with the honest note on what each costs to explain."""
    rs = config.RANDOM_STATE
    return {
        "Never fraud": {
            "estimator": DummyClassifier(strategy="constant", constant=0),
            "explainable": "Total",
            "learns": False,
        },
        "Amount rule": {
            "estimator": AmountRule(amount_column=0),
            "explainable": "Total",
            "learns": False,
        },
        "Logistic regression": {
            "estimator": Pipeline(
                [("scale", StandardScaler()),
                 ("clf", LogisticRegression(max_iter=2000, random_state=rs))]
            ),
            "explainable": "High",
            "learns": True,
        },
        "Decision tree": {
            "estimator": DecisionTreeClassifier(max_depth=4, random_state=rs),
            "explainable": "High",
            "learns": True,
        },
        "Random forest": {
            "estimator": RandomForestClassifier(
                n_estimators=200, min_samples_leaf=2, n_jobs=-1, random_state=rs
            ),
            "explainable": "Medium",
            "learns": True,
        },
        "Gradient boosting": {
            "estimator": HistGradientBoostingClassifier(
                max_iter=250, learning_rate=0.1, random_state=rs
            ),
            "explainable": "Medium",
            "learns": True,
        },
    }


def balancing_treatments(seed: int = config.RANDOM_STATE) -> dict[str, object]:
    """Five ways to handle a 0.5% positive class. `None` means "leave it alone"."""
    return {
        "None": None,
        "Class weight": "class_weight",
        "Random undersample": RandomUnderSampler(random_state=seed),
        "Random oversample": RandomOverSampler(random_state=seed),
        "SMOTE": SMOTE(random_state=seed, k_neighbors=5),
    }


def _with_class_weight(estimator):
    """Apply balanced class weights wherever the estimator supports them."""
    est = _clone_estimator(estimator)
    if isinstance(est, Pipeline):
        est.named_steps["clf"].set_params(class_weight="balanced")
    elif hasattr(est, "class_weight"):
        est.set_params(class_weight="balanced")
    return est


def _clone_estimator(estimator):
    from sklearn.base import clone

    return clone(estimator)


def build_pipeline(estimator, treatment) -> object:
    """Wrap an estimator in its balancing treatment.

    `imblearn.pipeline.Pipeline` -- never `sklearn.pipeline.Pipeline`. The
    imblearn version applies the sampler to training folds only. The sklearn one
    does not, and that one-word difference is the difference between an honest
    score and a fantasy.
    """
    if treatment is None:
        return _clone_estimator(estimator)
    if treatment == "class_weight":
        return _with_class_weight(estimator)
    return ImbPipeline(
        [("resample", treatment), ("model", _clone_estimator(estimator))]
    )


def _subsample(x: pd.DataFrame, y: pd.Series, max_rows: int, seed: int):
    """Keep the most recent rows. A random subsample would break the time order."""
    if max_rows is None or len(x) <= max_rows:
        return x, y
    return x.iloc[-max_rows:], y.iloc[-max_rows:]


def score_on(estimator, x) -> np.ndarray:
    proba = estimator.predict_proba(x)
    return proba[:, 1] if proba.ndim == 2 and proba.shape[1] > 1 else proba.ravel()


def run_balancing_bakeoff(
    estimator,
    x_train: pd.DataFrame,
    y_train: pd.Series,
    x_test: pd.DataFrame,
    y_test: pd.Series,
    amounts_test: np.ndarray,
    max_train_rows: int | None = 250_000,
    budget: float = config.REVIEW_BUDGET,
) -> pd.DataFrame:
    """One model family, five balancing treatments, one variable changed at a time."""
    xt, yt = _subsample(x_train, y_train, max_train_rows, config.RANDOM_STATE)

    rows = []
    for name, treatment in balancing_treatments().items():
        pipe = build_pipeline(estimator, treatment)
        started = time.time()
        pipe.fit(xt, yt)
        elapsed = time.time() - started

        result = metrics.evaluate_at_budget(
            y_test.to_numpy(), score_on(pipe, x_test), amounts_test, budget
        )
        rows.append(
            {
                "Treatment": name,
                "TP": result["tp"], "FP": result["fp"],
                "FN": result["fn"], "TN": result["tn"],
                "Precision": result["precision"],
                "Recall": result["recall"],
                "F1": result["f1"],
                "Accuracy": result["accuracy"],
                "$ caught": result["dollars_caught"],
                "$ missed": result["dollars_missed"],
                "Fit (s)": elapsed,
            }
        )
    return pd.DataFrame(rows).sort_values("Recall", ascending=False).reset_index(drop=True)


def leaked_smote_score(
    estimator,
    x: pd.DataFrame,
    y: pd.Series,
    max_rows: int | None = 120_000,
) -> dict[str, float]:
    """SMOTE applied *before* the split -- the number that looks magnificent.

    Synthetic minority points are interpolated between real training rows. Do this
    before splitting and some of those synthetic points land in the validation
    set, so the model is scored on data derived from data it trained on.

    Reported as average precision rather than a confusion matrix at the review
    budget, because resampling changes the class balance and a budget-based 2x2
    would no longer be comparable to the honest run. Threshold-free is the fair
    comparison here, and it is the one place in this notebook that needs one.
    """
    from sklearn.metrics import average_precision_score, roc_auc_score

    xs, ys = _subsample(x, y, max_rows, config.RANDOM_STATE)
    x_res, y_res = SMOTE(random_state=config.RANDOM_STATE).fit_resample(xs, ys)

    shuffled = np.random.default_rng(config.RANDOM_STATE).permutation(len(x_res))
    cut = int(len(shuffled) * 0.75)
    tr, te = shuffled[:cut], shuffled[cut:]

    model = _clone_estimator(estimator)
    model.fit(x_res.iloc[tr], y_res.iloc[tr])
    scores = score_on(model, x_res.iloc[te])
    truth = y_res.iloc[te]
    return {
        "average_precision": float(average_precision_score(truth, scores)),
        "roc_auc": float(roc_auc_score(truth, scores)),
        "positive_rate": float(truth.mean()),
        "rows": int(len(x_res)),
    }


def honest_smote_score(
    estimator,
    x_train: pd.DataFrame,
    y_train: pd.Series,
    x_test: pd.DataFrame,
    y_test: pd.Series,
    max_train_rows: int | None = 120_000,
) -> dict[str, float]:
    """The same technique, applied inside the pipeline so it only touches training folds."""
    from sklearn.metrics import average_precision_score, roc_auc_score

    xt, yt = _subsample(x_train, y_train, max_train_rows, config.RANDOM_STATE)
    pipe = build_pipeline(estimator, SMOTE(random_state=config.RANDOM_STATE))
    pipe.fit(xt, yt)
    scores = score_on(pipe, x_test)
    return {
        "average_precision": float(average_precision_score(y_test, scores)),
        "roc_auc": float(roc_auc_score(y_test, scores)),
        "positive_rate": float(y_test.mean()),
        "rows": int(len(xt)),
    }


def run_model_sweep(
    x_train: pd.DataFrame,
    y_train: pd.Series,
    x_test: pd.DataFrame,
    y_test: pd.Series,
    amounts_test: np.ndarray,
    treatment_name: str = "Class weight",
    max_train_rows: int | None = 250_000,
    budget: float = config.REVIEW_BUDGET,
) -> tuple[pd.DataFrame, dict]:
    """Six candidates, one balancing treatment held constant, all judged at the same budget."""
    xt, yt = _subsample(x_train, y_train, max_train_rows, config.RANDOM_STATE)
    treatment = balancing_treatments()[treatment_name]

    rows, fitted = [], {}
    for name, spec in candidate_models().items():
        # Balancing a rule or a constant is meaningless -- leave those alone.
        applied = treatment if spec["learns"] else None
        pipe = build_pipeline(spec["estimator"], applied)

        started = time.time()
        pipe.fit(xt, yt)
        elapsed = time.time() - started

        scores = score_on(pipe, x_test)
        result = metrics.evaluate_at_budget(y_test.to_numpy(), scores, amounts_test, budget)
        fitted[name] = {"model": pipe, "scores": scores, "result": result}

        rows.append(
            {
                "Model": name,
                "TP": result["tp"], "FP": result["fp"],
                "FN": result["fn"], "TN": result["tn"],
                "Precision": result["precision"],
                "Recall": result["recall"],
                "F1": result["f1"],
                "Accuracy": result["accuracy"],
                "$ caught": result["dollars_caught"],
                "$ missed": result["dollars_missed"],
                "Review hrs": result["review_hours"],
                "Fit (s)": elapsed,
                "Explainable": spec["explainable"],
            }
        )

    leaderboard = pd.DataFrame(rows).sort_values("Recall", ascending=False).reset_index(drop=True)
    return leaderboard, fitted


def time_series_cv(
    estimator,
    x: pd.DataFrame,
    y: pd.Series,
    n_splits: int = config.N_CV_SPLITS,
    budget: float = config.REVIEW_BUDGET,
    max_rows: int | None = 250_000,
) -> pd.DataFrame:
    """Cross-validation that respects the arrow of time.

    `TimeSeriesSplit`, not `KFold`: each fold trains on the past and validates on
    the future, which is the only arrangement that resembles production.
    """
    xs, ys = _subsample(x, y, max_rows, config.RANDOM_STATE)
    splitter = TimeSeriesSplit(n_splits=n_splits)

    rows = []
    for fold, (train_idx, val_idx) in enumerate(splitter.split(xs), start=1):
        model = _clone_estimator(estimator)
        model.fit(xs.iloc[train_idx], ys.iloc[train_idx])
        result = metrics.evaluate_at_budget(
            ys.iloc[val_idx].to_numpy(), score_on(model, xs.iloc[val_idx]), None, budget
        )
        rows.append(
            {
                "Fold": fold,
                "Train rows": len(train_idx),
                "Validate rows": len(val_idx),
                "Precision": result["precision"],
                "Recall": result["recall"],
                "F1": result["f1"],
            }
        )
    return pd.DataFrame(rows)


def permutation_importance_frame(
    model, x: pd.DataFrame, y: pd.Series, n_repeats: int = 3, top_n: int = 15
) -> pd.DataFrame:
    """Which columns the model actually leans on, measured by breaking them."""
    from sklearn.inspection import permutation_importance

    result = permutation_importance(
        model, x, y, n_repeats=n_repeats,
        random_state=config.RANDOM_STATE, scoring="average_precision", n_jobs=-1,
    )
    return (
        pd.DataFrame(
            {"Feature": x.columns,
             "Importance": result.importances_mean,
             "Std": result.importances_std}
        )
        .sort_values("Importance", ascending=False)
        .head(top_n)
        .reset_index(drop=True)
    )
