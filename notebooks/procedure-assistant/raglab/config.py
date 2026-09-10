"""Single source of truth for paths, the frozen spike decisions, and constants.

Every number a notebook cell, chart, or exported artifact quotes should come
from here or be recomputed live from the committed data, so there is one place
to change it and no chance of two artefacts disagreeing.

The choices below were frozen by the Module 5 RAG feasibility spike
(``M05_SPIKE_REPORT_rag.md``, verdict GO, 10/10 checks) and must not drift
without re-running that evidence:

- the 13-document corpus and its four layers (law / site procedure / equipment
  manual / plain-language guide), every eCFR fetch date-pinned to 2025-08-01;
- a **240-token** packing budget, not a word count, section-bounded;
- citations built by a stateful label stack, never by the paragraph's own label;
- ``all-MiniLM-L6-v2`` cosine over float16 vectors as the deployed retriever,
  with TF-IDF kept as the comparison;
- refusal at ``tau = 0.48`` plus the incorporation-by-reference rule;
- 60 evaluation questions in five buckets, written the way a technician talks.
"""

from __future__ import annotations

from pathlib import Path

import plotly.graph_objects as go

# -- Paths -------------------------------------------------------------------
PACKAGE_DIR = Path(__file__).resolve().parent
PROJECT_DIR = PACKAGE_DIR.parent
DATA_DIR = PROJECT_DIR / "data"
RAW_DIR = DATA_DIR / "corpus_raw"
RAW_CFR_DIR = RAW_DIR / "cfr"
RAW_PDF_DIR = RAW_DIR / "pdf"
RAW_TEXT_DIR = RAW_DIR / "text"
ARTIFACT_DIR = PROJECT_DIR / "artifacts"
BACKUP_DIR = PROJECT_DIR / "backup"

PROVENANCE_CSV = RAW_DIR / "provenance.csv"
LICENSE_NOTES = RAW_DIR / "LICENSES.md"
PARAGRAPHS_PARQUET = DATA_DIR / "corpus_paragraphs.parquet"
CHUNKS_PARQUET = DATA_DIR / "corpus_chunks.parquet"
OPEN_PATHS_PARQUET = DATA_DIR / "corpus_open_paths.parquet"
CHUNK_SIZE_PARQUET = DATA_DIR / "chunk_size_evidence.parquet"
EVAL_CSV = DATA_DIR / "eval_set.csv"
EVAL_MSHA_CSV = DATA_DIR / "eval_set_msha.csv"
# The answer pack is generated, not committed as an input: the written prose
# lives in raglab/answers.py and the retrieved context is recomputed against
# whatever index is loaded, then exported to artifacts/cached_answers.json.
CITATION_AUDIT_JSON = DATA_DIR / "citation_sample20.json"

# -- Corpus identity ---------------------------------------------------------
CORPUS_ID = "raglab-m05-v1"
CORPUS_RETRIEVED = "2026-09-02"
ECFR_DATE_PIN = "2025-08-01"
ECFR_FETCH_NOTE = (
    "Every eCFR URL is date-pinned to 2025-08-01 and fetched with "
    "`curl --compressed`; the API returns HTTP 406 without compression. "
    "Fetch once and commit - the developer portal serves a CAPTCHA wall to "
    "repeat callers, so a class of 30 must never hit it live."
)
FETCH_POLICY = (
    "The corpus is downloaded once by scripts/build_corpus.py --fetch and "
    "committed. Nothing in this notebook, in `npm run setup:procedures`, or in "
    "the classroom demo touches the network."
)

# -- The four layers ---------------------------------------------------------
LAYERS = {
    "regulation": (
        "The law",
        "What is legally required. 29 CFR 1910 (OSHA general industry) and "
        "30 CFR 56 (MSHA surface mines). Written as rules, not as instructions.",
    ),
    "site_procedure": (
        "The site procedure",
        "How one operator turns the law into a local program. The US Bureau of "
        "Reclamation FIST volumes are a real employer's own written procedures.",
    ),
    "equipment": (
        "The equipment manual",
        "What this specific machine needs: torque values, malfunction tables, "
        "service intervals. TM 9-6115-464-12, a 15 kW generator set.",
    ),
    "plain_language": (
        "The plain-language guide",
        "The regulator explaining its own rule to an employer. OSHA's booklets "
        "are the layer a technician can actually read.",
    ),
}

# -- Chunking ----------------------------------------------------------------
EMBEDDER = "sentence-transformers/all-MiniLM-L6-v2"
EMBEDDER_SHORT = "all-MiniLM-L6-v2"
EMBEDDING_DIM = 384
MODEL_TOKEN_WINDOW = 256          # MiniLM's hard wordpiece limit
TOKEN_BUDGET = 240                # 256 minus [CLS]/[SEP] and the heading prefix
CITATION_AUDIT_SCOPE = "29 CFR 1910"
CITATION_AUDIT_NOTE = (
    "The citation audit is scored on 29 CFR 1910 only. That is where the "
    "paragraph hierarchy exists: subparts J/N/O/Q/S nest six levels deep, so a "
    "label can be attached to the wrong ancestor. MSHA 30 CFR 56 numbers its "
    "rules flat - 56.14107 has no sub-paragraph tree to get wrong - so "
    "including it would dilute the measurement with rows that cannot fail."
)
CHUNKING_RULE = (
    "greedy packing of consecutive paragraphs from the same section into at "
    "most 240 MiniLM wordpiece tokens; a single paragraph over budget is split "
    "on sentence boundaries and keeps its parent citation"
)
INDEXED_TEXT_RULE = "<section heading>. <chunk text>"

