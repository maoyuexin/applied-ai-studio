from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from .config import MAX_QUESTION_CHARACTERS


Decision = Literal["answered", "refused_low_confidence", "refused_incorporated_by_reference"]


class AskRequest(BaseModel):
    """One question, as plain text.

    Nothing else is accepted: no document to search, no file to upload, no model
    name, no threshold. The blank check and the length cap are enforced here so
    a caller gets one sentence back that says what to change, rather than a
    schema error about string bounds.
    """

    model_config = ConfigDict(extra="forbid")

    question: str = Field(min_length=1, max_length=MAX_QUESTION_CHARACTERS)

    @field_validator("question", mode="before")
    @classmethod
    def check_question(cls, value: object) -> object:
        # A "before" validator runs ahead of the length constraint above, so
        # both rejections carry a message a beginner can act on.
        if not isinstance(value, str):
            return value
        if not value.strip():
            raise ValueError(
                "There is no question to look up. Type a question, or pick one of the "
                "packaged questions; the assistant never searches on an empty line."
            )
        if len(value) > MAX_QUESTION_CHARACTERS:
            raise ValueError(
                f"This question is {len(value):,} characters long. This demo reads up to "
                f"{MAX_QUESTION_CHARACTERS:,}. Ask the shorter question you actually have; "
                "pasting a whole procedure does not search it."
            )
        return value


# ── Retrieved passages ──────────────────────────────────────────────────────

class Passage(BaseModel):
    rank: int
    score: float
    citation: str
    citations: list[str]
    chunk_id: str
    doc_id: str
    source: str
    source_title: str
    section: str
    layer: str
    layer_label: str
    text: str
    words: int
    above_threshold: bool


class KeywordComparison(BaseModel):
    """What the committed TF-IDF index returns for the same question."""

    retriever: str
    citation: str
    source: str
    score: float
    agrees_with_deployed: bool
    note: str


class AskResult(BaseModel):
    question: str
    characters: int
    words: int

    passages: list[Passage]
    top_score: float
    threshold: float
    above_threshold: bool
    score_note: str
    retrieval_ms: float

    decision: Decision
    decision_label: str
    decision_detail: str
    rule_fired: str | None
    standards_named: list[str]

    keyword_comparison: KeywordComparison

    # Filled in only when the question is one of the 20 packaged questions.
    # A typed question gets passages and no drafted prose.
    is_packaged: bool
    qid: str | None
    bucket: str | None
    bucket_label: str | None
    answer: str | None
    answer_citations: list[str]
    refusal_reason: str | None
    consult: str | None
    teaching_note: str | None
    is_discussion_case: bool
    gold_citations: list[str]
    answer_note: str
    reproduces_packaged_retrieval: bool | None

    model_version: str
    boundary: str


class PackagedQuestion(BaseModel):
    qid: str
    bucket: str
    bucket_label: str
    question: str
    decision: Decision
    is_refusal: bool
    refusal_kind: str | None
    is_discussion_case: bool
    top_score: float
    above_threshold: bool
    top_citation: str
    top_source: str
    top_layer: str
    top_layer_label: str
    passages: int
    answer_citations: list[str]
    gold_citations: list[str]
    consult: str | None
    teaching_note: str | None
    summary: str


# ── The corpus and its licences ─────────────────────────────────────────────

class CorpusDocument(BaseModel):
    document: str
    title: str
    publisher: str
    layer: str
    license: str
    distribution: str
    is_statement_a: bool
    redistributable: bool
    words: int
    megabytes: float
    chunks: int
    indexed_words: int
    retrieved: str
    date_pin: str | None
    source_url: str
    committed_file: str
    md5: str
    in_base_corpus: bool
    indexed_note: str


class CorpusLayer(BaseModel):
    layer: str
    label: str
    description: str
    documents: int
    words: int
    megabytes: float
    chunks: int
    share_of_chunks: float
    items: list[CorpusDocument]


class ExcludedDocument(BaseModel):
    document: str
    why_excluded: str
    lesson: str


class LicenceGate(BaseModel):
    document: str
    naive_matches: int
    normalised_matches: int
    statement_a_present: bool
    restrictive_statement_present: bool
    destruction_notice: bool
    verdict: str
    note: str


class CorpusView(BaseModel):
    corpus: str
    retrieved: str
    date_pin: str
    licence_rule: str
    licence_lesson: str
    fetch_policy: str
    documents: int
    documents_indexed: int
    chunks: int
    words: int
    layers: list[CorpusLayer]
    excluded: list[ExcludedDocument]
    licence_gate: LicenceGate
    boundary: str


# ── Model card and evidence ─────────────────────────────────────────────────

