"""Export and verify the narrow artifact contract consumed by the credit API.

Five files leave the notebook, and nothing else:

- ``model.joblib``            the full sklearn Pipeline (feature builder + model)
- ``model_card.json``         intended use, provenance, measured results, limits
- ``evaluation.json``         every table the governance view needs
- ``operating_policy.json``   the expected-cost rule, parameters, and fallback
- ``sample_manifest.parquet`` ~60 held-out test accounts spanning both routes
"""

from __future__ import annotations

import json
import platform
from datetime import datetime, timezone
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
import shap
import sklearn

from . import config, data, explain, features, metrics


def build_manifest(
    test_df: pd.DataFrame,
    X_test: np.ndarray,
    probabilities: np.ndarray,
    flags: np.ndarray,
    explainer: "shap.TreeExplainer",
) -> pd.DataFrame:
    """Select ~60 test accounts spanning both routes, with reason codes.

    Deterministic selection: the flagged accounts are taken evenly across the
    flagged probability ordering (top risk down to the borderline flag), and
    the safe accounts evenly across the expected-cost ordering of everything
    not flagged (from nearly-flagged down to clearly safe).
    """
    flags = np.asarray(flags, bool)
    expo = metrics.exposure(test_df)
    expected_cost = probabilities * expo * config.LOSS_GIVEN_DEFAULT

    flagged_positions = np.where(flags)[0]
    flagged_positions = flagged_positions[np.argsort(-probabilities[flagged_positions])]
    keep_flagged = flagged_positions[
        np.unique(np.linspace(0, len(flagged_positions) - 1, config.MANIFEST_FLAGGED).round().astype(int))
    ]

    safe_positions = np.where(~flags)[0]
    safe_positions = safe_positions[np.argsort(-expected_cost[safe_positions])]
    n_safe = config.MANIFEST_TOTAL - len(keep_flagged)
    keep_safe = safe_positions[
        np.unique(np.linspace(0, len(safe_positions) - 1, n_safe).round().astype(int))
    ]

    keep = np.concatenate([keep_flagged, keep_safe])
    keep = keep[np.argsort(-probabilities[keep])]

    contributions = explain.shap_matrix(explainer, X_test[keep])
    reasons = [
        json.dumps(explain.top_reasons(contributions[row], X_test[keep][row]))
        for row in range(len(keep))
    ]

    subset = test_df.iloc[keep]
    manifest = pd.DataFrame({"account_id": subset["ID"].to_numpy()})
    for column_index, name in enumerate(features.ENGINEERED):
        manifest[name] = X_test[keep, column_index]
    for raw in ("LIMIT_BAL", "BILL_AMT1", "PAY_0", "PAY_AMT1"):
        manifest[raw] = subset[raw].to_numpy()
    manifest["probability"] = probabilities[keep]
    manifest["route"] = np.where(flags[keep], config.ROUTE_FLAGGED, config.ROUTE_SAFE)
    manifest["reasons"] = reasons
    manifest["actual_outcome"] = subset[config.TARGET].to_numpy()
    # Withheld demographics, exported ONLY for the governance audit view.
    manifest["audit_sex"] = subset["SEX"].map(config.SEX_LABELS).to_numpy()
    manifest["audit_age_band"] = data.age_band(subset["AGE"]).astype(str).to_numpy()
    return manifest.reset_index(drop=True)


def _rounded(records: list[dict]) -> list[dict]:
    return [
        {
            key: (round(value, 4) if isinstance(value, float) else value)
            for key, value in record.items()
        }
        for record in records
    ]


