export type RecommendProtocol = "discovery" | "standard";

export type RecommendColdStartKind =
  | "none"
  | "no_history_before_the_cut"
  | "history_below_the_threshold";

export type RecommendCustomerSource = "manifest" | "cold_start_example";

export interface RecommendProtocolInfo {
  id: string;
  name: string;
  ground_truth: string;
  candidates: string;
  question: string;
}

export interface RecommendHistoryProduct {
  stock_code: string;
  description: string;
  baskets: number;
  popularity_rank: number;
}

export interface RecommendHistorySummary {
  in_training_matrix: boolean;
  training_products: number;
  training_baskets: number;
  first_purchase: string | null;
  last_purchase: string | null;
  bought_after_the_cut: number;
  new_to_them_after_the_cut: number;
  top_products: RecommendHistoryProduct[];
  note: string;
}

export interface RecommendBecauseYouBought {
  stock_code: string;
  description: string;
  contribution: number;
}

export interface RecommendSlot {
  slot: number;
  stock_code: string;
  description: string;
  score: number;
  label: string;
  from_fallback: boolean;
  already_owned: boolean;
  bought_after_the_cut: boolean;
  is_new_to_them: boolean;
  popularity_rank: number;
  training_customers: number;
  because_you_bought: RecommendBecauseYouBought | null;
  reason: string;
}

export interface RecommendReorderItem {
  slot: number;
  stock_code: string;
  description: string;
  baskets_bought_in: number;
  score: number;
  bought_after_the_cut: boolean;
  popularity_rank: number;
}

export interface RecommendReorderStrip {
  title: string;
  available: boolean;
  rule: string;
  never: string;
  items: RecommendReorderItem[];
  hits_out_of_10_standard: number;
  note: string;
}

export interface RecommendSlotsResult {
  customer_id: number;
  persona: string;
  is_discussion_case: boolean;
  discussion_note: string | null;
  protocol: RecommendProtocol;
  protocol_detail: RecommendProtocolInfo;
  module_title: string;
  personalized: boolean;
  fallback_used: boolean;
  fallback_slots: number;
  reason: string;
  model_used: string;
  score_basis: string;
  slots: RecommendSlot[];
  hits_out_of_10: number;
  buy_it_again: RecommendReorderStrip;
  history: RecommendHistorySummary;
  matches_shipping_policy: boolean;
  policy_note: string;
  human_authority: string;
  score_note: string;
  boundary: string;
}

export interface RecommendPackagedCustomer {
  customer_id: number;
  persona: string;
  source: RecommendCustomerSource;
  selection_rule: string;
  cold_start: boolean;
  cold_start_kind: RecommendColdStartKind;
  is_discussion_case: boolean;
  discussion_note: string | null;
  training_products: number;
  training_baskets: number;
  bought_after_the_cut: number;
  new_to_them_after_the_cut: number;
  discovery_hits_out_of_10: number | null;
  reorder_hits_out_of_10_standard: number | null;
  history_note: string;
}

export interface RecommendCompareSlot {
  slot: number;
  stock_code: string;
  description: string;
  score: number;
  already_owned: boolean;
  bought_after_the_cut: boolean;
}

export interface RecommendCompareRanking {
  slots: RecommendCompareSlot[];
  hits_out_of_10: number;
  already_owned_in_slots: number;
  all_scores_zero: boolean;
  scores_note: string;
}

export interface RecommendModelComparison {
  model: string;
  how_it_works: string;
  is_deployed: boolean;
  standard: RecommendCompareRanking;
  discovery: RecommendCompareRanking;
  standard_hr10: number;
  standard_rank: number;
  discovery_hr10: number;
  discovery_rank: number;
  rank_change: number;
  discovery_coverage: number;
}

