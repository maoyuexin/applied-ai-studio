"""Run the full complaint-routing workflow headlessly and export verified artifacts.

Same steps and same frozen decisions as the notebook (committed splits -> the
matched representation comparison -> TF-IDF + logistic regression -> the 0.55
confidence policy chosen on validation -> a single frozen test scoring -> export
-> reload verification), so `npm run prepare:complaints` reproduces the exact
files the notebook commits evidence for.

Nothing here downloads a model or a dataset. The MiniLM embeddings are read from
the committed parquets.
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

import numpy as np

PROJECT_DIR = Path(__file__).resolve().parents[1]
if str(PROJECT_DIR) not in sys.path:
    sys.path.insert(0, str(PROJECT_DIR))

from complaintlab import config, data, handoff, metrics, models  # noqa: E402


def main() -> None:
    started = time.perf_counter()
    print("Loading the committed 70/15/15 complaint splits...")
    splits = data.load_splits()
    train, validation, test = splits["train"], splits["validation"], splits["test"]
    X_train, y_train = train[config.TEXT_COLUMN], train[config.TARGET]
    X_val, y_val = validation[config.TEXT_COLUMN], validation[config.TARGET]
    X_test, y_test = test[config.TEXT_COLUMN], test[config.TARGET]

    print("Fitting the baseline and the deployed TF-IDF model on the training split...")
    baseline = models.majority_baseline(y_train, len(y_val))
    tfidf = models.fit_tfidf(X_train, y_train, X_val)

    print(f"Matched comparison on {config.COMPARE_TRAIN_ROWS:,} complaints (TF-IDF vs MiniLM)...")
    subsample = models.comparison_subsample(train)
    tfidf_matched = models.fit_tfidf(
        subsample[config.TEXT_COLUMN],
        subsample[config.TARGET],
        X_val,
        name=f"TF-IDF + logistic regression ({config.COMPARE_TRAIN_ROWS:,} rows)",
    )
    E_train = models.load_embeddings(
        config.EMBEDDINGS_TRAIN_PARQUET, subsample["complaint_id"]
    )
    E_val = models.load_embeddings(
        config.EMBEDDINGS_VAL_PARQUET, validation["complaint_id"]
    )
    minilm = models.fit_embedding_model(
        E_train,
        subsample[config.TARGET],
        E_val,
        name=f"MiniLM embeddings + logistic regression ({config.COMPARE_TRAIN_ROWS:,} rows)",
    )
    comparison = models.leaderboard([tfidf_matched, minilm], y_val)
    leaderboard = models.leaderboard([baseline, tfidf], y_val)

    print("Choosing the confidence policy on validation only...")
    sweep = metrics.threshold_sweep(y_val, tfidf.val_predictions, tfidf.val_confidence)
    val_policy = metrics.policy_eval(y_val, tfidf.val_predictions, tfidf.val_confidence)
    val_per_team = metrics.per_team_table(y_val, tfidf.val_predictions)

    print("Policy frozen. Scoring the untouched test split once...")
    pipeline = tfidf.estimator
    test_probabilities = pipeline.predict_proba(X_test)
    classes = pipeline.named_steps["lr"].classes_
    test_predictions = classes[np.argmax(test_probabilities, axis=1)]
    test_confidence = test_probabilities.max(axis=1)
    test_scores = metrics.classification_scores(y_test, test_predictions)
    test_policy = metrics.policy_eval(y_test, test_predictions, test_confidence)
    test_per_team = metrics.per_team_table(y_test, test_predictions)
    test_confusion = metrics.confusion_frame(y_test, test_predictions)

    rows = handoff.reload_slice(test)
    slice_probabilities = pipeline.predict_proba(rows[config.TEXT_COLUMN].tolist())
    reload_check = {
        "complaints": handoff.RELOAD_CHECK_ROWS,
        "selection": "test split sorted by complaint_id, sampled with seed 42",
        "probability_sha256": handoff.probability_digest(slice_probabilities),
        "predictions": list(classes[np.argmax(slice_probabilities, axis=1)]),
    }

    evidence = handoff.assemble_evidence(
        splits, leaderboard, comparison, sweep, val_policy, val_per_team,
        test_scores, test_policy, test_per_team, test_confusion, reload_check,
    )
    manifest = handoff.build_manifest(test, test_predictions, test_confidence, pipeline)
    sizes = handoff.export(pipeline, evidence, manifest)
    identity = handoff.verify(test)

    for name, size in sizes.items():
        print(f"  {name:<26} {size}")
    print(
        f"Ready in {time.perf_counter() - started:.1f}s: test accuracy "
        f"{test_scores['accuracy']:.4f}, macro-F1 {test_scores['macro_f1']:.4f}, "
        f"coverage {test_policy['coverage']:.4f}, accuracy among auto-routed "
        f"{test_policy['accuracy_among_auto_routed']:.4f}."
    )
    print(
        f"Manifest: {len(manifest)} complaints, "
        f"{int((manifest['route'] == config.ROUTE_TRIAGE).sum())} triage, "
        f"{int(manifest['curated'].sum())} screened for teaching."
    )
    print(f"Reload: {identity['status']}, slice {identity['reload_slice']}.")


if __name__ == "__main__":
    main()
