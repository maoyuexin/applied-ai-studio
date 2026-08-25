"""The handoff: what leaves this notebook and becomes a running service.

Four artefacts, and the contract between them is deliberately narrow:

    model.joblib         the selected pipeline, exactly as it was scored here
    mlflow_model/        the same pipeline in a standard serving package
    model_card.json      what it is, how it was chosen, and what it measured
    test_stream.parquet  the held-out period, already engineered, with labels

The scoring service loads the first, renders the second, and replays the third.
It does not reimplement a feature, which is the whole point of `features.py`
being a shared module rather than a notebook cell.
"""

from __future__ import annotations

import json
import shutil
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

from . import config, features

SKOPS_TRUSTED_TYPES = [
    "imblearn.pipeline.Pipeline",
    "imblearn.under_sampling._prototype_selection._random_under_sampler.RandomUnderSampler",
]

# Everything the scorer needs, plus the fields a UI has to show a human. Derived
# from the feature module rather than restated, so adding a feature cannot
# silently leave the served stream one column short.
DISPLAY_COLUMNS = [
    "trans_num", "cc_num", "trans_date_trans_time", "merchant", "city", "state",
]
STREAM_COLUMNS = (
    DISPLAY_COLUMNS
    + features.NUMERIC_FEATURES
    + features.CATEGORICAL_FEATURES
    + ["is_fraud"]
)


def export(
    model,
    model_name: str,
    leaderboard: pd.DataFrame,
    bakeoff: pd.DataFrame,
    balancing_treatment: str,
    result: dict,
    feature_columns: list[str],
    test_frame: pd.DataFrame,
    selection_rationale: str,
    artifact_dir: Path = config.ARTIFACT_DIR,
) -> dict[str, str]:
    """Write the four artefacts and return their sizes."""
    import imblearn
    import joblib
    import mlflow
    import mlflow.sklearn
    import numpy as np
    import sklearn
    import skops
    from mlflow.models import infer_signature

    artifact_dir.mkdir(parents=True, exist_ok=True)
    model_path = artifact_dir / "model.joblib"
    mlflow_path = artifact_dir / "mlflow_model"
    card_path = artifact_dir / "model_card.json"
    stream_path = artifact_dir / "test_stream.parquet"

    joblib.dump(model, model_path, compress=3)

    card = {
        "model_name": model_name,
        "created_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "sklearn_version": sklearn.__version__,
        "balancing_treatment": balancing_treatment,
        "selection_rationale": selection_rationale,
        "dataset": {
            "name": config.DATASET_NAME,
            "generator": config.DATASET_GENERATOR,
            "seed": config.DATASET_SEED,
            "customers": config.DATASET_CUSTOMERS,
        },
        "windows": {
            "train": [str(config.TRAIN_START.date()), str(config.TRAIN_END.date())],
            "test": [str(config.TEST_START.date()), str(config.TEST_END.date())],
            "as_of": str(config.AS_OF_DATE.date()),
            "label_lag_days": config.LABEL_LAG_DAYS,
        },
        "operating_point": {
            "review_budget": config.REVIEW_BUDGET,
            "threshold": result["threshold"],
            "review_minutes_per_txn": config.REVIEW_MINUTES_PER_TXN,
        },
        "measured_on_holdout": {
            key: result[key]
            for key in ("tp", "fp", "fn", "tn", "precision", "recall", "f1",
                        "accuracy", "review_hours", "dollars_caught", "dollars_missed")
            if key in result
        },
        "feature_columns": list(feature_columns),
        "leaderboard": json.loads(leaderboard.to_json(orient="records")),
        "balancing_bakeoff": json.loads(bakeoff.to_json(orient="records")),
    }
    card_path.write_text(json.dumps(card, indent=2))

    available = [c for c in STREAM_COLUMNS if c in test_frame.columns]
    test_frame[available].to_parquet(stream_path, compression="zstd", index=False)

    # MLflow provides a framework-neutral serving contract while skops limits
    # deserialization to the two expected imbalanced-learn pipeline classes.
    example, _ = features.feature_matrix(test_frame.head(100))
    example = example.reindex(columns=feature_columns, fill_value=0.0).astype(float)
    probabilities = np.asarray(model.predict_proba(example), dtype=float)
    shutil.rmtree(mlflow_path, ignore_errors=True)
    mlflow.sklearn.save_model(
        sk_model=model,
        path=mlflow_path,
        signature=infer_signature(example, probabilities),
        input_example=example.head(3),
        pip_requirements=[
            f"imbalanced-learn=={imblearn.__version__}",
            f"mlflow-skinny=={mlflow.__version__}",
            f"numpy=={np.__version__}",
            f"pandas=={pd.__version__}",
            f"scikit-learn=={sklearn.__version__}",
            f"skops=={skops.__version__}",
        ],
        metadata={
            "model_name": model_name,
            "threshold": float(result["threshold"]),
            "review_budget": float(config.REVIEW_BUDGET),
        },
        pyfunc_predict_fn="predict_proba",
        skops_trusted_types=SKOPS_TRUSTED_TYPES,
    )

    def formatted_size(path: Path) -> str:
        size = (
            path.stat().st_size
            if path.is_file()
            else sum(item.stat().st_size for item in path.rglob("*") if item.is_file())
        )
        return f"{size / 1e6:.1f} MB" if size >= 1e6 else f"{size / 1e3:.0f} KB"

    return {
        path.name: formatted_size(path)
        for path in (model_path, mlflow_path, card_path, stream_path)
    }


def verify(artifact_dir: Path = config.ARTIFACT_DIR) -> dict:
    """Reload the artefacts and re-score the stream.

    Catches training/serving skew: if the reloaded model does not reproduce the
    numbers in its own card, something in the handoff is broken and it is far
    better to find out here than in front of a room.
    """
    import joblib
    import mlflow.pyfunc
    import numpy as np

    from . import metrics

    model = joblib.load(artifact_dir / "model.joblib")
    mlflow_model = mlflow.pyfunc.load_model(artifact_dir / "mlflow_model")
    card = json.loads((artifact_dir / "model_card.json").read_text())
    stream = pd.read_parquet(artifact_dir / "test_stream.parquet")

    x, y = features.feature_matrix(stream)
    x = x.reindex(columns=card["feature_columns"], fill_value=0.0)

    proba = model.predict_proba(x)
    scores = proba[:, 1] if proba.ndim == 2 else proba.ravel()
    mlflow_proba = np.asarray(mlflow_model.predict(x.astype(float)), dtype=float)
    mlflow_scores = mlflow_proba[:, 1] if mlflow_proba.ndim == 2 else mlflow_proba.ravel()
    reproduced = metrics.evaluate_at_budget(
        y.to_numpy(), scores, stream["amt"].to_numpy(), card["operating_point"]["review_budget"]
    )
    mlflow_reproduced = metrics.evaluate_at_budget(
        y.to_numpy(), mlflow_scores, stream["amt"].to_numpy(), card["operating_point"]["review_budget"]
    )

    claimed = card["measured_on_holdout"]
    drift = {k: reproduced[k] - claimed[k] for k in ("precision", "recall") if k in claimed}
    threshold = float(card["operating_point"]["threshold"])
    return {
        "claimed": claimed,
        "reproduced": reproduced,
        "mlflow_reproduced": mlflow_reproduced,
        "drift": drift,
        "mlflow_max_probability_delta": float(np.max(np.abs(scores - mlflow_scores))),
        "mlflow_decision_changes": int(
            np.count_nonzero((scores >= threshold) != (mlflow_scores >= threshold))
        ),
    }