def assemble_evidence(
    splits: dict[str, pd.DataFrame],
    leaderboard: pd.DataFrame,
    calibration_table: pd.DataFrame,
    sweep: pd.DataFrame,
    val_policy: dict,
    val_confusion: dict,
    val_review_everybody_NT: float,
    fairness: dict,
    audit_sex: pd.DataFrame,
    audit_age: pd.DataFrame,
    test_metrics: dict,
    test_policy: dict,
    test_confusion: dict,
    test_review_everybody_NT: float,
) -> dict:
    """The complete ``evaluation.json`` payload, in one place."""
    return {
        "split_counts": {
            name: {"n": int(len(part)), "default_rate": round(float(part[config.TARGET].mean()), 4)}
            for name, part in splits.items()
        },
        "validation_leaderboard": _rounded(leaderboard.to_dict("records")),
        "calibration_table": _rounded(calibration_table.to_dict("records")),
        "policy_sweep": _rounded(sweep.to_dict("records")),
        "chosen_policy_validation": {
            **_rounded([val_policy])[0],
            "confusion": val_confusion,
            "baselines_NT": {
                "review_nobody": 0,
                "review_everybody": round(float(val_review_everybody_NT)),
            },
        },
        "fairness": {
            "auc_without_protected": round(float(fairness["auc_without"]), 4),
            "auc_with_protected": round(float(fairness["auc_with"]), 4),
            "delta_auc": round(float(fairness["auc_with"] - fairness["auc_without"]), 4),
            "slice_audit": {
                "sex": _rounded(audit_sex.to_dict("records")),
                "age_band": _rounded(audit_age.to_dict("records")),
            },
            "note": (
                "Slices computed from withheld demographic columns the model never saw. "
                "Exclusion is not proof of fairness; this audit is the check."
            ),
        },
        "test_frozen": {
            "auc": round(float(test_metrics["auc"]), 4),
            "pr_auc": round(float(test_metrics["pr_auc"]), 4),
            "brier": round(float(test_metrics["brier"]), 4),
            **_rounded([test_policy])[0],
            "confusion": test_confusion,
            "baselines_NT": {
                "review_nobody": 0,
                "review_everybody": round(float(test_review_everybody_NT)),
            },
        },
    }


def export(
    pipeline,
    evidence: dict,
    manifest: pd.DataFrame,
    artifact_dir: Path = config.ARTIFACT_DIR,
) -> dict[str, str]:
    """Write the five artifacts. ``evidence`` is assembled by the notebook."""
    artifact_dir.mkdir(parents=True, exist_ok=True)
    model_path = artifact_dir / "model.joblib"
    card_path = artifact_dir / "model_card.json"
    policy_path = artifact_dir / "operating_policy.json"
    evaluation_path = artifact_dir / "evaluation.json"
    manifest_path = artifact_dir / "sample_manifest.parquet"

    joblib.dump(pipeline, model_path)
    manifest.to_parquet(manifest_path, index=False, compression="zstd")

    policy = {
        "name": "Expected-cost review policy",
        "rule": config.POLICY_RULE,
        "parameters": {
            "loss_given_default": config.LOSS_GIVEN_DEFAULT,
            "review_cost_NT": config.REVIEW_COST_NT,
            "currency": "NT$ (New Taiwan dollars)",
            "note": "All dollar parameters are synthetic classroom assumptions, not measured bank costs.",
        },
        "exposure": config.EXPOSURE_DEFINITION,
        "selected_on": "validation split only; the test split was scored once after freezing",
        "routes": {
            config.ROUTE_FLAGGED: "A credit analyst reviews the account and chooses the intervention.",
            config.ROUTE_SAFE: "No review this month; the account stays in ordinary monitoring.",
        },
        "fallback": (
            "An account with missing fields or codes outside the documented ranges is "
            "excluded from scoring and logged for manual data review. It is never silently scored."
        ),
        "boundary": (
            "A score is not a default determination; the analyst decides. The model never "
            "contacts a customer, never changes a limit, and never labels anyone a defaulter."
        ),
    }
    policy_path.write_text(json.dumps(policy, indent=2))
    evaluation_path.write_text(json.dumps(evidence, indent=2))

    created = datetime.now(timezone.utc).isoformat(timespec="seconds")
    card = {
        "model_name": "Credit-account review prioritization model",
        "model_version": created,
        "created_utc": created,
        "framework": f"scikit-learn {sklearn.__version__}",
        "packaging": "joblib Pipeline: creditlab.features.build_features -> HistGradientBoostingClassifier",
        "estimator": f"HistGradientBoostingClassifier(random_state={config.RANDOM_STATE}), library defaults, no calibration wrapper",
        "features": config.FEATURE_DISPLAY_NAMES,
        "protected_attributes_excluded": {
            "columns": config.PROTECTED_ATTRIBUTES,
            "reason": (
                "US fair-lending law (ECOA / Regulation B) restricts using these in a credit "
                "decision. They are exported only as audit columns, never as model inputs."
            ),
            "measured_cost_of_exclusion_auc": evidence["fairness"]["delta_auc"],
        },
        "reason_codes": {
            "mechanism": "shap.TreeExplainer on the deployed model",
            "output": f"up to {config.TOP_REASONS} risk-raising reasons in plain language",
            "note": "Borderline flags can have fewer than 3 risk-raising features.",
        },
        "dataset": {
            "name": config.DATASET_NAME,
            "uci_id": config.DATASET_UCI_ID,
            "url": config.DATASET_URL,
            "license": config.DATASET_LICENSE,
            "source_file_sha256": config.DATASET_XLS_SHA256,
            "citation": config.DATASET_CITATION,
            "population": config.DATASET_POPULATION,
            "split_counts": evidence["split_counts"],
        },
        "intended_use": (
            "Educational demonstration: rank existing packaged accounts for analyst review "
            "inside a monthly credit-risk workflow."
        ),
        "measured_on_untouched_test": evidence["test_frozen"],
        "operating_policy": policy,
        "limitations": [
            "One Taiwanese issuer, 2005, existing cardholders only; nothing here generalizes to other populations or eras.",
            "All accounts share one observation window, so out-of-time validation is impossible in this dataset. A real bank validates behavioral models out-of-time.",
            "All cost parameters (review cost, loss given default) are synthetic classroom assumptions.",
            "Excluding SEX, MARRIAGE, and AGE from the inputs does not guarantee fairness: behavior features can act as proxies. The exported slice audit is the check, not the exclusion.",
            "SHAP reason codes describe this model's arithmetic, not a customer's intent or circumstances.",
        ],
        "excluded_uses": [
            "Real credit decisions of any kind (approval, limits, pricing, collection)",
            "Scoring data from any other source or era",
            "Automated adverse action without an analyst and a compliance-reviewed notice",
        ],
        "environment": {
            "python": platform.python_version(),
            "numpy": np.__version__,
            "pandas": pd.__version__,
            "scikit_learn": sklearn.__version__,
            "shap": shap.__version__,
        },
    }
    card_path.write_text(json.dumps(card, indent=2))
    return {
        path.name: _formatted_size(path)
        for path in (model_path, card_path, policy_path, evaluation_path, manifest_path)
    }


