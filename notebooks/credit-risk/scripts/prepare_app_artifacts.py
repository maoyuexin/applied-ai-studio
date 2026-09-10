"""Run the full credit-risk workflow headlessly and export verified artifacts.

Same steps and same frozen decisions as the notebook (dataset -> split ->
candidates on validation -> expected-cost policy -> single frozen test scoring
-> export -> reload verification), so `npm run prepare:credit` reproduces the
exact files the notebook commits evidence for.
"""

from __future__ import annotations

import sys
from pathlib import Path

PROJECT_DIR = Path(__file__).resolve().parents[1]
if str(PROJECT_DIR) not in sys.path:
    sys.path.insert(0, str(PROJECT_DIR))

from creditlab import config, data, explain, features, handoff, metrics, models  # noqa: E402


def main() -> None:
    print("Loading committed accounts.parquet and splitting 60/20/20 (seed 42)...")
    accounts = data.load_accounts()
    splits = data.split_accounts(accounts)
    train_df, val_df, test_df = splits["train"], splits["validation"], splits["test"]
    y_train = train_df[config.TARGET].to_numpy()
    y_val = val_df[config.TARGET].to_numpy()
    y_test = test_df[config.TARGET].to_numpy()
    X_train, X_val = features.build_features(train_df), features.build_features(val_df)

    print("Fitting the compared models on the identical split...")
    baseline = models.majority_baseline(y_train, len(y_val))
    logistic = models.fit_logistic(X_train, y_train, X_val)
    boosted = models.fit_gradient_boosting(X_train, y_train, X_val)
    leaderboard = models.leaderboard([baseline, logistic, boosted], y_val)

    print("Validation policy work (calibration, sweep, fairness)...")
    calibration_table = metrics.reliability_table(y_val, boosted.val_probabilities)
    expo_val = metrics.exposure(val_df)
    sweep = metrics.policy_sweep(boosted.val_probabilities, y_val, expo_val)
    val_policy = metrics.policy_eval(
        boosted.val_probabilities, y_val, expo_val, config.REVIEW_COST_NT
    )
    val_flags = metrics.policy_flags(boosted.val_probabilities, expo_val, config.REVIEW_COST_NT)
    val_confusion = metrics.confusion(val_flags, y_val)

    with_protected = models.fit_gradient_boosting_with_protected(
        X_train, y_train, X_val, train_df, val_df
    )
    fairness = {
        "auc_without": metrics.ranking_metrics(y_val, boosted.val_probabilities)["auc"],
        "auc_with": metrics.ranking_metrics(y_val, with_protected.val_probabilities)["auc"],
    }
    audit_sex = metrics.slice_audit(
        val_df, boosted.val_probabilities, val_flags,
        val_df["SEX"].map(config.SEX_LABELS), "sex",
    )
    audit_age = metrics.slice_audit(
        val_df, boosted.val_probabilities, val_flags,
        data.age_band(val_df["AGE"]), "age_band",
    )

    print("Freezing the config and scoring the untouched test split once...")
    pipeline, fit_seconds = models.fit_final_pipeline(train_df, y_train)
    p_test = pipeline.predict_proba(test_df)[:, 1]
    expo_test = metrics.exposure(test_df)
    test_flags = metrics.policy_flags(p_test, expo_test, config.REVIEW_COST_NT)
    test_metrics = metrics.ranking_metrics(y_test, p_test)
    test_policy = metrics.policy_eval(p_test, y_test, expo_test, config.REVIEW_COST_NT)
    test_confusion = metrics.confusion(test_flags, y_test)

    evidence = handoff.assemble_evidence(
        splits, leaderboard, calibration_table, sweep,
        val_policy, val_confusion,
        metrics.review_everybody_savings(y_val, expo_val, config.REVIEW_COST_NT),
        fairness, audit_sex, audit_age,
        test_metrics, test_policy, test_confusion,
        metrics.review_everybody_savings(y_test, expo_test, config.REVIEW_COST_NT),
    )

    print("Building reason codes and exporting the artifact contract...")
    X_test = features.build_features(test_df)
    explainer = explain.build_explainer(pipeline.named_steps["model"])
    manifest = handoff.build_manifest(test_df, X_test, p_test, test_flags, explainer)
    sizes = handoff.export(pipeline, evidence, manifest)
    identity = handoff.verify()

    for name, size in sizes.items():
        print(f"  {name:<26} {size}")
    print(
        f"Ready in {fit_seconds:.1f}s fit: test AUC {test_metrics['auc']:.4f}, "
        f"flagged {test_policy['flagged']}/{len(y_test)}, "
        f"net savings NT${test_policy['net_savings_NT']:,}, "
        f"reload {identity['status']} ({identity['route_changes']} route changes)."
    )
    flagged_in_manifest = int((manifest["route"] == config.ROUTE_FLAGGED).sum())
    print(
        f"Manifest: {len(manifest)} accounts, {flagged_in_manifest} flagged, "
        f"{len(manifest) - flagged_in_manifest} standard monitoring."
    )


if __name__ == "__main__":
    main()
