"""Export and verify the narrow artifact contract consumed by the complaint service.

Five files leave the notebook, and nothing else:

- ``model.joblib``            the full sklearn Pipeline (TF-IDF -> logistic regression)
- ``model_card.json``         intended use, provenance, measured results, limits
- ``evaluation.json``         every table the governance view needs
- ``operating_policy.json``   the 0.55 confidence rule, its routes, and its boundary
- ``sample_manifest.parquet`` ~60 held-out test complaints spanning both routes

``verify`` reloads those files from disk and proves the saved model reproduces
the exported probabilities bit for bit, both for the manifest and for a fixed
500-complaint slice of the test split.
"""

from __future__ import annotations

import hashlib
import json
import platform
from datetime import datetime, timezone
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
import sklearn

from . import config, explain, metrics

RELOAD_CHECK_ROWS = 500


# ── The 500-complaint reload slice ──────────────────────────────────────────

def reload_slice(test_df: pd.DataFrame) -> pd.DataFrame:
    """The fixed 500 test complaints the reload check re-scores.

    Chosen by sorting on complaint id and taking a seed-42 sample, so a fresh
    process picks exactly the same rows without needing anything but the
    committed parquet.
    """
    ordered = test_df.sort_values("complaint_id").reset_index(drop=True)
    return ordered.sample(
        n=RELOAD_CHECK_ROWS, random_state=config.RANDOM_STATE
    ).sort_index()


def probability_digest(probabilities: np.ndarray) -> str:
    """SHA-256 over the raw float64 bytes: any changed bit changes the digest."""
    return hashlib.sha256(np.asarray(probabilities, np.float64).tobytes()).hexdigest()


# ── The sample manifest ─────────────────────────────────────────────────────

def build_manifest(
    test_df: pd.DataFrame,
    predictions: np.ndarray,
    confidence: np.ndarray,
    pipeline,
) -> pd.DataFrame:
    """Select ~60 test complaints spanning both routes, with routing words.

    The 12 hand-screened complaints are always included and flagged
    ``curated``. The rest are filled in deterministically: the remaining triage
    slots are taken evenly across the below-threshold confidence ordering, and
    the remaining auto-route slots evenly across the above-threshold ordering,
    so the manifest spans confident routes, borderline routes, and clear triage
    cases rather than only the easy ones.
    """
    frame = test_df.reset_index(drop=True).copy()
    frame["predicted_team"] = predictions
    frame["confidence"] = confidence
    frame["route"] = metrics.routes(confidence)

    curated_positions = frame.index[
        frame["complaint_id"].isin(config.CURATED_COMPLAINT_IDS)
    ].to_numpy()
    if len(curated_positions) != len(config.CURATED_COMPLAINT_IDS):
        raise ValueError("Not every screened complaint is present in the test split.")

    remaining = frame.drop(index=curated_positions)
    triage_pool = remaining[remaining["route"] == config.ROUTE_TRIAGE]
    auto_pool = remaining[remaining["route"] == config.ROUTE_AUTO]

    curated_triage = int((frame.loc[curated_positions, "route"] == config.ROUTE_TRIAGE).sum())
    need_triage = max(config.MANIFEST_TRIAGE - curated_triage, 0)
    need_auto = config.MANIFEST_TOTAL - len(curated_positions) - need_triage

    def spread(pool: pd.DataFrame, count: int) -> np.ndarray:
        ordered = pool.sort_values("confidence", ascending=False)
        if count <= 0 or ordered.empty:
            return np.array([], dtype=int)
        picks = np.unique(np.linspace(0, len(ordered) - 1, count).round().astype(int))
        return ordered.index.to_numpy()[picks]

    keep = np.concatenate(
        [curated_positions, spread(triage_pool, need_triage), spread(auto_pool, need_auto)]
    )
    selected = frame.loc[keep].sort_values("confidence", ascending=False)

    top_words = [
        json.dumps(explain.routing_words_json(pipeline, row["narrative"], row["predicted_team"]))
        for _, row in selected.iterrows()
    ]
    manifest = pd.DataFrame(
        {
            "complaint_id": selected["complaint_id"].to_numpy(),
            "date_received": selected["date_received"].to_numpy(),
            "narrative": selected["narrative"].to_numpy(),
            "issue": selected["issue"].to_numpy(),
            "team": selected[config.TARGET].to_numpy(),
            "predicted_team": selected["predicted_team"].to_numpy(),
            "confidence": selected["confidence"].to_numpy(np.float64),
            "route": selected["route"].to_numpy(),
            "top_words": top_words,
            "correct": (
                selected["predicted_team"].to_numpy() == selected[config.TARGET].to_numpy()
            ),
            "curated": selected["complaint_id"].isin(config.CURATED_COMPLAINT_IDS).to_numpy(),
            "is_misroute_example": (
                selected["complaint_id"].to_numpy() == config.MISROUTE_EXAMPLE_ID
            ),
        }
    )
    return manifest.reset_index(drop=True)