export interface RecommendCompareResult {
  customer_id: number;
  persona: string;
  personalized: boolean;
  reason: string;
  is_discussion_case: boolean;
  discussion_note: string | null;
  truth_standard: number;
  truth_discovery: number;
  protocols: RecommendProtocolInfo[];
  models: RecommendModelComparison[];
  lesson: string;
  score_note: string;
  boundary: string;
}

export interface RecommendLeaderboardRow {
  model: string;
  how_it_works: string;
  hr_at_10: number;
  precision_at_10: number;
  recall_at_10: number;
  ndcg_at_10: number;
  coverage: number;
  novelty: number;
  mean_popularity_rank: number;
  customers_scored: number;
  fit_seconds: number;
  rank: number;
  is_deployed: boolean;
}

export interface RecommendSideBySideRow {
  model: string;
  standard_hr10: number;
  standard_rank: number;
  discovery_hr10: number;
  discovery_rank: number;
  rank_change: number;
  discovery_coverage: number;
  is_deployed: boolean;
}

export interface RecommendRevenueRow {
  model: string;
  discovery_hits_per_customer: number;
  revenue_reached: number;
  share_of_available_new_product_revenue: number;
  is_deployed: boolean;
}

export interface RecommendInflationRow {
  model: string;
  honest_hr10: number;
  leave_one_out_hr10: number;
  inflation: number;
}

export interface RecommendExposureRow {
  model: string;
  coverage: number;
  recommendation_gini: number;
  share_from_the_top_100: number;
  share_from_the_less_popular_half: number;
  median_popularity_rank: number;
  distinct_products_shown: number;
  top_product_share_of_all_slots: number;
  is_deployed: boolean;
}

export interface RecommendExposureLoopRow {
  round: number;
  top_10_share: number;
  top_100_share: number;
  gini: number;
  distinct_products_ever_shown: number;
}

export interface RecommendTruncationRow {
  neighbours_kept: string;
  discovery_hr10: number;
  coverage: number;
  novelty: number;
  stored_megabytes: number;
  shrink_vs_the_full_matrix: number;
  is_deployed: boolean;
}

export interface RecommendDampingRow {
  damping_alpha: number;
  discovery_hr10: number;
  ndcg_at_10: number;
  coverage: number;
  largest_difference_from_alpha_zero: number;
}

export interface RecommendFallbackItem {
  slot: number;
  stock_code: string;
  description: string;
  revenue_in_window: number;
}

export interface RecommendFallbackSweepRow {
  rule: string;
  hr_at_10: number;
  precision_at_10: number;
  cold_customers_scored: number;
  is_chosen: boolean;
}

