export interface FraudTransactionInput {
  transaction_id: string;
  occurred_at: string;
  amount: number;
  category: string;
  amount_ratio_to_card_mean: number;
  card_transactions_1h: number;
  card_transactions_24h: number;
  minutes_since_previous: number;
  distance_from_home_km: number;
  customer_age: number;
  city_population: number;
}

export interface FraudSample {
  scenario_id: string;
  scenario_label: string;
  learning_note: string;
  merchant: string;
  location: string;
  card_last4: string;
  known_outcome: "Fraud" | "Normal transaction";
  transaction: FraudTransactionInput;
}

export interface FraudContextSignal {
  label: string;
  value: string;
  note: string;
}

export interface FraudLocalContribution {
  feature: string;
  label: string;
  value: string;
  contribution: number;
  direction: "toward_review" | "away_from_review";
}

export interface FraudLocalExplanation {
  method: "Tree SHAP";
  baseline_score: number;
  contributions: FraudLocalContribution[];
  note: string;
}

export interface FraudScore {
  transaction_id: string;
  fraud_score: number;
  threshold: number;
  decision: "review" | "normal";
  decision_label: string;
  model_name: string;
  model_version: string;
  score_note: string;
  context: FraudContextSignal[];
  explanation: FraudLocalExplanation;
}

export interface FraudFeature {
  name: string;
  kind: string;
  meaning: string;
  source_columns: string;
}

export interface FraudModelInfo {
  model_name: string;
  model_version: string;
  packaging: string;
  balancing_treatment: string;
  threshold: number;
  review_budget: number;
  score_note: string;
  training_window: string[];
  test_window: string[];
  metrics: {
    recall: number;
    precision: number;
    false_positives: number;
    false_negatives: number;
    fraud_caught: number;
    fraud_missed: number;
  };
  features: FraudFeature[];
  categories: string[];
}

export interface FraudQueueItem {
  transaction_id: string;
  occurred_at: string;
  merchant: string;
  location: string;
  amount: number;
  category: string;
  fraud_score: number;
  decision_label: string;
  known_outcome: "Fraud" | "Normal transaction";
}

export interface FraudReviewQueue {
  summary: {
    review_budget: number;
    threshold: number;
    heldout_transactions: number;
    transactions_routed_to_review: number;
    known_fraud_in_review: number;
  };
  items: FraudQueueItem[];
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

export function getFraudModel(): Promise<FraudModelInfo> {
  return requestJson<FraudModelInfo>("/api/fraud/model");
}

export function getFraudSamples(limit = 12): Promise<FraudSample[]> {
  return requestJson<FraudSample[]>(`/api/fraud/samples?limit=${limit}`);
}

export function getFraudReviewQueue(limit = 25): Promise<FraudReviewQueue> {
  return requestJson<FraudReviewQueue>(`/api/fraud/review-queue?limit=${limit}`);
}

export function scoreFraudTransaction(transaction: FraudTransactionInput): Promise<FraudScore> {
  return requestJson<FraudScore>("/api/fraud/score", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(transaction),
  });
}