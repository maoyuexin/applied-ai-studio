export type CreditRoute = "priority_review" | "standard_monitoring";
export type CreditOutcome = "Later missed the payment" | "Later paid";

export interface CreditAccountInput {
  account_id: string;
  credit_limit: number;
  current_bill: number;
  last_payment: number;
  months_late_now: number;
  worst_delay_6m: number;
  num_late_months_6m: number;
  payment_ratio_6m: number;
  bill_trend_6m: number;
}

export interface CreditBehavior {
  credit_limit_NT: number;
  current_bill_NT: number;
  bill_six_months_ago_NT: number;
  last_payment_NT: number;
  utilization: number;
  months_late_now: number;
  worst_delay_6m: number;
  num_late_months_6m: number;
  payment_ratio_6m: number;
  bill_trend_6m: number;
  derivation_note: string;
}

export interface CreditReasonCode {
  feature: string;
  display_name: string;
  direction: "raises risk";
  contribution: number;
  text: string;
}

export interface CreditPackagedAccount {
  scenario_id: string;
  scenario_label: string;
  learning_note: string;
  account_id: string;
  route: CreditRoute;
  route_label: string;
  probability: number;
  exposure_NT: number;
  expected_loss_NT: number;
  actual_outcome: CreditOutcome;
  behavior: CreditBehavior;
  inputs: CreditAccountInput;
}

export interface CreditScore {
  account_id: string;
  probability: number;
  route: CreditRoute;
  route_label: string;
  route_action: string;
  exposure_NT: number;
  expected_loss_NT: number;
  review_cost_NT: number;
  loss_given_default: number;
  currency: string;
  reasons: CreditReasonCode[];
  behavior: CreditBehavior;
  is_what_if: boolean;
  changed_inputs: string[];
  actual_outcome: CreditOutcome | null;
  outcome_note: string;
  model_version: string;
  score_note: string;
}

export interface CreditQueueItem {
  rank: number;
  account_id: string;
  probability: number;
  exposure_NT: number;
  expected_loss_NT: number;
  months_late_now: number;
  utilization: number;
  within_capacity: boolean;
  actual_outcome: CreditOutcome;
}

export interface CreditQueueSummary {
  review_cost_NT: number;
  frozen_review_cost_NT: number;
  loss_given_default: number;
  currency: string;
  rule: string;
  packaged_accounts: number;
  flagged_accounts: number;
  total_expected_loss_NT: number;
  review_capacity: number;
  accounts_over_capacity: number;
  capacity_note: string;
  assumption_note: string;
  selection_note: string;
}

export interface CreditPolicySweepRow {
  review_cost_NT: number;
  flagged: number;
  flagged_share: number;
  precision: number;
  recall: number;
  net_savings_NT: number;
}

export interface CreditPopulationResult {
  accounts: number;
  flagged: number;
  flagged_share: number;
  precision: number;
  recall: number;
  net_savings_NT: number;
  review_cost_NT: number;
  note: string;
}

export interface CreditReviewQueue {
  summary: CreditQueueSummary;
  population: CreditPopulationResult;
  policy_sweep: CreditPolicySweepRow[];
  items: CreditQueueItem[];
}

export interface CreditSliceRow {
  group: string;
  accounts: number;
  mean_score: number;
  flagged_share: number;
  actual_default_rate: number;
}

export interface CreditSliceGroup {
  key: string;
  label: string;
  rows: CreditSliceRow[];
}

export interface CreditModelInfo {
  model_name: string;
  model_version: string;
  framework: string;
  packaging: string;
  estimator: string;
  intended_use: string;
  score_note: string;
  reason_code_mechanism: string;
  features: { name: string; display_name: string }[];
  dataset: {
    name: string;
    url: string;
    license: string;
    citation: string;
    population: string;
    split_counts: Record<string, { n: number; default_rate: number }>;
  };
  test_metrics: {
    auc: number;
    pr_auc: number;
    brier: number;
    review_cost_NT: number;
    flagged: number;
    flagged_share: number;
    precision: number;
    recall: number;
    net_savings_NT: number;
    confusion: { TP: number; FP: number; FN: number; TN: number };
    review_everybody_NT: number;
    review_nobody_NT: number;
  };
  policy: {
    name: string;
    rule: string;
    plain_rule: string;
    loss_given_default: number;
    review_cost_NT: number;
    currency: string;
    parameter_note: string;
    exposure: string;
    selected_on: string;
    route_priority_review: string;
    route_standard_monitoring: string;
    fallback: string;
    boundary: string;
  };
  fairness: {
    excluded_columns: string[];
    exclusion_reason: string;
    auc_without_protected: number;
    auc_with_protected: number;
    delta_auc: number;
    delta_note: string;
    slices: CreditSliceGroup[];
    note: string;
    module_10_preview: string;
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
      ? payload.detail.map((item) => item.msg).filter(Boolean).join("; ")
      : payload?.detail;
    throw new Error(detail ?? payload?.error ?? `Request failed with ${response.status}.`);
  }
  return response.json() as Promise<T>;
}

export function getCreditModel(): Promise<CreditModelInfo> {
  return requestJson<CreditModelInfo>("/api/credit/model");
}

export function getCreditSamples(limit = 12): Promise<CreditPackagedAccount[]> {
  return requestJson<CreditPackagedAccount[]>(`/api/credit/samples?limit=${limit}`);
}

export function getCreditReviewQueue(limit = 30, reviewCost?: number): Promise<CreditReviewQueue> {
  const cost = reviewCost === undefined ? "" : `&review_cost=${reviewCost}`;
  return requestJson<CreditReviewQueue>(`/api/credit/review-queue?limit=${limit}${cost}`);
}

export function scoreCreditAccount(account: CreditAccountInput): Promise<CreditScore> {
  return requestJson<CreditScore>("/api/credit/score", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(account),
  });
}
