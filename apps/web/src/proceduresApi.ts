export type ProcedureDecision =
  | "answered"
  | "refused_low_confidence"
  | "refused_incorporated_by_reference";

export interface ProcedurePassage {
  rank: number;
  score: number;
  citation: string;
  citations: string[];
  chunk_id: string;
  doc_id: string;
  source: string;
  source_title: string;
  section: string;
  layer: string;
  layer_label: string;
  text: string;
  words: number;
  above_threshold: boolean;
}

export interface ProcedureKeywordComparison {
  retriever: string;
  citation: string;
  source: string;
  score: number;
  agrees_with_deployed: boolean;
  note: string;
}

export interface ProcedureAnswer {
  question: string;
  characters: number;
  words: number;

  passages: ProcedurePassage[];
  top_score: number;
  threshold: number;
  above_threshold: boolean;
  score_note: string;
  retrieval_ms: number;

  decision: ProcedureDecision;
  decision_label: string;
  decision_detail: string;
  rule_fired: string | null;
  standards_named: string[];
  keyword_comparison: ProcedureKeywordComparison;

  is_packaged: boolean;
  qid: string | null;
  bucket: string | null;
  bucket_label: string | null;
  answer: string | null;
  answer_citations: string[];
  refusal_reason: string | null;
  consult: string | null;
  teaching_note: string | null;
  is_discussion_case: boolean;
  gold_citations: string[];
  answer_note: string;
  reproduces_packaged_retrieval: boolean | null;

  model_version: string;
  boundary: string;
}

export interface ProcedureQuestion {
  qid: string;
  bucket: string;
  bucket_label: string;
  question: string;
  decision: ProcedureDecision;
  is_refusal: boolean;
  refusal_kind: string | null;
  is_discussion_case: boolean;
  top_score: number;
  above_threshold: boolean;
  top_citation: string;
  top_source: string;
  top_layer: string;
  top_layer_label: string;
  passages: number;
  answer_citations: string[];
  gold_citations: string[];
  consult: string | null;
  teaching_note: string | null;
  summary: string;
}

export interface ProcedureDocument {
  document: string;
  title: string;
  publisher: string;
  layer: string;
  license: string;
  distribution: string;
  is_statement_a: boolean;
  redistributable: boolean;
  words: number;
  megabytes: number;
  chunks: number;
  indexed_words: number;
  retrieved: string;
  date_pin: string | null;
  source_url: string;
  committed_file: string;
  md5: string;
  in_base_corpus: boolean;
  indexed_note: string;
}

export interface ProcedureLayer {
  layer: string;
  label: string;
  description: string;
  documents: number;
  words: number;
  megabytes: number;
  chunks: number;
  share_of_chunks: number;
  items: ProcedureDocument[];
}

export interface ProcedureCorpus {
  corpus: string;
  retrieved: string;
  date_pin: string;
  licence_rule: string;
  licence_lesson: string;
  fetch_policy: string;
  documents: number;
  documents_indexed: number;
  chunks: number;
  words: number;
  layers: ProcedureLayer[];
  excluded: { document: string; why_excluded: string; lesson: string }[];
  licence_gate: {
    document: string;
    naive_matches: number;
    normalised_matches: number;
    statement_a_present: boolean;
    restrictive_statement_present: boolean;
    destruction_notice: boolean;
    verdict: string;
    note: string;
  };
  boundary: string;
}

export interface ProcedureLeaderboardRow {
  retriever: string;
  questions: number;
  hit_at_1: number;
  hit_at_5: number;
  coverage_at_5: number;
  sec_at_1: number;
  sec_at_5: number;
  query_time: string;
  is_deployed: boolean;
}

export interface ProcedureBucketRow {
  bucket: string;
  label: string;
  questions: number;
  tfidf_hit_at_1: number;
  tfidf_hit_at_5: number;
  minilm_hit_at_1: number;
  minilm_hit_at_5: number;
}

export interface ProcedureRefusalBucketRow {
  bucket: string;
  label: string;
  questions: number;
  refused: number;
  rate: number;
  should_refuse: boolean;
}

export interface ProcedureRefusalSweepRow {
  tau: number;
  correct_refusal_outside_corpus: string;
  correct_refusal_incorporated_by_reference: string;
  false_refusal: string;
  is_chosen: boolean;
}

export interface ProcedureChunkingRow {
  policy: string;
  chunks: number;
  words_median: number;
  tokens_median: number;
  tokens_max: number;
  chunks_over_window: number;
  tokens_discarded: string;
  is_deployed: boolean;
}