class LeaderboardRow(BaseModel):
    retriever: str
    questions: int
    hit_at_1: float
    hit_at_5: float
    coverage_at_5: float
    sec_at_1: float
    sec_at_5: float
    query_time: str
    is_deployed: bool


class BucketRow(BaseModel):
    bucket: str
    label: str
    questions: int
    tfidf_hit_at_1: float
    tfidf_hit_at_5: float
    minilm_hit_at_1: float
    minilm_hit_at_5: float


class PhrasingEvidence(BaseModel):
    research_tfidf_hit_at_1: float
    technician_tfidf_hit_at_1: float
    technician_minilm_hit_at_1: float
    note: str
    lesson: str


class RefusalBucketRow(BaseModel):
    bucket: str
    label: str
    questions: int
    refused: int
    rate: float
    should_refuse: bool


class RefusalSweepRow(BaseModel):
    tau: float
    correct_refusal_outside_corpus: str
    correct_refusal_incorporated_by_reference: str
    false_refusal: str
    is_chosen: bool


class RefusalEvidence(BaseModel):
    tau: float
    rules: list[str]
    by_bucket: list[RefusalBucketRow]
    sweep: list[RefusalSweepRow]
    correct_refusal_outside_corpus: float
    correct_refusal_incorporated_by_reference: float
    false_refusal_rate: float
    false_refusals: list[str]
    missed_refusals: list[str]
    lesson: str


class DuplicateCorpusEvidence(BaseModel):
    shared_section_numbers: int
    byte_identical: int
    at_least_95_percent_similar: int
    mean_similarity: float
    questions: int
    minilm_cite_hit_at_1_before: float
    minilm_cite_hit_at_1_after: float
    minilm_text_hit_at_1_before: float
    minilm_text_hit_at_1_after: float
    minilm_right_text_wrong_rule: float
    tfidf_cite_hit_at_1_before: float
    tfidf_cite_hit_at_1_after: float
    tfidf_right_text_wrong_rule: float
    corpus_growth: float
    main_hit_at_5_before: float
    main_hit_at_5_after: float
    lesson: str


class CitationAudit(BaseModel):
    scope: str
    scope_note: str
    labelled_paragraphs: int
    naive_citation_wrong: str
    naive_citation_nonexistent: str
    stateful_structurally_invalid: int
    structural_check_is_a_self_check: str
    internal_cross_references: int
    cross_references_resolved_stateful: float
    cross_references_resolved_naive: float
    hand_audited: str
    lesson: str


class ClaimCheck(BaseModel):
    answers_checked: int
    refusals: int
    numerals_checked: int
    unsupported_numerals: int
    citations_not_retrieved: int
    what_it_catches: str
    what_it_misses: str


class ChunkingRow(BaseModel):
    policy: str
    chunks: int
    words_median: int
    tokens_median: int
    tokens_max: int
    chunks_over_window: int
    tokens_discarded: str
    is_deployed: bool


class ChunkingEvidence(BaseModel):
    rule: str
    token_budget: int
    model_token_window: int
    indexed_text: str
    sizes: list[ChunkingRow]
    lesson: str


class EvaluationSummary(BaseModel):
    questions_scored: int
    leaderboard: list[LeaderboardRow]
    per_bucket: list[BucketRow]
    question_phrasing: PhrasingEvidence
    refusal: RefusalEvidence
    duplicate_corpus: DuplicateCorpusEvidence
    citations: CitationAudit
    chunking: ChunkingEvidence
    unsupported_claim_check: ClaimCheck
    gold_citations_checked: int
    gold_citations_missing: int


class RepresentationInfo(BaseModel):
    embedder: str
    dimensions: int
    similarity: str
    storage: str
    chunking: str
    comparison_retriever: str


class PolicyInfo(BaseModel):
    refusal_threshold: float
    rules: list[dict[str, str]]
    top_k_shown: int
    service_must: list[str]
    boundary: str
    plain_rule: str


class EvaluationSetBucket(BaseModel):
    bucket: str
    description: str
    questions: int


class ModelInfo(BaseModel):
    name: str
    version: str
    generated: str
    what_it_does: str
    what_it_does_not_do: list[str]
    boundary: str
    intended_users: str
    known_limits: list[str]
    max_question_characters: int
    score_note: str

    corpus: CorpusView
    representation: RepresentationInfo
    policy: PolicyInfo
    evaluation: EvaluationSummary
    evaluation_set: list[EvaluationSetBucket]
    evaluation_set_written_by: str
    packaged_questions: int
    packaged_refusals: int
    environment: dict[str, str]


class HealthResponse(BaseModel):
    status: str
    service: str
    model: str
    model_version: str
    corpus: str
    embedder: str
    chunks: int
    documents_indexed: int
    packaged_questions: int
    refusal_threshold: float
    artifacts: dict[str, bool]
