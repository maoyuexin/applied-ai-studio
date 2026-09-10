"""Export and verify the narrow artifact contract the procedure service consumes.

Eight files leave the notebook, and nothing else:

- ``chunks.parquet``        every indexed passage, its citation and its source
- ``embeddings.npy``        the MiniLM vectors, float16, one row per chunk
- ``index.joblib``          the fitted TF-IDF vectorizer and matrix, kept as the
                            comparison retriever and as a keyword fallback
- ``model_card.json``       intended use, provenance, measured results, limits
- ``evaluation.json``       every number the notebook printed
- ``operating_policy.json`` tau, both refusal rules, and the boundary statement
- ``corpus_manifest.json``  per document: source, licence, distribution status,
                            checksum
- ``cached_answers.json``   the 20 packaged answers, 4 of them refusals

Two things are deliberately **not** exported. The MiniLM weights are not: the
service loads ``all-MiniLM-L6-v2`` by name from its own cache, so this
repository never ships 90 MB of model. And no generative model is exported at
all, because there is none - the answers are written by a person from retrieved
passages and cached.

``verify`` reloads the artifacts from disk and re-runs 50 questions through
them, requiring the top-5 chunk ids to be identical to the ones recorded at
export. Float16 storage is a real change to the vectors; this is the check that
it does not change what comes back.
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

from . import chunking, config, retrieval

RELOAD_QUESTIONS = 50

CHUNKS = "chunks.parquet"
EMBEDDINGS = "embeddings.npy"
INDEX = "index.joblib"
MODEL_CARD = "model_card.json"
EVALUATION = "evaluation.json"
POLICY = "operating_policy.json"
MANIFEST = "corpus_manifest.json"
ANSWERS = "cached_answers.json"

ARTIFACT_ORDER = [CHUNKS, EMBEDDINGS, INDEX, MODEL_CARD, EVALUATION, POLICY,
                  MANIFEST, ANSWERS]


# ── The reload baseline ─────────────────────────────────────────────────────

def reload_questions(questions: pd.DataFrame,
                     msha: pd.DataFrame) -> pd.DataFrame:
    """The fixed 50 questions the reload check re-runs.

    The main evaluation set first, then the MSHA set, taken in file order and
    truncated at 50, so a fresh process picks exactly the same questions from
    the committed CSVs without needing anything else.
    """
    columns = ["qid", "question"]
    return pd.concat([questions[columns], msha[columns]],
                     ignore_index=True).head(RELOAD_QUESTIONS)


def baseline_top5(retrievers: dict, questions: pd.DataFrame) -> dict:
    """Top-5 chunk ids per question per retriever, recorded before export."""
    baseline = {}
    for row in questions.to_dict("records"):
        entry = {}
        for name, retriever in retrievers.items():
            entry[name] = [retriever.chunks.iloc[position]["chunk_id"]
                           for position, _ in retriever.search(row["question"], 5)]
        baseline[row["qid"]] = entry
    return baseline


def vector_digest(vectors: np.ndarray) -> str:
    """SHA-256 over the raw float16 bytes: any changed bit changes the digest."""
    return hashlib.sha256(np.asarray(vectors, np.float16).tobytes()).hexdigest()


# ── evaluation.json ─────────────────────────────────────────────────────────

def _round(records, places: int = 4):
    if isinstance(records, pd.DataFrame):
        records = records.to_dict("records")
    return [{key: (round(value, places) if isinstance(value, float) else value)
             for key, value in record.items()} for record in records]


def assemble_evidence(
    corpus_summary: pd.DataFrame,
    licence_scan: dict,
    chunk_sizes: pd.DataFrame,
    truncation: dict,
    citation_audit: dict,
    leaderboard: pd.DataFrame,
    per_bucket: pd.DataFrame,
    phrasing: dict,
    gold_validation: dict,
    policy_sweep: pd.DataFrame,
    policy_result: dict,
    duplicate: dict,
    claim_check: dict,
    reload_check: dict,
) -> dict:
    """The complete ``evaluation.json`` payload, in one place.

    Everything the notebook prints is here, so a reader who never opens the
    notebook can still audit the claim, and so a printed number that drifts
    from the exported one is a visible contradiction rather than a private one.
    """
    return {
        "corpus": {
            "id": config.CORPUS_ID,
            "retrieved": config.CORPUS_RETRIEVED,
            "ecfr_date_pin": config.ECFR_DATE_PIN,
            "fetch_policy": config.FETCH_POLICY,
            "by_layer": _round(corpus_summary),
            "licence_gate_tm_9_6115_464_12": licence_scan,
        },
        "chunking": {
            "rule": config.CHUNKING_RULE,
            "token_budget": config.TOKEN_BUDGET,
            "model_token_window": config.MODEL_TOKEN_WINDOW,
            "indexed_text": config.INDEXED_TEXT_RULE,
            "size_comparison": _round(chunk_sizes),
            "tokens_discarded_by_policy": truncation,
        },
        "citations": citation_audit,
        "retrieval": {
            "questions_scored": int(leaderboard["Questions"].iloc[0]),
            "leaderboard": _round(leaderboard),
            "per_bucket": _round(per_bucket),
            "question_phrasing": phrasing,
            "gold_validation": gold_validation,
        },
        "refusal": {
            "tau": config.REFUSAL_TAU,
            "rules": list(config.REFUSAL_RULES),
            "sweep": _round(policy_sweep),
            "chosen": policy_result,
        },
        "duplicate_corpus": duplicate,
        "unsupported_claim_check": {
            key: value for key, value in claim_check.items()
            if not key.endswith("detail")},
        "reload_check": reload_check,
        "environment": {
            "python": platform.python_version(),
            "numpy": np.__version__,
            "pandas": pd.__version__,
            "scikit_learn": sklearn.__version__,
            "embedder": config.EMBEDDER,
            "generated": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        },
    }


def build_model_card(evidence: dict, chunks: pd.DataFrame,
                     manifest: pd.DataFrame) -> dict:
    """What this thing is for, what it was measured at, and where it fails."""
    retrieval_scores = {row["Retriever"]: row for row in
                        evidence["retrieval"]["leaderboard"]}
    return {
        "name": "Grounded procedure assistant - retrieval and citation",
        "version": config.CORPUS_ID,
        "generated": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "what_it_does": (
            "Given a maintenance or safety question, it returns the passages "
            "from a fixed, vetted corpus that are closest to the question, each "
            "carrying the citation a person can look up, and either a drafted "
            "answer written only from those passages or a refusal."),
        "what_it_does_not_do": [
            "It does not authorize work of any kind.",
            "It does not approve, issue or release a lockout, tagout or clearance.",
            "It does not answer from the model's own memory; every answer is "
            "written from retrieved passages or refused.",
            "It does not rank passages by legal authority - a plain-language "
            "booklet can outrank the regulation it describes.",
            "It does not decide whether a rule applies to your situation.",
        ],
        "boundary": config.BOUNDARY,
        "intended_users": (
            "Maintenance technicians, planners and safety staff who already know "
            "the work and need to find the governing passage quickly. Every "
            "answer is read and verified by a qualified person before use."),
        "corpus": {
            "documents": int(len(manifest)),
            "documents_in_base_corpus": int(manifest["in_base_corpus"].sum()),
            "chunks": int(len(chunks)),
            "layers": list(config.LAYERS),
            "date_pin": config.ECFR_DATE_PIN,
            "licence_rule": (
                "US Government work AND an unrestricted distribution status. "
                "Public domain alone is not sufficient - see corpus_manifest.json."),
        },
        "how_it_represents_text": {
            "embedder": config.EMBEDDER,
            "dimensions": config.EMBEDDING_DIM,
            "similarity": "cosine on L2-normalised vectors",
            "storage": "float16 (verified to leave the top-5 unchanged)",
            "chunking": config.CHUNKING_RULE,
            "comparison_retriever": "TF-IDF word counts, exported beside it",
        },
        "measured": {
            "questions": evidence["retrieval"]["questions_scored"],
            "deployed_retriever": retrieval_scores.get("MiniLM sentence embeddings"),
            "comparison_retriever": retrieval_scores.get("TF-IDF word counts"),
            "correct_refusal_outside_corpus": evidence["refusal"]["chosen"]["correct_refusal_D"],
            "correct_refusal_incorporated_by_reference": evidence["refusal"]["chosen"]["correct_refusal_E"],
            "false_refusal_rate": evidence["refusal"]["chosen"]["false_refusal_rate"],
            "unsupported_numerals_in_packaged_answers":
                evidence["unsupported_claim_check"]["unsupported_numerals"],
        },
        "known_limits": [
            "The citation on a chunk is the citation of its first paragraph. A "
            "chunk can carry text from the next paragraph, so a citation may be "
            "one paragraph coarse. The service must display the passage, not "
            "only its label.",
            "The unsupported-claim check verifies that every numeral came from a "
            "retrieved passage. It cannot tell whether that passage governs the "
            "question, so it catches invention and not misattribution.",
            "Near-duplicate documents destroy citation accuracy while leaving "
            "retrieval of the text almost untouched. Adding 30 CFR 57 beside "
            "30 CFR 56 moved citation hit@1 from "
            f"{evidence['duplicate_corpus']['minilm']['cite_hit@1_before']} to "
            f"{evidence['duplicate_corpus']['minilm']['cite_hit@1_after']}. Never "
            "load two near-identical regulations into one index.",
            "The corpus is pinned to " + config.ECFR_DATE_PIN + ". It does not "
            "know about anything published since, and it will not say so.",
            "Consensus standards incorporated by reference (ANSI, NFPA, ASTM) "
            "are not in the corpus and cannot be. Questions that need them are "
            "refused by rule, not by score.",
        ],
        "evaluation_set": {
            "questions": 60,
            "buckets": {key: {"description": value[0], "questions": value[1]}
                        for key, value in config.BUCKETS.items()},
            "written_by": (
                "Phrased the way a technician asks, not copied from the passage "
                "text. Questions copied from the passages hand a keyword matcher "
                "the answer and inflate its score - see evaluation.json."),
        },
    }


def build_policy(evidence: dict) -> dict:
    return {
        "refusal_threshold": config.REFUSAL_TAU,
        "rules": [
            {"rule": "low_confidence",
             "condition": f"top-1 cosine similarity < {config.REFUSAL_TAU}",
             "why": "Nothing in the corpus is close enough to the question.",
             "action": "Refuse and name what the corpus does contain."},
            {"rule": "incorporated_by_reference",
             "condition": "the retrieved context incorporates a named consensus "
                          "standard by reference AND the question asks for a "
                          "specification, rating or value",
             "why": "The rule points at a document the corpus does not hold, so "
                    "a confident-looking number nearby is not the answer.",
             "action": "Refuse, name the standard, and tell the reader to obtain it."},
        ],
        "measured_at_this_threshold": evidence["refusal"]["chosen"],
        "top_k_shown": config.TOP_K_SHOWN,
        "service_must": [
            "Display every retrieved passage in full beside its citation.",
            "Display the citation as retrieved; never re-format or shorten it.",
            "Show the refusal text unchanged when the status is a refusal.",
            "Never present an answer without its passages.",
        ],
        "boundary": config.BOUNDARY,
    }


def build_manifest(manifest: pd.DataFrame) -> dict:
    return {
        "corpus": config.CORPUS_ID,
        "retrieved": config.CORPUS_RETRIEVED,
        "ecfr_date_pin": config.ECFR_DATE_PIN,
        "licence_rule": (
            "Two independent gates: copyright status AND distribution status. A "
            "US Government work carries no copyright and can still be restricted "
            "from redistribution by a distribution statement on page 1. Accept "
            "DISTRIBUTION STATEMENT A only."),
        "documents": [
            {"document": row["doc"], "title": row["title"], "layer": row["layer"],
             "publisher": row["publisher"], "source_url": row["url"],
             "license": row["license"], "distribution": row["distribution"],
             "retrieved": row["retrieved"], "date_pin": row["date_pin"],
             "committed_file": row["file"], "md5": row["md5"],
             "bytes": int(row["bytes"]), "words": int(row["words"]),
             "in_base_corpus": bool(row["in_base_corpus"])}
            for row in manifest.to_dict("records")],
        "excluded": [
            {"document": row["document"], "why_excluded": row["why_rejected"],
             "lesson": row["lesson"]}
            for row in _rejected()],
    }


def _rejected() -> list[dict]:
    from . import corpus
    return corpus.REJECTED


# ── Export ──────────────────────────────────────────────────────────────────

def export(chunks: pd.DataFrame, vectors: np.ndarray, tfidf,
           evidence: dict, model_card: dict, policy: dict,
           manifest: dict, pack: dict) -> pd.DataFrame:
    """Write the eight-file contract and report what each one costs."""
    config.ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)

    table = chunks.copy()
    table["citations"] = table["citations"].apply(list)
    table.to_parquet(config.ARTIFACT_DIR / CHUNKS, index=False, compression="zstd")

    np.save(config.ARTIFACT_DIR / EMBEDDINGS, np.asarray(vectors, np.float16))

    joblib.dump({"vectorizer": tfidf.vectorizer, "matrix": tfidf.matrix,
                 "chunk_ids": chunks["chunk_id"].tolist(),
                 "params": dict(config.TFIDF_PARAMS)},
                config.ARTIFACT_DIR / INDEX, compress=3)

    for name, payload in ((MODEL_CARD, model_card), (EVALUATION, evidence),
                          (POLICY, policy), (MANIFEST, manifest),
                          (ANSWERS, pack)):
        (config.ARTIFACT_DIR / name).write_text(
            json.dumps(payload, indent=1, default=_encode), encoding="utf-8")

    rows = []
    for name in ARTIFACT_ORDER:
        path = config.ARTIFACT_DIR / name
        rows.append({"Artifact": name,
                     "Size": f"{path.stat().st_size / 1e6:.2f} MB",
                     "What the service does with it": _PURPOSE[name]})
    return pd.DataFrame(rows)


_PURPOSE = {
    CHUNKS: "Looks up the passage text and citation for a retrieved row",
    EMBEDDINGS: "Scores a question against every passage (cosine)",
    INDEX: "The TF-IDF comparison retriever and keyword fallback",
    MODEL_CARD: "Shown to reviewers; states what the system will not do",
    EVALUATION: "Every measured number, for governance and for regression tests",
    POLICY: "The refusal threshold and both refusal rules, read at startup",
    MANIFEST: "Proves every document may be redistributed",
    ANSWERS: "The 20 packaged answers served in the classroom demo",
}


def _encode(value):
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.floating,)):
        return float(value)
    if isinstance(value, (np.bool_,)):
        return bool(value)
    if isinstance(value, np.ndarray):
        return value.tolist()
    raise TypeError(f"cannot serialise {type(value)!r}")


# ── Verify ──────────────────────────────────────────────────────────────────

def verify(questions: pd.DataFrame, msha: pd.DataFrame) -> dict:
    """Reload the artifacts from disk and reproduce the recorded top-5.

    Nothing in-memory is reused. The chunk table, the float16 vectors and the
    TF-IDF index are read back from ``artifacts/``, the sentence encoder is
    loaded by name, and 50 questions are re-run. Identical top-5 chunk ids for
    both retrievers, or this raises.
    """
    from sklearn.preprocessing import normalize

    from .index import EmbedRetriever

    evidence = json.loads((config.ARTIFACT_DIR / EVALUATION).read_text())
    recorded = evidence["reload_check"]["baseline_top5"]

    table = pd.read_parquet(config.ARTIFACT_DIR / CHUNKS)
    chunk_ids = table["chunk_id"].tolist()
    vectors = np.load(config.ARTIFACT_DIR / EMBEDDINGS).astype(np.float32)
    vectors /= np.linalg.norm(vectors, axis=1, keepdims=True)
    saved = joblib.load(config.ARTIFACT_DIR / INDEX)
    model = EmbedRetriever.load_model()

    texts = [chunking.indexed_text(title, text) for title, text
             in zip(table["source_title"].fillna(""), table["text"])]
    del texts  # loaded only to prove the parquet carries what the index needs

    asked = reload_questions(questions, msha)
    matches = {"tfidf": 0, "minilm": 0}
    mismatches = []
    for row in asked.to_dict("records"):
        scores = (normalize(saved["vectorizer"].transform([row["question"]]))
                  @ saved["matrix"].T).toarray()[0]
        tfidf_top5 = [chunk_ids[i] for i in np.argsort(-scores)[:5]]
        query = model.encode([row["question"]], normalize_embeddings=True)[0]
        minilm_top5 = [chunk_ids[i] for i in np.argsort(-(vectors @ query))[:5]]
        for name, got in (("tfidf", tfidf_top5), ("minilm", minilm_top5)):
            if got == recorded[row["qid"]][name]:
                matches[name] += 1
            else:
                mismatches.append({"qid": row["qid"], "retriever": name,
                                   "recorded": recorded[row["qid"]][name],
                                   "reloaded": got})

    asked_count = len(asked)
    result = {
        "questions": asked_count,
        "identical_top5_tfidf": f"{matches['tfidf']}/{asked_count}",
        "identical_top5_minilm": f"{matches['minilm']}/{asked_count}",
        "chunks_reloaded": len(table),
        "embedding_dtype_on_disk": "float16",
        "embedding_digest": vector_digest(np.load(config.ARTIFACT_DIR / EMBEDDINGS)),
        "digest_recorded_at_export": evidence["reload_check"]["embedding_digest"],
        "mismatches": mismatches,
    }
    result["status"] = (
        "identical" if not mismatches and
        result["embedding_digest"] == result["digest_recorded_at_export"]
        else "MISMATCH")
    if result["status"] != "identical":
        raise AssertionError(f"Reload is not identical: {result}")
    return result


def committed_size() -> pd.DataFrame:
    """What this lab asks a student to clone, by directory."""
    rows = []
    for label, directory in (("Raw corpus (committed once)", config.RAW_DIR),
                             ("Derived tables", config.DATA_DIR),
                             ("Exported artifacts", config.ARTIFACT_DIR)):
        if label == "Derived tables":
            total = sum(path.stat().st_size for path in directory.glob("*")
                        if path.is_file())
        else:
            total = sum(path.stat().st_size for path in directory.rglob("*")
                        if path.is_file())
        rows.append({"What": label, "Megabytes": round(total / 1e6, 2)})
    rows.append({"What": "Total committed",
                 "Megabytes": round(sum(row["Megabytes"] for row in rows), 2)})
    return pd.DataFrame(rows)