export interface ProcedureEvaluation {
  questions_scored: number;
  leaderboard: ProcedureLeaderboardRow[];
  per_bucket: ProcedureBucketRow[];
  question_phrasing: {
    research_tfidf_hit_at_1: number;
    technician_tfidf_hit_at_1: number;
    technician_minilm_hit_at_1: number;
    note: string;
    lesson: string;
  };
  refusal: {
    tau: number;
    rules: string[];
    by_bucket: ProcedureRefusalBucketRow[];
    sweep: ProcedureRefusalSweepRow[];
    correct_refusal_outside_corpus: number;
    correct_refusal_incorporated_by_reference: number;
    false_refusal_rate: number;
    false_refusals: string[];
    missed_refusals: string[];
    lesson: string;
  };
  duplicate_corpus: {
    shared_section_numbers: number;
    byte_identical: number;
    at_least_95_percent_similar: number;
    mean_similarity: number;
    questions: number;
    minilm_cite_hit_at_1_before: number;
    minilm_cite_hit_at_1_after: number;
    minilm_text_hit_at_1_before: number;
    minilm_text_hit_at_1_after: number;
    minilm_right_text_wrong_rule: number;
    tfidf_cite_hit_at_1_before: number;
    tfidf_cite_hit_at_1_after: number;
    tfidf_right_text_wrong_rule: number;
    corpus_growth: number;
    main_hit_at_5_before: number;
    main_hit_at_5_after: number;
    lesson: string;
  };
  citations: {
    scope: string;
    scope_note: string;
    labelled_paragraphs: number;
    naive_citation_wrong: string;
    naive_citation_nonexistent: string;
    stateful_structurally_invalid: number;
    structural_check_is_a_self_check: string;
    internal_cross_references: number;
    cross_references_resolved_stateful: number;
    cross_references_resolved_naive: number;
    hand_audited: string;
    lesson: string;
  };
  chunking: {
    rule: string;
    token_budget: number;
    model_token_window: number;
    indexed_text: string;
    sizes: ProcedureChunkingRow[];
    lesson: string;
  };
  unsupported_claim_check: {
    answers_checked: number;
    refusals: number;
    numerals_checked: number;
    unsupported_numerals: number;
    citations_not_retrieved: number;
    what_it_catches: string;
    what_it_misses: string;
  };
  gold_citations_checked: number;
  gold_citations_missing: number;
}

export interface ProcedureModelInfo {
  name: string;
  version: string;
  generated: string;
  what_it_does: string;
  what_it_does_not_do: string[];
  boundary: string;
  intended_users: string;
  known_limits: string[];
  max_question_characters: number;
  score_note: string;
  corpus: ProcedureCorpus;
  representation: {
    embedder: string;
    dimensions: number;
    similarity: string;
    storage: string;
    chunking: string;
    comparison_retriever: string;
  };
  policy: {
    refusal_threshold: number;
    rules: Record<string, string>[];
    top_k_shown: number;
    service_must: string[];
    boundary: string;
    plain_rule: string;
  };
  evaluation: ProcedureEvaluation;
  evaluation_set: { bucket: string; description: string; questions: number }[];
  evaluation_set_written_by: string;
  packaged_questions: number;
  packaged_refusals: number;
  environment: Record<string, string>;
}

async function requestJson<T>(url: string, options?: RequestInit): Promise<T> {
  const response = await fetch(url, options);
  if (!response.ok) {
    const payload = (await response.json().catch(() => null)) as
      | { detail?: string | { msg?: string }[]; error?: string }
      | null;
    const detail = Array.isArray(payload?.detail)
      ? payload.detail
        .map((item) => item.msg?.replace(/^Value error, /, ""))
        .filter(Boolean)
        .join("; ")
      : payload?.detail;
    throw new Error(detail ?? payload?.error ?? `Request failed with ${response.status}.`);
  }
  return response.json() as Promise<T>;
}

export function getProceduresModel(): Promise<ProcedureModelInfo> {
  return requestJson<ProcedureModelInfo>("/api/procedures/model");
}

export function getProceduresQuestions(limit = 20): Promise<ProcedureQuestion[]> {
  return requestJson<ProcedureQuestion[]>(`/api/procedures/questions?limit=${limit}`);
}

export function getProceduresCorpus(): Promise<ProcedureCorpus> {
  return requestJson<ProcedureCorpus>("/api/procedures/corpus");
}

export function askProcedureQuestion(question: string): Promise<ProcedureAnswer> {
  return requestJson<ProcedureAnswer>("/api/procedures/ask", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ question }),
  });
}
