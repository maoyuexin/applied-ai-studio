export type ComplaintRoute = "auto_route" | "human_triage";

export interface ComplaintTeamProbability {
  team: string;
  description: string;
  probability: number;
  is_predicted: boolean;
}

export interface ComplaintRoutingWord {
  word: string;
  push: number;
}

export interface ComplaintClassification {
  predicted_team: string;
  predicted_team_description: string;
  confidence: number;
  threshold: number;
  route: ComplaintRoute;
  route_label: string;
  route_rule: string;
  route_action: string;
  probabilities: ComplaintTeamProbability[];
  routing_words: ComplaintRoutingWord[];
  routing_words_note: string;
  characters: number;
  words: number;
  is_packaged_complaint: boolean;
  known_team: string | null;
  correct: boolean | null;
  outcome_note: string;
  model_version: string;
  score_note: string;
  boundary: string;
}

export interface ComplaintPackaged {
  scenario_id: string;
  scenario_label: string;
  learning_note: string;
  complaint_id: string;
  date_received: string;
  narrative: string;
  characters: number;
  issue: string;
  known_team: string;
  predicted_team: string;
  confidence: number;
  route: ComplaintRoute;
  route_label: string;
  correct: boolean;
  curated: boolean;
  is_misroute_example: boolean;
  top_words: ComplaintRoutingWord[];
}

export interface ComplaintQueueItem {
  complaint_id: string;
  date_received: string;
  issue: string;
  excerpt: string;
  narrative: string;
  characters: number;
  predicted_team: string;
  confidence: number;
  route: ComplaintRoute;
  known_team: string;
  correct: boolean;
  curated: boolean;
  is_misroute_example: boolean;
}

export interface ComplaintTeamQueue {
  team: string;
  description: string;
  complaints: number;
  share_of_auto_routed: number;
  misrouted: number;
  items: ComplaintQueueItem[];
}

export interface ComplaintTriageQueue {
  complaints: number;
  share: number;
  workload_note: string;
  action: string;
  items: ComplaintQueueItem[];
}

export interface ComplaintFrozenTestRouting {
  complaints: number;
  auto_routed: number;
  coverage: number;
  accuracy_among_auto_routed: number;
  triage_rows: number;
  triage_share: number;
  accuracy_among_triage: number;
  note: string;
}

export interface ComplaintQueueSummary {
  packaged_complaints: number;
  auto_routed: number;
  sent_to_triage: number;
  triage_share: number;
  misroutes_in_auto_routed: number;
  threshold: number;
  rule: string;
  plain_rule: string;
  workload_note: string;
  selection_note: string;
  boundary: string;
  boundary_detail: string;
}

export interface ComplaintQueueBoard {
  summary: ComplaintQueueSummary;
  test: ComplaintFrozenTestRouting;
  teams: ComplaintTeamQueue[];
  triage: ComplaintTriageQueue;
}

export interface ComplaintTeamInfo {
  name: string;
  description: string;
  precision: number;
  recall: number;
  f1: number;
  complaints_in_test: number;
}

export interface ComplaintPerTeamRow {
  team: string;
  precision: number;
  recall: number;
  f1: number;
  complaints: number;
}

export interface ComplaintRepresentationResult {
  model: string;
  trained_on: number;
  representation: string;
  validation_accuracy: number;
  validation_macro_f1: number;
  fit_seconds: number;
  explanation_available: string;
}

export interface ComplaintDedupeTeamShare {
  team: string;
  share_removed: number;
}

export interface ComplaintThresholdSweepRow {
  threshold: number;
  coverage: number;
  accuracy_among_auto_routed: number;
  triage_share: number;
  overall_accuracy: number;
  is_chosen: boolean;
}

export interface ComplaintModelInfo {
  model_name: string;
  model_version: string;
  framework: string;
  packaging: string;
  estimator: string;
  task: string;
  input: string;
  output: string;
  intended_use: string;
  score_note: string;
  max_narrative_characters: number;
  representation: {
    kind: string;
    settings: {
      ngram_range: number[];
      min_df: number;
      max_features: number;
      sublinear_tf: boolean;
      strip_accents: string;
    };
    columns_learned: number;
    why_not_a_transformer: string;
  };
  explanation: {
    mechanism: string;
    output: string;
    note: string;
    plain_mechanism: string;
  };
  teams: ComplaintTeamInfo[];
  per_team: ComplaintPerTeamRow[];
  confusion: { labels: string[]; rows_are_true_team: boolean; matrix: number[][] };
  dataset: {
    name: string;
    publisher: string;
    home: string;
    retrieved: string;
    rights: string;
    window: string;
    row_meaning: string;
    narratives: string;
    dedupe_rule: string;
    class_cap: string;
    split_counts: Record<string, number>;
  };
  test_metrics: {
    accuracy: number;
    macro_f1: number;
    threshold: number;
    complaints: number;
    auto_routed: number;
    coverage: number;
    accuracy_among_auto_routed: number;
    triage_rows: number;
    triage_share: number;
    accuracy_among_triage: number;
    baseline_accuracy: number;
    baseline_macro_f1: number;
    baseline_note: string;
    note: string;
  };
  policy: {
    name: string;
    rule: string;
    plain_rule: string;
    confidence_threshold: number;
    confidence_definition: string;
    selected_on: string;
    auto_route_when: string;
    auto_route_action: string;
    auto_route_coverage: number;
    auto_route_accuracy: number;
    triage_when: string;
    triage_action: string;
    triage_share: number;
    triage_complaints: number;
    fallback: string;
    boundary: string;
    boundary_detail: string;
  };
  threshold_sweep: ComplaintThresholdSweepRow[];
  representation_comparison: {
    design: string;
    embedding_model: string;
    embedding_facts: Record<string, string>;
    results: ComplaintRepresentationResult[];
    winner: string;
    accuracy_gap: number;
    lesson: string;
  };
  dedupe: {
    rule: string;
    mapped_rows_in_window: number;
    rows_removed: number;
    share_removed: number;
    distinct_narratives: number;
    narratives_filed_more_than_once: number;
    share_removed_by_team: ComplaintDedupeTeamShare[];
    test_rows_seen_verbatim_in_train: number;
    inflated_test_accuracy: number;
    honest_test_accuracy: number;
    inflation_percentage_points: number;
    lesson: string;
  };
  limitations: string[];
  excluded_uses: string[];
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

export function getComplaintsModel(): Promise<ComplaintModelInfo> {
  return requestJson<ComplaintModelInfo>("/api/complaints/model");
}

export function getComplaintsSamples(limit = 12): Promise<ComplaintPackaged[]> {
  return requestJson<ComplaintPackaged[]>(`/api/complaints/samples?limit=${limit}`);
}

export function getComplaintsQueues(limit = 60): Promise<ComplaintQueueBoard> {
  return requestJson<ComplaintQueueBoard>(`/api/complaints/queues?limit=${limit}`);
}

export function classifyComplaint(narrative: string): Promise<ComplaintClassification> {
  return requestJson<ComplaintClassification>("/api/complaints/classify", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ narrative }),
  });
}
