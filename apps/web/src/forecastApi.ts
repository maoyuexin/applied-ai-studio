/* The baseline leaderboard, the interval comparison and the seasonal coverage
   slices leave the notebook as records whose keys are themselves data - column
   labels like "Coverage (promised 80%)". They travel untyped on purpose, and
   every screen that reads one reads it by a key the model card publishes. */
export type ForecastTableRow = Record<string, string | number | null>;

export interface ForecastDatasetInfo {
  dataset: string;
  uci_id: number;
  license: string;
  doi: string;
  url: string;
  citation: string;
  grain: string;
  training_window: string[];
  cohort_rule: string;
  population: string;
}

export interface ForecastEvaluationSummary {
  held_out_window: string[];
  scored_once: boolean;
  rows: number;
  products: number;
  test_weeks: number;
  mae_units: number;
  rmse_units: number;
  mae_of_flat_zero: number;
  coverage_delivered: number;
  coverage_promised: number;
  median_band_units: number;
  band_over_median_demand: number;
  pinball_10: number;
  pinball_50: number;
  pinball_90: number;
  metric_not_reported: string;
  mape_of_the_point_forecast: number;
  mape_of_a_flat_zero_forecast: number;
  mape_note: string;
}

export interface ForecastPolicyInfo {
  policy_version: string;
  decision: string;
  plain_rule: string;
  critical_ratios: Record<string, number>;
  ratios_swept: number[];
  overstock_formula: string;
  understock_formula: string;
  cost_assumption_note: string;
  costs_are_classroom_assumptions: boolean;
  cohort_rule: string;
  cohort_size: number;
  products_refused: number;
  window_weeks: number;
  nominal_low: number;
  nominal_high: number;
  nominal_coverage: number;
  horizon_weeks: number;
  train_window: string[];
  test_window: string[];
  human_authority: string;
  prohibited_claims: string[];
  fallback: string;
  recalibration: string;
}

export interface ForecastSeasonalCoverage {
  slices: ForecastTableRow[];
  ramp_months: string;
  worst_slice_coverage: number;
  worst_slice_label: string;
  misses_above_band_share: string;
  note: string;
}

export interface ForecastModelInfo {
  model_name: string;
  model_version: string;
  course: string;
  model_type: string;
  how_it_works: string;
  intended_use: string;
  not_for: string[];
  authority_boundary: string;
  boundary_short: string;
  forecast_note: string;
  interval_note: string;
  prohibited_claims: string[];
  packaged_products: number;
  cohort_products: number;
  residuals_per_product: number;
  median_unit_price: number;
  dataset: ForecastDatasetInfo;
  evaluation: ForecastEvaluationSummary;
  policy: ForecastPolicyInfo;
  newsvendor_sweep: ForecastTableRow[];
  interval_methods: ForecastTableRow[];
  point_baselines: ForecastTableRow[];
  seasonal_coverage: ForecastSeasonalCoverage;
  per_product_outcomes: ForecastTableRow[];
  limitations: string[];
  monitoring: string;
  environment: Record<string, string>;
}

export interface ForecastProductSummary {
  product_id: string;
  product: string;
  why_this_product: string;
  unit_price: number;
  test_weeks: number;
  train_nonzero_share: number;
  mean_units_per_week: number;
  point_mean: number;
  band_low_mean: number;
  band_high_mean: number;
  band_over_demand: number;
  coverage: number;
  misses: number;
  misses_above_band: number;
  cost_point: number;
  cost_quantile: number;
  cost_change_pct: number;
  policy_is_cheaper: boolean;
  demand_summary: string;
  policy_outcome: string;
}

export interface ForecastHistoryWeek {
  week: string;
  actual: number;
}

export interface ForecastPlanWeek {
  week: string;
  actual: number;
  point: number;
  low: number;
  high: number;
  covered: boolean;
  order_point: number;
  order_quantile: number;
  short_point: number;
  short_quantile: number;
  excess_point: number;
  excess_quantile: number;
}

export interface ForecastOrderOutcome {
  rule: string;
  plain_rule: string;
  quantile: number | null;
  units_ordered: number;
  units_short: number;
  units_excess: number;
  cost: number;
  fill_rate: number;
  weeks_short: number;
  weeks_left_over: number;
}

export interface ForecastLatestWeek {
  week: string;
  actual: number;
  point: number;
  low: number;
  high: number;
  band_width: number;
  covered: boolean;
  order_point: number;
  order_quantile: number;
  extra_units: number;
}

export interface ForecastPlan {
  product_id: string;
  product: string;
  why_this_product: string;
  unit_price: number;
  weeks_planned: number;
  week_start: string;
  week_end: string;
  cost_ratio: number;
  critical_ratio: number;
  is_policy_ratio: boolean;
  ratio_note: string;
  overstock_cost_per_unit_week: number;
  understock_cost_per_unit: number;
  cost_note: string;
  history: ForecastHistoryWeek[];
  weekly: ForecastPlanWeek[];
  latest: ForecastLatestWeek;
  point_plan: ForecastOrderOutcome;
  quantile_plan: ForecastOrderOutcome;
  cost_change_pct: number;
  policy_is_cheaper: boolean;
  saving: number;
  coverage: number;
  misses: number;
  misses_above_band: number;
  band_over_demand: number;
  mean_units_per_week: number;
  boundary: string;
  forecast_note: string;
  interval_note: string;
  model_version: string;
  policy_version: string;
}

export interface ForecastCohortOutcome {
  rule: string;
  plain_rule: string;
  units_ordered: number;
  units_short: number;
  units_excess: number;
  cost: number;
  fill_rate: number;
  share_of_weeks_short: number;
}

export interface ForecastLosingProduct {
  product_id: string;
  product: string;
  cost_point: number;
  cost_quantile: number;
  extra_cost: number;
  change_pct: number;
  actual_units: number;
  ordered_units: number;
  units_left_over: number;
}

export interface ForecastPolicySweep {
  cost_ratio: number;
  critical_ratio: number;
  is_policy_ratio: boolean;
  ratio_note: string;
  products: number;
  product_weeks: number;
  test_weeks: number;
  week_start: string;
  week_end: string;
  quantile_plan: ForecastCohortOutcome;
  point_plan: ForecastCohortOutcome;
  mean_plan: ForecastCohortOutcome;
  units_uplift_pct: number;
  vs_point_pct: number;
  vs_mean_pct: number;
  cheaper_than_point: boolean;
  cheaper_than_mean: boolean;
  products_cheaper: number;
  products_worse: number;
  products_worse_share: number;
  extra_cost_on_losers: number;
  worst_products: ForecastLosingProduct[];
  best_products: ForecastLosingProduct[];
  cost_note: string;
  boundary: string;
  note: string;
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

export function getForecastModel(): Promise<ForecastModelInfo> {
  return requestJson<ForecastModelInfo>("/api/forecast/model");
}

export function getForecastProducts(limit = 10): Promise<ForecastProductSummary[]> {
  return requestJson<ForecastProductSummary[]>(`/api/forecast/products?limit=${limit}`);
}

export function getForecastPolicySweep(ratio?: number): Promise<ForecastPolicySweep> {
  const query = ratio === undefined ? "" : `?ratio=${ratio}`;
  return requestJson<ForecastPolicySweep>(`/api/forecast/policy-sweep${query}`);
}

export function planForecast(productId: string, costRatio?: number): Promise<ForecastPlan> {
  const body: { product_id: string; cost_ratio?: number } = { product_id: productId };
  if (costRatio !== undefined) body.cost_ratio = costRatio;
  return requestJson<ForecastPlan>("/api/forecast/plan", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
}
