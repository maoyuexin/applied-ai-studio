from __future__ import annotations

import json
import math
import os
import sys
import time
from pathlib import Path

import joblib
import numpy as np
import pandas as pd

from .config import MAX_QUESTION_CHARACTERS, REPOSITORY_ROOT
from .schemas import (
    AskResult,
    BucketRow,
    ChunkingEvidence,
    ChunkingRow,
    CitationAudit,
    ClaimCheck,
    CorpusDocument,
    CorpusLayer,
    CorpusView,
    DuplicateCorpusEvidence,
    EvaluationSetBucket,
    EvaluationSummary,
    ExcludedDocument,
    KeywordComparison,
    LeaderboardRow,
    LicenceGate,
    ModelInfo,
    PackagedQuestion,
    Passage,
    PhrasingEvidence,
    PolicyInfo,
    RefusalBucketRow,
    RefusalEvidence,
    RefusalSweepRow,
    RepresentationInfo,
)

# Nothing here reaches the network. The corpus is committed, the vectors are
# committed, and the sentence encoder is read from the local model cache that
# `npm run setup:procedures` fills. These two flags make that a guarantee rather
# than a hope: if the cache is missing, the service fails at start-up with a
# message that names the fix instead of quietly downloading during a class.
os.environ.setdefault("HF_HUB_OFFLINE", "1")
os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")

# Serving reuses the notebook's own retrieval and refusal code rather than a
# second copy that could drift from it. raglab.index.EmbedRetriever is the class
# that produced embeddings.npy, and raglab.evaluate.policy_signals /
# refusal_reason are the functions that decided every refusal in the evaluation.
# Both need the notebook package importable, so its directory goes on sys.path
# before anything loads.
NOTEBOOK_ROOT = REPOSITORY_ROOT / "notebooks" / "procedure-assistant"
if str(NOTEBOOK_ROOT) not in sys.path:
    sys.path.insert(0, str(NOTEBOOK_ROOT))

from raglab import config as lab, evaluate, index  # noqa: E402

ARTIFACT_FILES = (
    "chunks.parquet",
    "embeddings.npy",
    "index.joblib",
    "model_card.json",
    "evaluation.json",
    "operating_policy.json",
    "corpus_manifest.json",
    "cached_answers.json",
)

ANSWERED = "answered"
REFUSED_LOW = "refused_low_confidence"
REFUSED_IBR = "refused_incorporated_by_reference"

DISCUSSION_QID = "E01"

SCORE_NOTE = (
    "The score is how closely the passage reads like the question, on a scale of 0 to 1. "
    "It says the wording is close. It does not say the passage governs your machine, your "
    "site, or the work you are about to do."
)

ANSWER_NOTE_PACKAGED = (
    "This is one of the 20 packaged questions. The answer below was written from these "
    "passages and checked before it shipped. The assistant did not write anything new just now."
)

ANSWER_NOTE_PACKAGED_REFUSAL = (
    "This is one of the 20 packaged questions, and it is a refusal. Refusing is the correct "
    "outcome here, not a failure: the library does not hold the answer, so the assistant says "
    "so and points you at what does."
)

ANSWER_NOTE_UNPACKAGED = (
    "This question is not one of the 20 packaged questions, so there is no drafted answer for "
    "it. What you see below is exactly what the search returned. This demo never writes new "
    "prose while you wait - a qualified person reads the passages and decides."
)

ANSWER_NOTE_UNPACKAGED_REFUSAL = (
    "This question is not one of the 20 packaged questions. The refusal below came from the "
    "operating policy, not from drafted text: the search results did not clear the bar, so "
    "nothing is offered as an answer."
)

LABEL_UNPACKAGED_ANSWERED = "Passages found - no drafted answer for this question"

DECISION_LABELS = {
    ANSWERED: "Answered from the passages",
    REFUSED_LOW: "Refused - nothing in the library is close enough",
    REFUSED_IBR: "Refused - the rule points at a standard this library does not hold",
}

KEYWORD_AGREES = (
    "Keyword search returned the same passage as the deployed retriever for this question."
)
KEYWORD_DISAGREES = (
    "Keyword search returned a different passage. It matches words; the deployed retriever "
    "matches meaning, which is why the two disagree on questions a technician phrases in "
    "their own words."
)

