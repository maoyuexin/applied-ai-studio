export type MaintenanceRoute = "work_order" | "watch" | "no_action";

/* The drift, sweep and coverage tables leave the notebook as records whose keys
   are themselves data - month names like "2020-04", column labels like
   "false callouts @ 4". They travel untyped on purpose, and every screen that
   reads one reads it by a key the model card publishes. */
export type MaintenanceTableRow = Record<string, string | number | null>;

export interface MaintenanceFeatureInfo {
  name: string;
  display_name: string;
  planner_question: string;
  direction_that_means_trouble: string;
  plain_direction: string;
  training_normal: number;
  training_normal_text: string;
  training_scale: number;
}

export interface MaintenanceFrozenTest {
  window: string[];
  threshold: number;
  scored_hours: number;
  alert_hours: number;
  clean_hours: number;
  false_alarm_hours: number;
  false_alarm_rate_on_clean_hours: number;
  false_callouts: number;
  false_callouts_per_month: number;
  months: number;
  failures_detected: number;
  failures_with_advance_warning: number;
  first_alert: string | null;
  lead_hours: number | null;
  policy: MaintenanceTableRow;
  never_alert: MaintenanceTableRow;
  honest_roi_note: string;
}

export interface MaintenanceDrift {
  naive_single_feature_pct_clean_hours_alerting: MaintenanceTableRow[];
  detector_false_callouts_by_month: MaintenanceTableRow[];
  mitigations: MaintenanceTableRow[];
  monthly_alert_load_at_operating_threshold: MaintenanceTableRow[];
  cruel_interaction: string;
}

export interface MaintenanceDiscussionCase {
  healthy_window_id: string;
  healthy_label: string;
  healthy_peak_score: number;
  failure_window_id: string;
  failure_label: string;
  failure_peak_score: number;
  gap: number;
  statement: string;
}

export interface MaintenanceModelInfo {
  model_name: string;
  model_version: string;
  course: string;
  model_type: string;
  how_it_works: string;
  intended_use: string;
  not_for: string[];
  authority_boundary: string;
  boundary_short: string;
  score_note: string;
  packaged_windows: number;
  scored_hours: number;
  features: MaintenanceFeatureInfo[];
  dataset: {
    dataset: string;
    uci_id: number;
    license: string;
    url: string;
    citation: string;
    raw_sampling: string;
    committed_resolution: string;
    training_window: string[];
    population: string;
  };
  policy: {
    policy_version: string;
    threshold: number;
    watch_threshold: number;
    route_work_order: string;
    route_watch: string;
    route_no_action: string;
    plain_rule: string;
    response_hours: number;
    merge_gap_hours: number;
    threshold_selected_on: string[];
    training_window: string[];
    held_out_test: string[];
    fallback: string;
    recalibration: string;
    boundary_statement: string;
    costs_are_synthetic: boolean;
    costs: Record<string, number>;
    cost_note: string;
  };
  frozen_test: MaintenanceFrozenTest;
  drift: MaintenanceDrift;
  threshold_sweep: MaintenanceTableRow[];
  baseline_policies: MaintenanceTableRow[];
  full_period_policy: MaintenanceTableRow;
  full_period_never_alert: MaintenanceTableRow;
  feature_bug: {
    description: string;
    hours_deleted_per_failure: MaintenanceTableRow[];
  };
  training_window_not_clean: {
    training_hours: number;
    hours_above_threshold: number;
    share_above_threshold: number;
    episodes: number;
    peak_score: number;
    peak_at: string;
    episode_list: MaintenanceTableRow[];
  };
  data_coverage: {
    summary: MaintenanceTableRow[];
    pre_onset_coverage: MaintenanceTableRow[];
    note: string;
  };
  discussion_case: MaintenanceDiscussionCase;
  limitations: string[];
  monitoring: string;
  environment: Record<string, string>;
}

export interface MaintenanceSampleWindow {
  sample_id: string;
  label: string;
  purpose: string;
  start: string;
  end: string;
  hours_with_data: number;
  peak_score: number;
  peak_at: string;
  median_score: number;
  work_order_hours: number;
  watch_hours: number;
  route_at_peak: MaintenanceRoute;
  route_label_at_peak: string;
  top_driver_at_peak: string;
  top_driver_z: number;
  covers_documented_failure: boolean;
}