# -- Retrieval ---------------------------------------------------------------
TOP_K_SHOWN = 4
TOP_K_SCORED = 5
TFIDF_PARAMS = dict(sublinear_tf=True, ngram_range=(1, 2), min_df=1,
                    stop_words="english", lowercase=True)

# -- Operating policy --------------------------------------------------------
REFUSAL_TAU = 0.48
REFUSAL_RULES = [
    "top-1 cosine similarity below 0.48",
    "the retrieved context incorporates a named consensus standard by "
    "reference AND the question asks for a specification, rating or value",
]
BOUNDARY = (
    "The assistant retrieves and drafts. It never authorizes work, never "
    "approves a lockout, and never answers a safety question from the model's "
    "own memory. A qualified person reads the cited passage and decides."
)

# -- Evaluation buckets ------------------------------------------------------
BUCKETS = {
    "A": ("Answerable, single section", 25),
    "B": ("Answerable, several sections", 10),
    "C": ("Numeric fact", 10),
    "D": ("Unanswerable, outside the corpus", 8),
    "E": ("Unanswerable, incorporated by reference", 7),
}
BUCKET_ORDER = ["A", "B", "C", "D", "E"]

# -- Frozen spike measurements ----------------------------------------------
# Recomputed live wherever the notebook can afford it; kept here so a drift in
# any live number is visible against the evidence the module was signed off on.
SPIKE = {
    "documents": 13,
    "raw_megabytes": 14.0,
    "words": 404_283,
    "chunks": 3222,
    "naive_citation_wrong": 0.823,
    "naive_citation_nonexistent": 0.774,
    "stateful_structurally_invalid": 0,
    "hand_audit": "20/20",
    "xref_total": 194,
    "xref_stateful": 0.918,
    "xref_naive": 0.129,
    "section_chunk_tokens_discarded": 0.654,
    "tfidf_hit1": 0.333, "tfidf_hit5": 0.578,
    "minilm_hit1": 0.489, "minilm_hit5": 0.800,
    "minilm_sec1": 0.733, "minilm_sec5": 0.889,
    "research_tfidf_hit1_claim": 0.90,
    "refuse_D": 0.875, "refuse_E": 0.857, "false_refusal": 0.044,
    "dup_shared_sections": 420,
    "dup_identical_sections": 329,
    "dup_mean_similarity": 0.987,
    "dup_minilm_cite1_before": 0.800, "dup_minilm_cite1_after": 0.267,
    "dup_tfidf_cite1_before": 0.667, "dup_tfidf_cite1_after": 0.033,
    "dup_minilm_text1_before": 0.800, "dup_minilm_text1_after": 0.767,
}

# -- Palette -----------------------------------------------------------------
COLOR_PRIMARY = "#636EFA"   # the deployed retriever, correct citations
COLOR_ALERT = "#EF553B"     # wrong citations, refusals we got wrong, damage
COLOR_ACCENT = "#00CC96"    # policy marks, the chosen threshold, correct refusals
COLOR_WARN = "#FFA15A"      # the comparison retriever, secondary series
COLOR_MUTED = "#B6B6C4"     # context series
COLOR_DARK = "#2A3F5F"      # emphasis text marks
PLOT_TEMPLATE = "plotly_white"

LAYER_COLORS = {
    "regulation": COLOR_PRIMARY,
    "site_procedure": COLOR_ACCENT,
    "equipment": COLOR_WARN,
    "plain_language": COLOR_MUTED,
}
BUCKET_COLORS = {
    "A": COLOR_PRIMARY, "B": "#8E96FB", "C": COLOR_ACCENT,
    "D": COLOR_WARN, "E": COLOR_ALERT,
}
RETRIEVER_COLORS = {"tfidf": COLOR_WARN, "minilm": COLOR_PRIMARY}


def layout(figure: go.Figure, title: str, height: int = 440) -> go.Figure:
    """One house style for every figure in the lab."""
    figure.update_layout(
        title=title,
        template=PLOT_TEMPLATE,
        height=height,
        margin=dict(l=80, r=50, t=90, b=80),
        font=dict(family="Arial", size=13, color="#20242B"),
        hoverlabel=dict(font_size=13),
    )
    return figure


def describe() -> str:
    return (
        f"raglab - corpus {CORPUS_ID} - retriever {EMBEDDER_SHORT} "
        f"({EMBEDDING_DIM}-dim cosine, float16)\n"
        f"chunking: {TOKEN_BUDGET}-token budget against a "
        f"{MODEL_TOKEN_WINDOW}-token model window, section-bounded\n"
        f"refusal: tau = {REFUSAL_TAU} plus the incorporation-by-reference rule\n"
        f"eCFR date pin: {ECFR_DATE_PIN} - corpus retrieved {CORPUS_RETRIEVED}\n"
        f"boundary: {BOUNDARY}"
    )
