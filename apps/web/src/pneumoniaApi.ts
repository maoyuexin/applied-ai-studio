export type PneumoniaRoute = "priority_review" | "standard_review" | "quality_hold";
export type PneumoniaLabel = "Normal" | "Pneumonia-labeled";
export type PneumoniaComparison =
  | "true_positive"
  | "false_positive"
  | "false_negative"
  | "true_negative";

export interface PneumoniaScoreRequest {
  sample_id: string;
  blur_radius: number;
  exposure_shift: number;
}

export interface PneumoniaQuality {
  status: "sufficient" | "insufficient";
  mean_intensity: number;
  focus_score: number;
  reasons: string[];
}

export interface PneumoniaScore {
  sample_id: string;
  transformed: boolean;
  image_data_uri: string;
  overlay_data_uri: string | null;
  dataset_label: PneumoniaLabel | null;
  label_note: string;
  model_score: number | null;
  threshold: number;
  route: PneumoniaRoute;
  route_label: string;
  model_name: string;
  model_version: string;
  score_note: string;
  quality: PneumoniaQuality;
  influence_note: string | null;
}

export interface PneumoniaSample {
  sample_id: string;
  scenario_label: string;
  learning_note: string;
  dataset_label: PneumoniaLabel;
  comparison: PneumoniaComparison;
  model_score: number;
  route: Exclude<PneumoniaRoute, "quality_hold">;
  image_data_uri: string;
}

export interface PneumoniaMetrics {
  sensitivity: number;
  specificity: number;
  precision: number;
  accuracy: number;
  roc_auc: number;
  average_precision: number;
  true_positives: number;
  false_positives: number;
  false_negatives: number;
  true_negatives: number;
  priority_review_rate: number;
}

export interface PneumoniaModelInfo {
  model_name: string;
  model_version: string;
  framework: string;
  packaging: string;
  architecture: string;
  trainable_parameters: number;
  input_shape: number[];
  threshold: number;
  target_validation_sensitivity: number;
  score_note: string;
  intended_use: string;
  metrics: PneumoniaMetrics;
  dataset: {
    name: string;
    source: string;
    license: string;
    population: string;
    archive_md5: string;
    split_counts: Record<string, number>;
    class_counts: Record<string, number>;
  };
  limitations: string[];
  excluded_uses: string[];
  robustness: Array<Record<string, string | number>>;
}

export interface PneumoniaQueueItem {
  sample_id: string;
  dataset_label: PneumoniaLabel;
  model_score: number;
  route: Exclude<PneumoniaRoute, "quality_hold">;
  route_label: string;
  comparison: PneumoniaComparison;
}

export interface PneumoniaReviewQueue {
  summary: {
    heldout_studies: number;
    priority_review: number;
    standard_review: number;
    quality_hold: number;
    threshold: number;
    priority_review_rate: number;
    pneumonia_labeled_in_priority: number;
    normal_labeled_in_priority: number;
  };
  items: PneumoniaQueueItem[];
  teaching_cases: PneumoniaQueueItem[];
  retrospective_note: string;
}

async function requestJson<T>(url: string, options?: RequestInit): Promise<T> {
  const response = await fetch(url, options);
  if (!response.ok) {
    const payload = (await response.json().catch(() => null)) as
      | { detail?: string; error?: string }
      | null;
    throw new Error(payload?.detail ?? payload?.error ?? `Request failed with ${response.status}.`);
  }
  return response.json() as Promise<T>;
}

export function getPneumoniaModel(): Promise<PneumoniaModelInfo> {
  return requestJson<PneumoniaModelInfo>("/api/pneumonia/model");
}

export function getPneumoniaSamples(limit = 12): Promise<PneumoniaSample[]> {
  return requestJson<PneumoniaSample[]>(`/api/pneumonia/samples?limit=${limit}`);
}

export function getPneumoniaReviewQueue(limit = 25): Promise<PneumoniaReviewQueue> {
  return requestJson<PneumoniaReviewQueue>(`/api/pneumonia/review-queue?limit=${limit}`);
}

export function scorePneumoniaSample(request: PneumoniaScoreRequest): Promise<PneumoniaScore> {
  return requestJson<PneumoniaScore>("/api/pneumonia/score", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(request),
  });
}