def verify(artifact_dir: Path = config.ARTIFACT_DIR) -> dict[str, object]:
    """Reload the saved artifacts and prove score and route identity.

    Loads ``model.joblib`` and ``sample_manifest.parquet`` fresh from disk,
    re-scores the manifest's engineered features, and requires the stored
    probabilities to match BITWISE, and every route to match exactly.
    """
    pipeline = joblib.load(artifact_dir / "model.joblib")
    manifest = pd.read_parquet(artifact_dir / "sample_manifest.parquet")
    policy = json.loads((artifact_dir / "operating_policy.json").read_text())

    X = manifest[features.ENGINEERED].to_numpy(np.float64)
    reproduced = pipeline.named_steps["model"].predict_proba(X)[:, 1]
    stored = manifest["probability"].to_numpy(np.float64)
    bitwise_identical = reproduced.tobytes() == stored.tobytes()

    review_cost = float(policy["parameters"]["review_cost_NT"])
    lgd = float(policy["parameters"]["loss_given_default"])
    expo = np.clip(
        manifest["BILL_AMT1"].to_numpy(np.float64),
        0,
        manifest["LIMIT_BAL"].to_numpy(np.float64),
    )
    route = np.where(
        reproduced * expo * lgd > review_cost, config.ROUTE_FLAGGED, config.ROUTE_SAFE
    )
    route_changes = int((route != manifest["route"].to_numpy()).sum())

    if not bitwise_identical or route_changes:
        raise AssertionError("Reloaded artifacts do not reproduce the exported scores/routes.")
    return {
        "status": "verified",
        "samples": int(len(manifest)),
        "probabilities_bitwise_identical": bitwise_identical,
        "route_changes": route_changes,
    }


def _formatted_size(path: Path) -> str:
    size = path.stat().st_size
    return f"{size / 1e6:.1f} MB" if size >= 1e6 else f"{size / 1e3:.0f} KB"