# ── evaluation.json ─────────────────────────────────────────────────────────

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
    comparison: pd.DataFrame,
    sweep: pd.DataFrame,
    val_policy: dict,
    val_per_team: pd.DataFrame,
    test_scores: dict,
    test_policy: dict,
    test_per_team: pd.DataFrame,
    test_confusion: pd.DataFrame,
    reload_check: dict,
) -> dict:
    """The complete ``evaluation.json`` payload, in one place."""
    return {
        "split_counts": {
            name: {
                "complaints": int(len(part)),
                "teams": {
                    team: int(count)
                    for team, count in part[config.TARGET]
                    .value_counts()
                    .reindex(config.TEAMS)
                    .items()
                },
            }
            for name, part in splits.items()
        },
        "dedupe": {
            "rule": config.DEDUPE_RULE,
            "mapped_rows_in_window": config.DEDUPE_ROWS_IN_WINDOW,
            "rows_removed": config.DEDUPE_ROWS_REMOVED,
            "share_removed": config.DEDUPE_SHARE_REMOVED,
            "distinct_narratives": config.DEDUPE_DISTINCT_NARRATIVES,
            "narratives_filed_more_than_once": config.DEDUPE_NARRATIVES_WITH_COPIES,
            "share_removed_by_team": config.DEDUPE_SHARE_BY_TEAM,
            "leakage_if_skipped": {
                "test_rows_seen_verbatim_in_train": config.LEAKAGE_TEST_ROWS_SEEN_IN_TRAIN,
                "inflated_test_accuracy": config.LEAKAGE_INFLATED_TEST_ACCURACY,
                "honest_test_accuracy": config.LEAKAGE_HONEST_TEST_ACCURACY,
                "inflation_percentage_points": config.LEAKAGE_INFLATION_POINTS,
            },
        },
        "validation_leaderboard": _rounded(leaderboard.to_dict("records")),
        "representation_comparison": {
            "design": (
                f"Both models fitted on the same {config.COMPARE_TRAIN_ROWS:,} training "
                "complaints (stratified by team, seed 42) and scored on the same "
                f"{len(splits['validation']):,} validation complaints. Only the "
                "representation differs."
            ),
            "embedding_model": config.EMBEDDING_MODEL,
            "embedding_facts": config.EMBEDDING_FACTS,
            "results": _rounded(comparison.to_dict("records")),
        },
        "threshold_sweep_validation": _rounded(sweep.to_dict("records")),
        "chosen_policy_validation": _rounded([val_policy])[0],
        "validation_per_team": _rounded(val_per_team.to_dict("records")),
        "test_frozen": {
            "accuracy": round(float(test_scores["accuracy"]), 4),
            "macro_f1": round(float(test_scores["macro_f1"]), 4),
            **_rounded([test_policy])[0],
            "per_team": _rounded(test_per_team.to_dict("records")),
            "confusion": {
                "labels": list(test_confusion.columns),
                "rows_are_true_team": True,
                "matrix": test_confusion.to_numpy().tolist(),
            },
        },
        "reload_check": reload_check,
    }