export interface RecommendModelInfo {
  model_name: string;
  model_version: string;
  generated: string;
  framework: string;
  deployed_model: {
    id: string;
    label: string;
    how_it_works: string;
    neighbours_kept: number;
    scoring: string;
    why_not_the_most_accurate_model: string;
    stored_links: number;
    stored_megabytes: number;
    similarity_digest: string;
  };
  what_it_does: string;
  what_it_does_not_do: string[];
  intended_users: string;
  boundary: string;
  prohibited_claims: string[];
  known_limits: string[];
  dataset: {
    name: string;
    license: string;
    citation: string;
    population: string;
    raw_rows: number;
    clean_rows: number;
    committed_rows: number;
    committed_grain: string;
    products_in_the_catalog: number;
    customers_in_the_matrix: number;
    sibling_lab: Record<string, string>;
  };
  split: {
    type: string;
    cut: string;
    min_training_products_per_customer: number;
    users: number;
    items: number;
    training_pairs: number;
    sparsity: number;
    customers_scored_standard: number;
    customers_scored_discovery: number;
    why_not_random: string;
  };
  protocols: RecommendProtocolInfo[];
  leaderboards: {
    rule: string;
    standard: RecommendLeaderboardRow[];
    discovery: RecommendLeaderboardRow[];
    side_by_side: RecommendSideBySideRow[];
    reorder_zero_score_diagnosis: {
      customers: number;
      customers_with_any_positive_score: number;
      share_with_all_zero_scores: number;
      mean_popularity_rank_of_slots: number;
      catalog_size: number;
      explanation: string;
    };
  };
  incremental_revenue: {
    available_new_product_revenue: number;
    customers: number;
    by_model: RecommendRevenueRow[];
    deployed_share: number;
    no_personalization_share: number;
    gain_percentage_points: number;
    upper_bound_note: string;
    boundary: string;
  };
  leave_one_out: {
    design: string;
    plain_words: string;
    by_model: RecommendInflationRow[];
  };
  popularity_bias: {
    what_each_model_shows: RecommendExposureRow[];
    exposure_loop: {
      rounds: number;
      assumed_conversion: number;
      assumption_note: string;
      history: RecommendExposureLoopRow[];
      start_top_10_share: number;
      end_top_10_share: number;
    };
  };
  engineering: {
    truncation_trade: RecommendTruncationRow[];
    popularity_damping_is_a_no_op: RecommendDampingRow[];
    damping_note: string;
  };
  cold_start: {
    registered_customers_active_in_test: number;
    cold_registered_customers: number;
    cold_registered_share: number;
    cold_registered_revenue_share: number;
    thin_history_customers: number;
    thin_history_share: number;
    unservable_customers: number;
    unservable_share: number;
    products_sold_in_test: number;
    cold_products: number;
    cold_product_share: number;
    cold_product_revenue_share: number;
    guest_baskets_in_test: number;
    guest_revenue_share: number;
    fallback_hr10: number;
    warning: string;
  };
  repeat_purchasing: {
    test_truth_pairs: number;
    repeat_pairs: number;
    repeat_share: number;
    new_pairs: number;
    new_share: number;
    test_revenue: number;
    repeat_revenue: number;
    repeat_revenue_share: number;
    users_with_a_repeat: number;
    users_scored: number;
    users_with_a_repeat_share: number;
    note: string;
  };
  concentration: {
    items: number;
    gini: number;
    top_10_share: number;
    top_100_share: number;
    top_500_share: number;
  };
  policy: {
    slots: number;
    module_title: string;
    ranking_model: string;
    eligibility: string;
    personalize_if: string;
    statement: string;
    fallback: {
      rule: string;
      window_days: number;
      refresh: string;
      label: string;
      never_label_it: string;
      items: RecommendFallbackItem[];
      sweep: RecommendFallbackSweepRow[];
    };
    reorder_surface: { title: string; rule: string; never: string };
    human_authority: string;
    service_must: string[];
    outcomes: {
      test_window_customers: number;
      personalized_customers: number;
      personalized_share: number;
      fallback_customers: number;
      fallback_share: number;
      customers_needing_partial_backfill: number;
      partial_backfill_share: number;
      slots_total: number;
      slots_from_fallback: number;
      fallback_slot_share: number;
      guest_baskets_in_test: number;
      guest_revenue_share_of_test: number;
      guest_fallback_share: number;
    };
    boundary: string;
  };
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

export function getRecommendModel(): Promise<RecommendModelInfo> {
  return requestJson<RecommendModelInfo>("/api/recommend/model");
}

export function getRecommendCustomers(limit = 12): Promise<RecommendPackagedCustomer[]> {
  return requestJson<RecommendPackagedCustomer[]>(`/api/recommend/customers?limit=${limit}`);
}

export function getRecommendSlots(
  customerId: number,
  protocol: RecommendProtocol = "discovery",
): Promise<RecommendSlotsResult> {
  return requestJson<RecommendSlotsResult>("/api/recommend/slots", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ customer_id: customerId, protocol }),
  });
}

export function getRecommendCompare(customerId: number): Promise<RecommendCompareResult> {
  return requestJson<RecommendCompareResult>(
    `/api/recommend/compare?customer_id=${customerId}`,
  );
}