PHRASING_LESSON = (
    "The same keyword retriever scored 90% or 31% on the same corpus, depending only on who "
    "wrote the questions. Questions generated from the passage text hand a keyword matcher "
    "the answer. Ask for the benchmark's questions before you believe its number."
)

REFUSAL_LESSON = (
    "A score rule alone cannot see bucket E. Those questions retrieve confidently - the rule "
    "that governs them really is in the library - but the rule points at an outside standard "
    "the library does not contain, so a confident-looking number nearby is not the answer. "
    "That is why there are two refusal rules and not one threshold."
)

DUPLICATE_LESSON = (
    "Adding a near-identical regulation beside the first left the right text being found and "
    "the wrong rule being cited on half the questions. Retrieval looked healthy while the "
    "citation - the part a technician acts on - collapsed. Never load two near-identical "
    "regulations into one library."
)

CITATION_LESSON = (
    "The structural check passed on a citation that was wrong. It grades the chunker against "
    "the chunker, so it can only catch labels that are malformed, never labels that are "
    "well-formed and attached to the wrong rule. The regulation's own cross-references were "
    "the independent ground truth that exposed it."
)

CLAIM_CATCHES = (
    "Every numeral in a packaged answer is checked back to a passage that was actually "
    "retrieved, so an invented torque figure or an invented distance cannot survive."
)
CLAIM_MISSES = (
    "It cannot tell whether that passage governs the question. A real number copied out of "
    "the wrong rule passes this check. Zero unsupported claims is not zero mistakes."
)

CHUNKING_LESSON = (
    "Whole-section chunks would have thrown away about two thirds of their words past the "
    "model's 256-token limit, silently and with no error message. The deployed policy packs "
    "to a 240-token budget, so nothing is cut off."
)

LICENCE_LESSON = (
    "Public domain is not the same as redistributable. Copyright status and distribution "
    "status are two separate gates: a US Government manual can carry no copyright at all and "
    "still be marked DISTRIBUTION STATEMENT C, which forbids public release. This library "
    "accepts Statement A only, verified in the document's own text."
)

LICENCE_GATE_NOTE = (
    "Page one of the equipment manual was read and searched for a distribution statement. "
    "Statement A - approved for public release - was found and no restrictive statement was."
)

PLAIN_RULE = (
    "Read the score on the closest passage. Below 0.48 the assistant refuses, because nothing "
    "in the library is close enough to the question. It also refuses when the rule it found "
    "points at an outside standard - ANSI, NFPA, ASTM - that the library does not contain, "
    "even when the score is high."
)

SHOULD_REFUSE_BUCKETS = ("D", "E")
BUCKET_SPREAD = ("A", "C", "B", "E", "D")


def _clean(value: object) -> str | None:
    """corpus_manifest.json carries a bare NaN for documents with no date pin."""
    if value is None:
        return None
    if isinstance(value, float) and math.isnan(value):
        return None
    text = str(value).strip()
    return text or None


def _first_sentence(text: str, limit: int = 165) -> str:
    stripped = " ".join(text.split())
    for stop in (". ", "; "):
        head, separator, _ = stripped.partition(stop)
        if separator and len(head) <= limit:
            return f"{head}."
    return stripped if len(stripped) <= limit else f"{stripped[:limit].rstrip()}..."


class StoredTfidf(index.TfidfRetriever):
    """The committed TF-IDF index, loaded rather than refitted.

    ``index.TfidfRetriever`` fits a vectorizer in its constructor. The service
    must never re-index: index.joblib already holds the fitted vectorizer and
    the passage matrix the notebook measured. Subclassing keeps the notebook's
    own ``scores`` and ``search`` while skipping the fit.
    """

    def __init__(self, chunks: pd.DataFrame, vectorizer, matrix) -> None:
        self.chunks = chunks.reset_index(drop=True)
        self.vectorizer = vectorizer
        self.matrix = matrix
        self.build_seconds = 0.0