export interface MaintenanceHourScore {
  hour: string;
  score: number;
  route_at_policy: MaintenanceRoute;
  route_at_threshold: MaintenanceRoute;
  alerts: boolean;
}

export interface MaintenanceFeatureFact {
  name: string;
  display_name: string;
  planner_question: string;
  reading: string;
  normal: string;
  plain_direction: string;
  distance_from_normal: number;
  share_of_score: number;
  pushes_score_up: boolean;
  sentence: string;
}

export interface MaintenanceWindowScore {
  window_id: string;
  label: string;
  purpose: string;
  start: string;
  end: string;
  hours_with_data: number;
  threshold: number;
  policy_threshold: number;
  watch_threshold: number;
  threshold_is_override: boolean;
  threshold_note: string;
  hours: MaintenanceHourScore[];
  peak_score: number;
  peak_at: string;
  median_score: number;
  route_at_peak: MaintenanceRoute;
  route_label: string;
  technician_action: string;
  alert_hours: number;
  watch_hours: number;
  no_action_hours: number;
  alerting_hours: string[];
  first_alert_hour: string | null;
  alert_hours_at_policy: number;
  route_changed_by_threshold: boolean;
  drivers: MaintenanceFeatureFact[];
  readings_at: string;
  covers_documented_failure: boolean;
  boundary: string;
  score_note: string;
  model_version: string;
}

export interface MaintenanceMonthlyLoad {
  month: string;
  clean_hours: number;
  alert_hours: number;
  pct_of_clean_hours: number;
  false_callouts: number;
}

export interface MaintenanceBaselineCost {
  policy: string;
  plain_name: string;
  callouts: number;
  technician_hours: number;
  failures_caught: number;
  failures_total: number;
  callout_cost_usd: number;
  fault_cost_usd: number;
  total_cost_usd: number;
}

export interface MaintenanceQueue {
  threshold: number;
  threshold_note: string;
  is_operating_threshold: boolean;
  policy_threshold: number;
  window_start: string;
  window_end: string;
  months: number;
  alert_hours: number;
  callouts: number;
  false_callouts: number;
  alerts_per_month: number;
  technician_hours: number;
  failures_caught: number;
  failures_missed: number;
  failures_total: number;
  callout_cost_usd: number;
  fault_cost_usd: number;
  total_cost_usd: number;
  never_alert: MaintenanceBaselineCost;
  scheduled_inspection: MaintenanceBaselineCost;
  net_vs_never_usd: number;
  net_vs_scheduled_usd: number;
  beats_never_alert: boolean;
  beats_scheduled_inspection: boolean;
  monthly_load: MaintenanceMonthlyLoad[];
  drift: {
    busiest_month: string;
    busiest_alert_hours: number;
    quietest_month: string;
    quietest_alert_hours: number;
    sentence: string;
  };
  assumption_note: string;
  boundary: string;
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

export function getMaintenanceModel(): Promise<MaintenanceModelInfo> {
  return requestJson<MaintenanceModelInfo>("/api/maintenance/model");
}

export function getMaintenanceSamples(limit = 8): Promise<MaintenanceSampleWindow[]> {
  return requestJson<MaintenanceSampleWindow[]>(`/api/maintenance/samples?limit=${limit}`);
}

export function getMaintenanceQueue(threshold?: number): Promise<MaintenanceQueue> {
  const query = threshold === undefined ? "" : `?threshold=${threshold}`;
  return requestJson<MaintenanceQueue>(`/api/maintenance/queue${query}`);
}

export function scoreMaintenanceWindow(
  windowId: string,
  threshold?: number,
): Promise<MaintenanceWindowScore> {
  const body: { window_id: string; threshold?: number } = { window_id: windowId };
  if (threshold !== undefined) body.threshold = threshold;
  return requestJson<MaintenanceWindowScore>("/api/maintenance/score", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
}