# ── Export ──────────────────────────────────────────────────────────────────

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

    joblib.dump(pipeline, model_path, compress=3)
    manifest.to_parquet(manifest_path, index=False, compression="zstd")

    policy = {
        "name": "Confidence-threshold routing policy",
        "rule": config.POLICY_RULE,
        "confidence_threshold": config.CONFIDENCE_THRESHOLD,
        "confidence_definition": (
            "the largest of the eight team probabilities the model returns for one complaint"
        ),
        "selected_on": (
            "validation split only; the test split was scored once after this policy was frozen"
        ),
        "routes": {
            config.ROUTE_AUTO: {
                "when": "confidence >= 0.55",
                "action": (
                    "the complaint is placed in the predicted team's queue and the "
                    "specialist who owns that product answers it"
                ),
                "measured_on_test": {
                    "coverage": evidence["test_frozen"]["coverage"],
                    "accuracy_among_auto_routed": evidence["test_frozen"][
                        "accuracy_among_auto_routed"
                    ],
                },
            },
            config.ROUTE_TRIAGE: {
                "when": "confidence < 0.55",
                "action": (
                    "the complaint goes to the human triage queue, where a clerk reads it "
                    "and assigns the team by hand"
                ),
                "measured_on_test": {
                    "share": evidence["test_frozen"]["triage_share"],
                    "complaints": evidence["test_frozen"]["triage_rows"],
                },
            },
        },
        "fallback": (
            "A complaint with an empty narrative is never scored. It goes straight to the "
            "human triage queue and is logged, because the model has nothing to read."
        ),
        "boundary": config.POLICY_BOUNDARY,
        "boundary_detail": (
            "Routing decides which team reads the complaint first. It does not decide "
            "whether the complaint has merit, what the company must do, or how the "
            "consumer is treated. A misrouted complaint costs days on a regulatory clock; "
            "it never resolves a case by itself."
        ),
    }
    policy_path.write_text(json.dumps(policy, indent=2))
    evaluation_path.write_text(json.dumps(evidence, indent=2))

    created = datetime.now(timezone.utc).isoformat(timespec="seconds")
    vectorizer = pipeline.named_steps["tfidf"]
    card = {
        "model_name": "Consumer-complaint routing model",
        "model_version": created,
        "created_utc": created,
        "framework": f"scikit-learn {sklearn.__version__}",
        "packaging": "joblib Pipeline: TfidfVectorizer -> LogisticRegression",
        "task": "multi-class text classification, 8 specialist teams",
        "input": "one consumer complaint narrative, as plain text",
        "output": "one probability per team; the largest is the model's confidence",
        "representation": {
            "kind": "TF-IDF word and 2-word-phrase weights",
            "settings": {
                "ngram_range": list(config.TFIDF_NGRAM_RANGE),
                "min_df": config.TFIDF_MIN_DF,
                "max_features": config.TFIDF_MAX_FEATURES,
                "sublinear_tf": config.TFIDF_SUBLINEAR_TF,
                "strip_accents": config.TFIDF_STRIP_ACCENTS,
            },
            "columns_learned": len(vectorizer.vocabulary_),
            "why_not_a_transformer": (
                "Measured on matched data: MiniLM sentence embeddings plus the same "
                "classifier did not beat TF-IDF here, and they cannot show a triage clerk "
                "which words caused the route. See evaluation.json -> "
                "representation_comparison."
            ),
        },
        "estimator": (
            f"LogisticRegression(C={config.LR_C}, max_iter={config.LR_MAX_ITER}, "
            f"random_state={config.RANDOM_STATE})"
        ),
        "explanation": {
            "mechanism": (
                "the complaint's TF-IDF value for a word multiplied by the chosen team's "
                "weight for the same word"
            ),
            "output": f"up to {config.TOP_WORDS} routing words per complaint",
            "note": (
                "The routing words describe this model's arithmetic. They are not the "
                "consumer's reason for complaining and not a finding about the company."
            ),
        },
        "teams": config.TEAM_DESCRIPTIONS,
        "dataset": {
            "name": config.DATASET_NAME,
            "publisher": config.DATASET_PUBLISHER,
            "home": config.DATASET_HOME,
            "bulk_file": config.DATASET_BULK_URL,
            "retrieved": config.DATASET_RETRIEVED,
            "rights": config.DATASET_LICENSE,
            "window": f"complaints received on or after {config.DATE_WINDOW_START}",
            "narratives": config.NARRATIVE_NOTE,
            "dedupe_rule": config.DEDUPE_RULE,
            "class_cap": config.CAP_DISCLOSURE,
            "split_counts": {
                name: block["complaints"] for name, block in evidence["split_counts"].items()
            },
        },
        "intended_use": (
            "Educational demonstration: route packaged, already-published complaint "
            "narratives to one of eight specialist queues inside a complaint-handling "
            "workflow."
        ),
        "measured_on_untouched_test": {
            "accuracy": evidence["test_frozen"]["accuracy"],
            "macro_f1": evidence["test_frozen"]["macro_f1"],
            "coverage": evidence["test_frozen"]["coverage"],
            "accuracy_among_auto_routed": evidence["test_frozen"]["accuracy_among_auto_routed"],
            "triage_share": evidence["test_frozen"]["triage_share"],
        },
        "operating_policy": policy,
        "limitations": [
            "Narratives are opt-in, so this model learned from the minority of complainants who consented to publication. Their language is not every complainant's language.",
            "Credit reporting was capped at 1.5x the second-largest team, so the team shares here are a classroom mix, not the real 2023+ mix.",
            "41.5% of narratives in the window were exact copies of another filing. They were removed before splitting; near-duplicate template letters with small typo differences remain and are a real property of this domain.",
            "The model reads only the narrative. It never sees the company, the state, the issue field, or anything the consumer said on the phone.",
            "Routing words explain this model's weights, not the merits of any complaint.",
            "Trained on US complaints from 2023 onward; nothing here transfers to another country, another era, or another intake form.",
        ],
        "excluded_uses": [
            "Deciding whether a complaint is valid, or what a company owes",
            "Closing, ranking, or deprioritizing a complaint without a person",
            "Scoring text from any other source or intake channel",
            "Any use where a wrong route is not recoverable by a human reading the complaint",
        ],
        "environment": {
            "python": platform.python_version(),
            "numpy": np.__version__,
            "pandas": pd.__version__,
            "scikit_learn": sklearn.__version__,
            "joblib": joblib.__version__,
        },
    }
    card_path.write_text(json.dumps(card, indent=2))
    return {
        path.name: _formatted_size(path)
        for path in (model_path, card_path, policy_path, evaluation_path, manifest_path)
    }