class ProcedureRuntime:
    def __init__(self, artifact_dir: Path):
        self.artifact_dir = artifact_dir
        missing = [name for name in ARTIFACT_FILES if not (artifact_dir / name).exists()]
        if missing:
            raise FileNotFoundError(
                f"Missing procedure-assistant artifacts in {artifact_dir}: {', '.join(missing)}."
            )

        self.card = json.loads((artifact_dir / "model_card.json").read_text())
        self.evaluation = json.loads((artifact_dir / "evaluation.json").read_text())
        self.policy = json.loads((artifact_dir / "operating_policy.json").read_text())
        self.manifest = json.loads((artifact_dir / "corpus_manifest.json").read_text())
        self.pack = json.loads((artifact_dir / "cached_answers.json").read_text())

        # Fixed artifact paths only. Nothing here accepts a corpus path, an
        # index path, an upload, or any file a caller names.
        self.chunks = pd.read_parquet(artifact_dir / "chunks.parquet")
        vectors = np.load(artifact_dir / "embeddings.npy")
        stored = joblib.load(artifact_dir / "index.joblib")

        if len(vectors) != len(self.chunks):
            raise ValueError(
                f"embeddings.npy has {len(vectors)} rows and chunks.parquet has "
                f"{len(self.chunks)}. Re-run npm run prepare:procedures."
            )

        # The committed vectors, not a re-encode of the corpus. Only the
        # question is encoded at request time.
        self.retriever = index.EmbedRetriever(self.chunks, vectors=vectors)
        self.keyword = StoredTfidf(self.chunks, stored["vectorizer"], stored["matrix"])

        self.model_version = str(self.card["version"])
        self.tau = float(self.policy["refusal_threshold"])
        self.top_k = int(self.policy["top_k_shown"])
        self.boundary = str(self.policy["boundary"])

        self.layer_words = self.chunks.groupby("layer")["words"].sum().to_dict()
        self.doc_chunks = self.chunks.groupby("source").size().to_dict()
        self.doc_words = self.chunks.groupby("source")["words"].sum().to_dict()
        self.layer_of_document = {
            str(row["document"]): str(row["layer"]) for row in self.manifest["documents"]
        }

        self.answers = {str(row["qid"]): row for row in self.pack["answers"]}
        self.packaged_by_question = {
            self._key(str(row["question"])): str(row["qid"]) for row in self.pack["answers"]
        }
        self._questions = [self._packaged_question(row) for row in self.pack["answers"]]
        self._spread = self._spread_order(self._questions)

    # ── Helpers ─────────────────────────────────────────────────────────────

    @staticmethod
    def _key(question: str) -> str:
        return " ".join(question.split()).casefold()

    def _bucket_label(self, bucket: str) -> str:
        description, _ = lab.BUCKETS.get(bucket, (bucket, 0))
        return description

    def _layer_label(self, layer: str) -> str:
        label, _ = lab.LAYERS.get(layer, (layer, ""))
        return label

    def _layer_of(self, source: str) -> str:
        return self.layer_of_document.get(source, "regulation")

    @staticmethod
    def _spread_order(rows: list[PackagedQuestion]) -> list[PackagedQuestion]:
        """Round-robin across the buckets so a short list still spans them.

        The picker on the page asks for a handful of questions, and a list that
        followed the pack order would be all bucket A until it ran out. Cycling
        A, C, B, E, D puts a refusal - the incorporation-by-reference case -
        within the first four, which is the one every reader should see.
        """
        by_bucket: dict[str, list[PackagedQuestion]] = {}
        for row in rows:
            by_bucket.setdefault(row.bucket, []).append(row)
        order = [b for b in BUCKET_SPREAD if b in by_bucket]
        order += [b for b in by_bucket if b not in order]
        ordered: list[PackagedQuestion] = []
        while any(by_bucket[bucket] for bucket in order):
            for bucket in order:
                if by_bucket[bucket]:
                    ordered.append(by_bucket[bucket].pop(0))
        return ordered

    # ── Packaged questions ──────────────────────────────────────────────────

    def _packaged_question(self, row: dict) -> PackagedQuestion:
        status = str(row["status"])
        top = row["retrieved"][0]
        source = str(top["source"])
        layer = self._layer_of(source)
        answer = str(row["answer"])
        return PackagedQuestion(
            qid=str(row["qid"]),
            bucket=str(row["bucket"]),
            bucket_label=self._bucket_label(str(row["bucket"])),
            question=str(row["question"]),
            decision=status,
            is_refusal=status != ANSWERED,
            refusal_kind=None if status == ANSWERED else status,
            is_discussion_case=str(row["qid"]) == DISCUSSION_QID,
            top_score=float(row["top_score"]),
            above_threshold=float(row["top_score"]) >= self.tau,
            top_citation=str(top["citation"]),
            top_source=source,
            top_layer=layer,
            top_layer_label=self._layer_label(layer),
            passages=len(row["retrieved"]),
            answer_citations=[str(c) for c in row["citations"]],
            gold_citations=[str(c) for c in row["gold_citations"]],
            consult=_clean(row.get("consult")),
            teaching_note=_clean(row.get("teaching_note")),
            summary=_first_sentence(answer),
        )

    def questions(self, limit: int = 20) -> list[PackagedQuestion]:
        return self._spread[: max(1, min(limit, len(self._spread)))]

    # ── Asking one question ─────────────────────────────────────────────────

    def ask(self, question: str) -> AskResult:
        asked = question.strip()
        started = time.perf_counter()
        hits = self.retriever.search(asked, self.top_k)
        elapsed_ms = 1000 * (time.perf_counter() - started)

        passages = [
            self._passage(rank, position, score)
            for rank, (position, score) in enumerate(hits, 1)
        ]
        top_score = float(hits[0][1]) if hits else 0.0

        # The refusal decision is taken by the notebook's own policy code on the
        # index that is loaded, not copied out of the answer pack.
        signals = evaluate.policy_signals(
            self.retriever,
            pd.DataFrame([{"qid": "live", "bucket": "live", "question": asked}]),
        )
        decision = str(evaluate.refusal_reason(signals, self.tau)[0])
        standards = [str(name) for name in signals.iloc[0]["standards"]]

        qid = self.packaged_by_question.get(self._key(asked))
        packaged = self.answers.get(qid) if qid else None

        return AskResult(
            question=asked,
            characters=len(asked),
            words=len(asked.split()),
            passages=passages,
            top_score=round(top_score, 4),
            threshold=self.tau,
            above_threshold=top_score >= self.tau,
            score_note=SCORE_NOTE,
            retrieval_ms=round(elapsed_ms, 2),
            decision=decision,
            decision_label=(
                DECISION_LABELS[decision]
                if packaged is not None or decision != ANSWERED
                else LABEL_UNPACKAGED_ANSWERED
            ),
            decision_detail=self._decision_detail(decision, top_score, standards),
            rule_fired=self._rule_fired(decision),
            standards_named=standards,
            keyword_comparison=self.keyword_comparison(
                asked, passages[0].citation if passages else ""
            ),
            is_packaged=packaged is not None,
            qid=qid,
            bucket=str(packaged["bucket"]) if packaged else None,
            bucket_label=self._bucket_label(str(packaged["bucket"])) if packaged else None,
            answer=str(packaged["answer"]) if packaged else None,
            answer_citations=[str(c) for c in packaged["citations"]] if packaged else [],
            refusal_reason=_clean(packaged.get("refusal_reason")) if packaged else None,
            consult=_clean(packaged.get("consult")) if packaged else None,
            teaching_note=_clean(packaged.get("teaching_note")) if packaged else None,
            is_discussion_case=qid == DISCUSSION_QID,
            gold_citations=[str(c) for c in packaged["gold_citations"]] if packaged else [],
            answer_note=self._answer_note(packaged is not None, decision),
            reproduces_packaged_retrieval=(
                None
                if packaged is None
                else (
                    bool(passages)
                    and passages[0].citation == str(packaged["retrieved"][0]["citation"])
                    and round(top_score, 4) == round(float(packaged["top_score"]), 4)
                )
            ),
            model_version=self.model_version,
            boundary=self.boundary,
        )

    def keyword_comparison(self, question: str, deployed_citation: str) -> KeywordComparison:
        hits = self.keyword.search(question.strip(), 1)
        position, score = hits[0]
        chunk = self.chunks.iloc[position]
        agrees = str(chunk["citation"]) == deployed_citation
        return KeywordComparison(
            retriever="TF-IDF word counts",
            citation=str(chunk["citation"]),
            source=str(chunk["source"]),
            score=round(float(score), 4),
            agrees_with_deployed=agrees,
            note=KEYWORD_AGREES if agrees else KEYWORD_DISAGREES,
        )

    def _passage(self, rank: int, position: int, score: float) -> Passage:
        chunk = self.chunks.iloc[position]
        layer = str(chunk["layer"])
        return Passage(
            rank=rank,
            score=round(float(score), 4),
            citation=str(chunk["citation"]),
            citations=[str(c) for c in chunk["citations"]],
            chunk_id=str(chunk["chunk_id"]),
            doc_id=str(chunk["doc_id"]),
            source=str(chunk["source"]),
            source_title=str(chunk["source_title"]),
            section=str(chunk["section"]),
            layer=layer,
            layer_label=self._layer_label(layer),
            text=str(chunk["text"]),
            words=int(chunk["words"]),
            above_threshold=float(score) >= self.tau,
        )

    def _rule_fired(self, decision: str) -> str | None:
        if decision == REFUSED_LOW:
            return str(self.policy["rules"][0]["condition"])
        if decision == REFUSED_IBR:
            return str(self.policy["rules"][1]["condition"])
        return None

    def _decision_detail(self, decision: str, top_score: float, standards: list[str]) -> str:
        if decision == REFUSED_LOW:
            return (
                f"The closest passage scored {top_score:.2f}, below the {self.tau} line. Nothing "
                "in this library is close enough to the question. The library holds the law, one "
                "operator's own written procedures, one generator set manual and two OSHA "
                "booklets - if your question is about another machine or another vendor, it is "
                "not in here."
            )
        if decision == REFUSED_IBR:
            named = ", ".join(standards[:3]) if standards else "a consensus standard"
            return (
                f"The rule that came back names {named}, and that document is not in this "
                "library and cannot be - those standards are copyrighted and sold. A "
                "confident-looking number in a nearby passage is not the answer to this "
                "question. Obtain the named standard."
            )
        return (
            f"The closest passage scored {top_score:.2f}, above the {self.tau} line, and the "
            "rule it came from does not point at an outside standard. Read the passages and "
            "decide; the citation beside each one is what you look up."
        )

    @staticmethod
    def _answer_note(packaged: bool, decision: str) -> str:
        if packaged:
            return ANSWER_NOTE_PACKAGED if decision == ANSWERED else ANSWER_NOTE_PACKAGED_REFUSAL
        return ANSWER_NOTE_UNPACKAGED if decision == ANSWERED else ANSWER_NOTE_UNPACKAGED_REFUSAL

    # ── The corpus and its licences ─────────────────────────────────────────

    def _document(self, row: dict) -> CorpusDocument:
        name = str(row["document"])
        distribution = str(row["distribution"])
        statement_a = distribution.upper().startswith("DISTRIBUTION STATEMENT A")
        in_base = bool(row["in_base_corpus"])
        return CorpusDocument(
            document=name,
            title=str(row["title"]),
            publisher=str(row["publisher"]),
            layer=str(row["layer"]),
            license=str(row["license"]),
            distribution=distribution,
            is_statement_a=statement_a,
            redistributable=statement_a or distribution.lower().startswith("unrestricted"),
            words=int(row["words"]),
            megabytes=round(int(row["bytes"]) / 1e6, 2),
            chunks=int(self.doc_chunks.get(name, 0)),
            indexed_words=int(self.doc_words.get(name, 0)),
            retrieved=str(row["retrieved"]),
            date_pin=_clean(row.get("date_pin")),
            source_url=str(row["source_url"]),
            committed_file=str(row["committed_file"]),
            md5=str(row["md5"]),
            in_base_corpus=in_base,
            indexed_note=(
                f"{self.doc_chunks.get(name, 0):,} passages in the search index"
                if in_base
                else "Held back from the search index. It is the near-duplicate regulation the "
                "notebook adds only to show what a duplicate corpus does to citations."
            ),
        )

    def corpus_view(self) -> CorpusView:
        documents = [self._document(row) for row in self.manifest["documents"]]
        indexed = int(self.chunks.shape[0])
        layers: list[CorpusLayer] = []
        for key, (label, description) in lab.LAYERS.items():
            items = [document for document in documents if document.layer == key]
            chunks = sum(document.chunks for document in items)
            layers.append(
                CorpusLayer(
                    layer=key,
                    label=label,
                    description=description,
                    documents=len(items),
                    words=sum(document.words for document in items),
                    megabytes=round(sum(document.megabytes for document in items), 2),
                    chunks=chunks,
                    share_of_chunks=round(chunks / indexed, 4) if indexed else 0.0,
                    items=items,
                )
            )

        gate = self.evaluation["corpus"]["licence_gate_tm_9_6115_464_12"]
        return CorpusView(
            corpus=str(self.manifest["corpus"]),
            retrieved=str(self.manifest["retrieved"]),
            date_pin=str(self.manifest["ecfr_date_pin"]),
            licence_rule=str(self.manifest["licence_rule"]),
            licence_lesson=LICENCE_LESSON,
            fetch_policy=str(self.evaluation["corpus"]["fetch_policy"]),
            documents=len(documents),
            documents_indexed=sum(1 for document in documents if document.in_base_corpus),
            chunks=indexed,
            words=sum(document.words for document in documents),
            layers=layers,
            excluded=[
                ExcludedDocument(
                    document=str(row["document"]),
                    why_excluded=str(row["why_excluded"]),
                    lesson=str(row["lesson"]),
                )
                for row in self.manifest["excluded"]
            ],
            licence_gate=LicenceGate(
                document="TM 9-6115-464-12",
                naive_matches=int(gate["naive_matches"]),
                normalised_matches=int(gate["normalised_matches"]),
                statement_a_present=bool(gate["statement_a_present"]),
                restrictive_statement_present=bool(gate["restrictive_statement_present"]),
                destruction_notice=bool(gate["destruction_notice"]),
                verdict=str(gate["verdict"]),
                note=LICENCE_GATE_NOTE,
            ),
            boundary=self.boundary,
        )

    # ── Model card and evidence ─────────────────────────────────────────────

    def _leaderboard(self) -> list[LeaderboardRow]:
        deployed = str(self.card["measured"]["deployed_retriever"]["Retriever"])
        return [
            LeaderboardRow(
                retriever=str(row["Retriever"]),
                questions=int(row["Questions"]),
                hit_at_1=float(row["hit@1"]),
                hit_at_5=float(row["hit@5"]),
                coverage_at_5=float(row["coverage@5"]),
                sec_at_1=float(row["sec@1"]),
                sec_at_5=float(row["sec@5"]),
                query_time=str(row["Query time"]),
                is_deployed=str(row["Retriever"]) == deployed,
            )
            for row in self.evaluation["retrieval"]["leaderboard"]
        ]

    def _per_bucket(self) -> list[BucketRow]:
        rows = []
        for row in self.evaluation["retrieval"]["per_bucket"]:
            label = str(row["Bucket"])
            bucket = label.split(" - ")[0].strip()
            rows.append(
                BucketRow(
                    bucket=bucket,
                    label=label.split(" - ", 1)[-1].strip(),
                    questions=int(row["n"]),
                    tfidf_hit_at_1=float(row["TF-IDF word counts hit@1"]),
                    tfidf_hit_at_5=float(row["TF-IDF word counts hit@5"]),
                    minilm_hit_at_1=float(row["MiniLM sentence embeddings hit@1"]),
                    minilm_hit_at_5=float(row["MiniLM sentence embeddings hit@5"]),
                )
            )
        return rows

    def _refusal(self) -> RefusalEvidence:
        refusal = self.evaluation["refusal"]
        chosen = refusal["chosen"]
        return RefusalEvidence(
            tau=float(refusal["tau"]),
            rules=[str(rule) for rule in refusal["rules"]],
            by_bucket=[
                RefusalBucketRow(
                    bucket=bucket,
                    label=self._bucket_label(bucket),
                    questions=int(values["questions"]),
                    refused=int(values["refused"]),
                    rate=float(values["rate"]),
                    should_refuse=bucket in SHOULD_REFUSE_BUCKETS,
                )
                for bucket, values in chosen["by_bucket"].items()
            ],
            sweep=[
                RefusalSweepRow(
                    tau=float(row["tau"]),
                    correct_refusal_outside_corpus=str(row["Correct refusal, D"]),
                    correct_refusal_incorporated_by_reference=str(row["Correct refusal, E"]),
                    false_refusal=str(row["False refusal, A+B+C"]),
                    is_chosen=float(row["tau"]) == float(refusal["tau"]),
                )
                for row in refusal["sweep"]
            ],
            correct_refusal_outside_corpus=float(chosen["correct_refusal_D"]),
            correct_refusal_incorporated_by_reference=float(chosen["correct_refusal_E"]),
            false_refusal_rate=float(chosen["false_refusal_rate"]),
            false_refusals=[str(qid) for qid in chosen["false_refusals"]],
            missed_refusals=[str(qid) for qid in chosen["missed_refusals"]],
            lesson=REFUSAL_LESSON,
        )

    def _duplicate(self) -> DuplicateCorpusEvidence:
        duplicate = self.evaluation["duplicate_corpus"]
        similarity = duplicate["similarity"]
        minilm = duplicate["minilm"]
        tfidf = duplicate["tfidf"]
        collateral = duplicate["collateral"]
        return DuplicateCorpusEvidence(
            shared_section_numbers=int(similarity["shared_section_numbers"]),
            byte_identical=int(similarity["byte_identical"]),
            at_least_95_percent_similar=int(similarity["at_least_95_percent_similar"]),
            mean_similarity=float(similarity["mean_similarity"]),
            questions=int(minilm["questions"]),
            minilm_cite_hit_at_1_before=float(minilm["cite_hit@1_before"]),
            minilm_cite_hit_at_1_after=float(minilm["cite_hit@1_after"]),
            minilm_text_hit_at_1_before=float(minilm["text_hit@1_before"]),
            minilm_text_hit_at_1_after=float(minilm["text_hit@1_after"]),
            minilm_right_text_wrong_rule=float(minilm["right_text_wrong_rule@1_after"]),
            tfidf_cite_hit_at_1_before=float(tfidf["cite_hit@1_before"]),
            tfidf_cite_hit_at_1_after=float(tfidf["cite_hit@1_after"]),
            tfidf_right_text_wrong_rule=float(tfidf["right_text_wrong_rule@1_after"]),
            corpus_growth=float(collateral["corpus_growth"]),
            main_hit_at_5_before=float(
                collateral["before"]["main_hit@5"] if "before" in collateral
                else collateral["main_hit@5_before"]
            ),
            main_hit_at_5_after=float(
                collateral["after"]["main_hit@5"] if "after" in collateral
                else collateral["main_hit@5_after"]
            ),
            lesson=DUPLICATE_LESSON,
        )

    def _citations(self) -> CitationAudit:
        citations = self.evaluation["citations"]
        return CitationAudit(
            scope=str(citations["scope"]),
            scope_note=str(citations["scope_note"]),
            labelled_paragraphs=int(citations["labelled_paragraphs"]),
            naive_citation_wrong=str(citations["naive_citation_wrong"]),
            naive_citation_nonexistent=str(citations["naive_citation_nonexistent"]),
            stateful_structurally_invalid=int(citations["stateful_structurally_invalid"]),
            structural_check_is_a_self_check=str(citations["structural_check_is_a_self_check"]),
            internal_cross_references=int(citations["internal_cross_references"]),
            cross_references_resolved_stateful=float(citations["cross_references_resolved_stateful"]),
            cross_references_resolved_naive=float(citations["cross_references_resolved_naive"]),
            hand_audited=str(citations["hand_audited"]),
            lesson=CITATION_LESSON,
        )

    def _chunking(self) -> ChunkingEvidence:
        chunking = self.evaluation["chunking"]
        return ChunkingEvidence(
            rule=str(chunking["rule"]),
            token_budget=int(chunking["token_budget"]),
            model_token_window=int(chunking["model_token_window"]),
            indexed_text=str(chunking["indexed_text"]),
            sizes=[
                ChunkingRow(
                    policy=str(row["Chunking policy"]),
                    chunks=int(row["Chunks"]),
                    words_median=int(row["Words (median)"]),
                    tokens_median=int(row["Tokens (median)"]),
                    tokens_max=int(row["Tokens (max)"]),
                    chunks_over_window=int(row["Chunks over 256 tokens"]),
                    tokens_discarded=str(row["Tokens discarded"]),
                    is_deployed="deployed" in str(row["Chunking policy"]),
                )
                for row in chunking["size_comparison"]
            ],
            lesson=CHUNKING_LESSON,
        )

    def _evaluation_summary(self) -> EvaluationSummary:
        retrieval = self.evaluation["retrieval"]
        phrasing = retrieval["question_phrasing"]
        claims = self.evaluation["unsupported_claim_check"]
        gold = retrieval["gold_validation"]
        return EvaluationSummary(
            questions_scored=int(retrieval["questions_scored"]),
            leaderboard=self._leaderboard(),
            per_bucket=self._per_bucket(),
            question_phrasing=PhrasingEvidence(
                research_tfidf_hit_at_1=float(phrasing["research_tfidf_hit1"]),
                technician_tfidf_hit_at_1=float(phrasing["technician_tfidf_hit1"]),
                technician_minilm_hit_at_1=float(phrasing["technician_minilm_hit1"]),
                note=str(phrasing.get("note", "No additional note was recorded in this artifact.")),
                lesson=PHRASING_LESSON,
            ),
            refusal=self._refusal(),
            duplicate_corpus=self._duplicate(),
            citations=self._citations(),
            chunking=self._chunking(),
            unsupported_claim_check=ClaimCheck(
                answers_checked=int(claims["answers_checked"]),
                refusals=int(claims["refusals"]),
                numerals_checked=int(claims["numerals_checked"]),
                unsupported_numerals=int(claims["unsupported_numerals"]),
                citations_not_retrieved=int(claims["citations_not_retrieved"]),
                what_it_catches=CLAIM_CATCHES,
                what_it_misses=CLAIM_MISSES,
            ),
            gold_citations_checked=int(gold["gold_citations"]),
            gold_citations_missing=int(gold["missing_from_the_chunk_table"]),
        )

    def model_info(self) -> ModelInfo:
        representation = self.card["how_it_represents_text"]
        return ModelInfo(
            name=str(self.card["name"]),
            version=self.model_version,
            generated=str(self.card["generated"]),
            what_it_does=str(self.card["what_it_does"]),
            what_it_does_not_do=[str(line) for line in self.card["what_it_does_not_do"]],
            boundary=self.boundary,
            intended_users=str(self.card["intended_users"]),
            known_limits=[str(line) for line in self.card["known_limits"]],
            max_question_characters=MAX_QUESTION_CHARACTERS,
            score_note=SCORE_NOTE,
            corpus=self.corpus_view(),
            representation=RepresentationInfo(
                embedder=str(representation["embedder"]),
                dimensions=int(representation["dimensions"]),
                similarity=str(representation["similarity"]),
                storage=str(representation["storage"]),
                chunking=str(representation["chunking"]),
                comparison_retriever=str(representation["comparison_retriever"]),
            ),
            policy=PolicyInfo(
                refusal_threshold=self.tau,
                rules=[{str(k): str(v) for k, v in rule.items()} for rule in self.policy["rules"]],
                top_k_shown=self.top_k,
                service_must=[str(line) for line in self.policy["service_must"]],
                boundary=self.boundary,
                plain_rule=PLAIN_RULE,
            ),
            evaluation=self._evaluation_summary(),
            evaluation_set=[
                EvaluationSetBucket(
                    bucket=bucket,
                    description=str(values["description"]),
                    questions=int(values["questions"]),
                )
                for bucket, values in self.card["evaluation_set"]["buckets"].items()
            ],
            evaluation_set_written_by=str(self.card["evaluation_set"]["written_by"]),
            packaged_questions=len(self._questions),
            packaged_refusals=sum(1 for row in self._questions if row.is_refusal),
            environment={
                str(key): str(value) for key, value in self.evaluation["environment"].items()
            },
        )

    # ── Readiness ───────────────────────────────────────────────────────────

    def artifact_readiness(self) -> dict[str, bool]:
        return {name: (self.artifact_dir / name).exists() for name in ARTIFACT_FILES}
