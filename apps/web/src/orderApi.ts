export interface OrderProduct {
  id: string;
  name: string;
  description: string;
  category: string;
  price_cents: number;
  image_url: string;
  quantity_available: number;
}

export interface OrderCustomer {
  id: string;
  name: string;
  email: string;
  address_line: string;
  city: string;
  region: string;
  postal_code: string;
}

export interface OrderLine {
  product_id: string;
  quantity: number;
  unit_price_cents: number;
  product: OrderProduct;
}

export interface OrderEvent {
  id: number;
  sequence: number;
  event_type: string;
  stage: string;
  actor: string;
  summary: string;
  details: Record<string, unknown>;
  occurred_at: string;
}

export interface OrderDecision {
  id: number;
  decision_type: string;
  method: string;
  recommendation: string;
  score: number | null;
  status: string;
  evidence: string[];
  impact: DecisionImpact | null;
  algorithm_profile: AlgorithmProfile | null;
  decided_by: string;
  created_at: string;
}

export interface AlgorithmFeature {
  name: string;
  kind: string;
  source: string;
  role: string;
}

export interface AlgorithmMetric {
  name: string;
  target: string;
  why: string;
}

export interface AlgorithmProfile {
  title: string;
  category: string;
  implementation_status: string;
  purpose: string;
  algorithm: string;
  why_fit: string;
  output: string;
  training_required: boolean;
  training_approach: string;
  training_data: string;
  target_definition: string;
  split_strategy: string;
  preprocessing: string[];
  features: AlgorithmFeature[];
  metrics: AlgorithmMetric[];
  testing: string[];
  monitoring: string[];
  limitations: string[];
}

export interface DecisionSignal {
  label: string;
  value: string;
  influence: "raises" | "lowers" | "neutral";
  contribution: string;
  explanation: string;
}

export interface DecisionThreshold {
  label: string;
  range: string;
  outcome: string;
}

export interface DecisionImpact {
  question: string;
  model_name: string;
  model_version: string;
  model_kind: string;
  output_name: string;
  output_value: number;
  output_unit: string;
  output_label: string;
  thresholds: DecisionThreshold[];
  selected_branch: string;
  process_effect: string;
  business_effect: string;
  human_boundary: string;
  counterfactual: string;
  input_signals: DecisionSignal[];
}

export interface OnlineOrder {
  id: string;
  display_id: string;
  status: string;
  scenario: string;
  subtotal_cents: number;
  shipping_cents: number;
  total_cents: number;
  version: number;
  created_at: string;
  updated_at: string;
  customer: OrderCustomer;
  items: OrderLine[];
  events: OrderEvent[];
  decisions: OrderDecision[];
}

export interface OrderSubmission {
  customer_name: string;
  customer_email: string;
  address_line: string;
  city: string;
  region: string;
  postal_code: string;
  items: Array<{ product_id: string; quantity: number }>;
  scenario: string;
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

export function getOrderProducts(): Promise<OrderProduct[]> {
  return requestJson<OrderProduct[]>("/api/orders/products");
}

export async function getOrders(): Promise<OnlineOrder[]> {
  const response = await requestJson<{ items: OnlineOrder[]; total: number }>("/api/orders");
  return response.items;
}

export function getOrder(orderId: string): Promise<OnlineOrder> {
  return requestJson<OnlineOrder>(`/api/orders/${encodeURIComponent(orderId)}`);
}

export function submitOrder(input: OrderSubmission): Promise<OnlineOrder> {
  return requestJson<OnlineOrder>("/api/orders", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(input),
  });
}

export function advanceOrder(orderId: string): Promise<OnlineOrder> {
  return requestJson<OnlineOrder>(`/api/orders/${encodeURIComponent(orderId)}/advance`, {
    method: "POST",
  });
}

export function subscribeToOrder(
  orderId: string,
  afterEventId: number,
  onEvent: (event: OrderEvent) => void,
): () => void {
  const source = new EventSource(
    `/api/orders/${encodeURIComponent(orderId)}/events/stream?after=${afterEventId}`,
  );
  source.onmessage = (message) => onEvent(JSON.parse(message.data) as OrderEvent);
  return () => source.close();
}