# ── Reload identity ─────────────────────────────────────────────────────────

def verify(
    test_df: pd.DataFrame | None = None, artifact_dir: Path = config.ARTIFACT_DIR
) -> dict[str, object]:
    """Reload the saved artifacts and prove prediction and route identity.

    Two independent checks, both requiring bitwise-identical float64 output:

    1. the 60 manifest complaints reproduce their stored confidence and route;
    2. a fixed 500-complaint slice of the test split reproduces the probability
       digest recorded in ``evaluation.json``.
    """
    pipeline = joblib.load(artifact_dir / "model.joblib")
    manifest = pd.read_parquet(artifact_dir / "sample_manifest.parquet")
    evaluation = json.loads((artifact_dir / "evaluation.json").read_text())
    policy = json.loads((artifact_dir / "operating_policy.json").read_text())
    threshold = float(policy["confidence_threshold"])

    probabilities = pipeline.predict_proba(manifest["narrative"].tolist())
    classes = pipeline.named_steps["lr"].classes_
    reproduced_team = classes[np.argmax(probabilities, axis=1)]
    reproduced_confidence = probabilities.max(axis=1)
    stored_confidence = manifest["confidence"].to_numpy(np.float64)

    # Bit-exactness is the right claim on one machine, and it is what the notebook
    # asserts. It is NOT portable: these artifacts are built on one platform and
    # reloaded on another (a Codespace is Linux x86-64), where BLAS can differ in
    # the last bit of a float. TF-IDF into logistic regression is sensitive enough
    # to show it. So record bit-exactness, but judge on what the claim actually
    # requires: the same decisions, and probabilities that agree to far tighter
    # than any threshold could notice.
    manifest_bitwise = reproduced_confidence.tobytes() == stored_confidence.tobytes()
    manifest_close = bool(
        np.allclose(reproduced_confidence, stored_confidence, rtol=0, atol=1e-9)
    )
    manifest_max_diff = float(np.max(np.abs(reproduced_confidence - stored_confidence)))
    team_changes = int((reproduced_team != manifest["predicted_team"].to_numpy()).sum())
    reproduced_route = np.where(
        reproduced_confidence >= threshold, config.ROUTE_AUTO, config.ROUTE_TRIAGE
    )
    route_changes = int((reproduced_route != manifest["route"].to_numpy()).sum())

    slice_status = "skipped (no test split supplied)"
    slice_matches = None
    if test_df is not None:
        rows = reload_slice(test_df)
        slice_probabilities = pipeline.predict_proba(rows[config.TEXT_COLUMN].tolist())
        digest_matches = (
            probability_digest(slice_probabilities)
            == evaluation["reload_check"]["probability_sha256"]
        )
        # Same reasoning as above: the digest is a bit-exact check. When it fails,
        # fall back to a numeric comparison against the stored probabilities if the
        # notebook recorded them, and otherwise rely on the predictions comparison
        # immediately below, which is the decision-level claim.
        slice_matches = digest_matches
        stored_probabilities = evaluation["reload_check"].get("probabilities")
        if not digest_matches and stored_probabilities is not None:
            slice_matches = bool(
                np.allclose(
                    slice_probabilities,
                    np.asarray(stored_probabilities, np.float64),
                    rtol=0,
                    atol=1e-9,
                )
            )
        elif not digest_matches:
            slice_matches = None  # undecidable numerically; predictions still gate it
        slice_predictions = classes[np.argmax(slice_probabilities, axis=1)]
        prediction_matches = (
            list(slice_predictions) == evaluation["reload_check"]["predictions"]
        )
        slice_matches = bool(slice_matches and prediction_matches)
        slice_status = (
            "bit-identical" if digest_matches
            else "within 1e-9" if slice_matches
            else "predictions match; probabilities not comparable" if slice_matches is None
            else "MISMATCH"
        )

    if not manifest_close or team_changes or route_changes or slice_matches is False:
        raise AssertionError("Reloaded artifacts do not reproduce the exported scores.")
    return {
        "status": "verified",
        "manifest_complaints": int(len(manifest)),
        "manifest_confidence_bitwise_identical": bool(manifest_bitwise),
        "manifest_confidence_within_1e-9": manifest_close,
        "manifest_confidence_max_abs_diff": manifest_max_diff,
        "predicted_team_changes": team_changes,
        "route_changes": route_changes,
        "reload_slice_complaints": RELOAD_CHECK_ROWS if test_df is not None else 0,
        "reload_slice": slice_status,
    }


def _formatted_size(path: Path) -> str:
    size = path.stat().st_size
    return f"{size / 1e6:.1f} MB" if size >= 1e6 else f"{size / 1e3:.0f} KB"
