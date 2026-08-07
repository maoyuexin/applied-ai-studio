import { useEffect, useRef, useState } from "react";
import { createPortal } from "react-dom";
import {
  Activity,
  AlertTriangle,
  ArrowLeft,
  ArrowRight,
  BarChart3,
  BrainCircuit,
  Check,
  Circle,
  CircleCheck,
  Clock3,
  Database,
  ExternalLink,
  FlaskConical,
  Gauge,
  GitBranch,
  ListChecks,
  MapPin,
  Minus,
  PackageCheck,
  Play,
  Plus,
  RotateCcw,
  ShieldCheck,
  ShoppingBag,
  SlidersHorizontal,
  Store,
  TestTube2,
  TrendingDown,
  TrendingUp,
  Truck,
  UserCheck,
  UserRound,
  Warehouse,
  X,
} from "lucide-react";
import {
  advanceOrder,
  getOrder,
  getOrderProducts,
  getOrders,
  submitOrder,
  subscribeToOrder,
  type OnlineOrder,
  type OrderDecision,
  type OrderProduct,
} from "../orderApi";
import { navigate } from "../router";

type Workspace = "customer" | "operations" | "scenario";

const orderStatuses = [
  "submitted",
  "address_validated",
  "payment_cleared",
  "allocated",
  "packed",
  "shipped",
  "delivered",
];

const statusLabels: Record<string, string> = {
  submitted: "Order received",
  address_validated: "Address confirmed",
  payment_cleared: "Payment cleared",
  allocated: "Inventory allocated",
  packed: "Packed",
  shipped: "In transit",
  delivered: "Delivered",
  cancelled: "Cancelled",
};

const workspaceOptions: Array<{
  id: Workspace;
  label: string;
  detail: string;
  icon: typeof Store;
}> = [
  { id: "customer", label: "Customer", detail: "Store and tracking", icon: Store },
  { id: "operations", label: "Merchant", detail: "Orders and decisions", icon: ListChecks },
  { id: "scenario", label: "Scenario", detail: "Run controls", icon: SlidersHorizontal },
];

const algorithmCards: Array<{
  decisionType: string;
  label: string;
  detail: string;
  icon: typeof BrainCircuit;
}> = [
  { decisionType: "address_validation", label: "Rule engine", detail: "Address deliverability", icon: ShieldCheck },
  { decisionType: "payment_screening", label: "Payment classifier", detail: "Fraud probability", icon: BrainCircuit },
  { decisionType: "fulfillment_allocation", label: "Allocation optimizer", detail: "Warehouse and carrier", icon: Warehouse },
  { decisionType: "delivery_risk_prediction", label: "Delivery predictor", detail: "Late-delivery risk", icon: Truck },
];

const nonAiRunEffects: Record<string, { branch: string; effect: string }> = {
  address_validation: {
    branch: "Continue to payment screening",
    effect: "The address passed deterministic postal and service-area checks, so the order skipped correction and continued.",
  },
  fulfillment_allocation: {
    branch: "Reserve inventory and dispatch from one warehouse",
    effect: "Inventory was reserved at SEA-01 and Northline Ground was selected, so the order advanced to picking and packing.",
  },
};

const customerEventCopy: Record<string, string> = {
  "order.submitted": "We received your order.",
  "address.validated": "Your delivery details are confirmed.",
  "payment.screened": "Your payment is confirmed.",
  "inventory.allocated": "Your items are reserved for fulfillment.",
  "shipment.packed": "Your order is packed.",
  "shipment.dispatched": "Your order is on the way.",
  "order.delivered": "Your order was delivered.",
};

const money = (value: number): string =>
  new Intl.NumberFormat("en-US", { style: "currency", currency: "USD" }).format(value / 100);

const eventTime = (value: string): string =>
  new Intl.DateTimeFormat("en-US", { hour: "numeric", minute: "2-digit" }).format(new Date(value));

const decisionOutput = (value: number, unit: string): string =>
  `${value.toFixed(2)}${unit}`;

function StatusTrack({ order }: { order: OnlineOrder }) {
  const activeIndex = orderStatuses.indexOf(order.status);
  return (
    <ol className="order-status-track" aria-label="Order progress">
      {orderStatuses.map((status, index) => {
        const complete = index <= activeIndex;
        return (
          <li className={complete ? "complete" : ""} key={status}>
            {complete ? <CircleCheck size={17} aria-hidden="true" /> : <Circle size={17} aria-hidden="true" />}
            <span>{statusLabels[status]}</span>
          </li>
        );
      })}
    </ol>
  );
}

function EventTimeline({ order, audience = "operations" }: {
  order: OnlineOrder;
  audience?: "customer" | "operations";
}) {
  return (
    <div className="order-event-timeline">
      {order.events.map((event, index) => (
        <div className="order-event" key={event.id}>
          <div className="order-event-marker"><span>{index + 1}</span></div>
          <div>
            <div><strong>{audience === "customer" ? customerEventCopy[event.event_type] ?? "Your order was updated." : event.summary}</strong><time>{eventTime(event.occurred_at)}</time></div>
            <p>{audience === "customer" ? "Order update" : `${event.actor} · ${event.event_type.replaceAll(".", " ")}`}</p>
          </div>
        </div>
      ))}
    </div>
  );
}

function DecisionPanel({ decision, onExplore }: {
  decision?: OrderDecision;
  onExplore?: (decision: OrderDecision) => void;
}) {
  if (!decision) {
    return (
      <section className="order-decision-empty">
        <Clock3 size={24} aria-hidden="true" />
        <strong>No decision recorded yet</strong>
        <p>Advance the order to reach address validation, payment screening, and allocation.</p>
      </section>
    );
  }
  const isAi = decision.method.startsWith("ai-");
  const impact = decision.impact;
  const canExplore = Boolean(decision.algorithm_profile && onExplore);
  return (
    <section
      className={`order-decision-panel ${isAi ? "is-ai" : ""}`}
      onDoubleClick={canExplore ? () => onExplore?.(decision) : undefined}
      title={canExplore ? "Double-click to explore this algorithm" : undefined}
    >
      <div className="order-decision-heading">
        {isAi ? <BrainCircuit size={18} aria-hidden="true" /> : decision.method === "optimization" ? <Gauge size={18} aria-hidden="true" /> : <ShieldCheck size={18} aria-hidden="true" />}
        <div><span>{isAi ? "AI decision" : "Decision method"}</span><strong>{decision.decision_type.replaceAll("_", " ")}</strong>{impact ? <small>{impact.model_name} · {impact.model_version}</small> : null}</div>
      </div>
      {impact ? <div className="order-decision-question"><span>Business question</span><p>{impact.question}</p></div> : null}
      <div className="order-decision-result">
        <div><span>{impact ? impact.output_name : "Recommendation"}</span><strong>{impact ? decisionOutput(impact.output_value, impact.output_unit) : decision.recommendation}</strong>{impact ? <small>{impact.output_label} · {impact.model_kind}</small> : decision.score !== null ? <small>{(decision.score * 100).toFixed(2)}% risk score</small> : null}</div>
        {impact ? <><ArrowRight size={18} aria-hidden="true" /><div><span>Selected branch</span><strong>{impact.selected_branch}</strong><small>Applied to workflow</small></div></> : null}
      </div>
      {impact ? <>
        <div className="order-decision-signals">
          <span>Input signals and influence</span>
          <small>In this deterministic simulation, contributions are percentage-point adjustments that sum to the displayed probability.</small>
          <div>{impact.input_signals.map((signal) => (
            <div className={`signal-${signal.influence}`} key={signal.label}>
              {signal.influence === "raises" ? <TrendingUp size={14} aria-hidden="true" /> : signal.influence === "lowers" ? <TrendingDown size={14} aria-hidden="true" /> : <Minus size={14} aria-hidden="true" />}
              <div><strong>{signal.label}</strong><span>{signal.value}</span><p>{signal.explanation}</p></div><b>{signal.contribution}</b>
            </div>
          ))}</div>
        </div>
        <div className="order-decision-thresholds">
          <span>Policy thresholds</span>
          <div>{impact.thresholds.map((threshold) => (
            <div className={threshold.label.toLowerCase() === impact.output_label.toLowerCase() ? "selected" : ""} key={threshold.label}><strong>{threshold.label}</strong><b>{threshold.range}</b><p>{threshold.outcome}</p></div>
          ))}</div>
        </div>
        <div className="order-decision-process">
          <div><BrainCircuit size={16} aria-hidden="true" /><span>Model result</span><p>{impact.output_label} at {decisionOutput(impact.output_value, impact.output_unit)}</p></div>
          <ArrowRight size={16} aria-hidden="true" />
          <div><GitBranch size={16} aria-hidden="true" /><span>Process influence</span><p>{impact.process_effect}</p></div>
        </div>
        <div className="order-decision-outcomes">
          <div><span>Business effect</span><p>{impact.business_effect}</p></div>
          <div><span>If the prediction changed</span><p>{impact.counterfactual}</p></div>
        </div>
        <div className="order-decision-human"><UserCheck size={16} aria-hidden="true" /><div><span>Human authority</span><p>{impact.human_boundary}</p></div></div>
      </> : <div className="order-decision-evidence">
          <span>Evidence</span>
          <ul>{decision.evidence.map((item) => <li key={item}><Check size={13} aria-hidden="true" /> {item}</li>)}</ul>
        </div>}
      <footer>
        <div><span>Applied by</span><strong>{decision.decided_by}</strong></div>
        {canExplore ? <button type="button" onClick={() => onExplore?.(decision)}><BrainCircuit size={14} aria-hidden="true" /> Explore algorithm</button> : null}
      </footer>
    </section>
  );
}

type AlgorithmTab = "overview" | "features" | "development" | "metrics";

const algorithmTabs: Array<{
  id: AlgorithmTab;
  label: string;
  icon: typeof BrainCircuit;
}> = [
  { id: "overview", label: "Overview", icon: BrainCircuit },
  { id: "features", label: "Features", icon: Database },
  { id: "development", label: "Train & test", icon: FlaskConical },
  { id: "metrics", label: "Metrics", icon: BarChart3 },
];

function AlgorithmDrilldown({ decision, onClose }: {
  decision: OrderDecision;
  onClose: () => void;
}) {
  const profile = decision.algorithm_profile!;
  const nonAiRun = nonAiRunEffects[decision.decision_type];
  const currentRunOutput = decision.impact
    ? decisionOutput(decision.impact.output_value, decision.impact.output_unit)
    : decision.recommendation;
  const currentRunLabel = decision.impact?.output_label
    ?? decision.evidence.join(" · ");
  const currentRunBranch = decision.impact?.selected_branch
    ?? nonAiRun?.branch
    ?? decision.status;
  const currentRunEffect = decision.impact?.process_effect
    ?? nonAiRun?.effect
    ?? "The recorded result was applied to the next workflow step.";
  const [tab, setTab] = useState<AlgorithmTab>("overview");
  const closeRef = useRef<HTMLButtonElement>(null);

  useEffect(() => {
    const previousOverflow = document.body.style.overflow;
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") onClose();
    };
    document.body.style.overflow = "hidden";
    window.addEventListener("keydown", onKeyDown);
    closeRef.current?.focus();
    return () => {
      document.body.style.overflow = previousOverflow;
      window.removeEventListener("keydown", onKeyDown);
    };
  }, [onClose]);

  const dialog = (
    <div
      className="algorithm-dialog-backdrop"
      onMouseDown={(event) => {
        if (event.target === event.currentTarget) onClose();
      }}
    >
      <section
        className="algorithm-dialog"
        role="dialog"
        aria-modal="true"
        aria-labelledby="algorithm-dialog-title"
      >
        <header className="algorithm-dialog-header">
          <div>
            <span><BrainCircuit size={15} aria-hidden="true" /> Algorithm drill-down</span>
            <h2 id="algorithm-dialog-title">{profile.title}</h2>
            <p>{profile.purpose}</p>
          </div>
          <button ref={closeRef} type="button" onClick={onClose} aria-label="Close algorithm details" title="Close"><X size={19} /></button>
        </header>

        <div className="algorithm-dialog-summary">
          <div><span>Decision</span><strong>{decision.decision_type.replaceAll("_", " ")}</strong></div>
          <div><span>Algorithm family</span><strong>{profile.category}</strong></div>
          <div><span>Training</span><strong>{profile.training_required ? "Required" : "Not required"}</strong></div>
          <div><span>Current implementation</span><strong>{profile.implementation_status}</strong></div>
        </div>

        <nav className="algorithm-dialog-tabs" aria-label="Algorithm detail sections">
          {algorithmTabs.map(({ id, label, icon: Icon }) => (
            <button type="button" className={tab === id ? "active" : ""} onClick={() => setTab(id)} aria-pressed={tab === id} key={id}><Icon size={15} aria-hidden="true" /> {label}</button>
          ))}
        </nav>

        <div className="algorithm-dialog-content">
          {tab === "overview" ? (
            <div className="algorithm-overview">
              <section>
                <span>How it works</span>
                <h3>{profile.category}</h3>
                <p>{profile.algorithm}</p>
              </section>
              <section>
                <span>Why this fits</span>
                <h3>Method choice</h3>
                <p>{profile.why_fit}</p>
              </section>
              <section>
                <span>Output contract</span>
                <h3>What the workflow receives</h3>
                <p>{profile.output}</p>
              </section>
              <section className="algorithm-status-note">
                <AlertTriangle size={18} aria-hidden="true" />
                <div><span>Reality boundary</span><p>{profile.implementation_status}. The development plan below is proposed and has not produced claimed production performance.</p></div>
              </section>
              <section className="algorithm-current-run">
                <div><span>Current run output</span><strong>{currentRunOutput}</strong><small>{currentRunLabel}</small></div>
                <ArrowRight size={18} aria-hidden="true" />
                <div><span>Branch applied</span><strong>{currentRunBranch}</strong><small>{currentRunEffect}</small></div>
              </section>
            </div>
          ) : null}

          {tab === "features" ? (
            <div className="algorithm-features">
              <header><div><span>Feature contract</span><h3>{profile.features.length} inputs</h3></div><p>Every feature must exist at decision time. Source and role are explicit to reduce leakage and ownership ambiguity.</p></header>
              <div className="algorithm-feature-table" role="table" aria-label={`${profile.title} features`}>
                <div className="algorithm-table-header" role="row"><span>Feature</span><span>Type</span><span>Source</span><span>How it is used</span></div>
                {profile.features.map((feature) => (
                  <div role="row" key={feature.name}><strong>{feature.name}</strong><span data-label="Type">{feature.kind}</span><span data-label="Source">{feature.source}</span><p data-label="Role">{feature.role}</p></div>
                ))}
              </div>
              <section className="algorithm-list-section"><h3><Database size={16} aria-hidden="true" /> Preparation</h3><ol>{profile.preprocessing.map((item) => <li key={item}>{item}</li>)}</ol></section>
            </div>
          ) : null}

          {tab === "development" ? (
            <div className="algorithm-development">
              <section className="algorithm-development-grid">
                <div><span>{profile.training_required ? "Training approach" : "Configuration approach"}</span><h3>{profile.training_required ? "How to train" : "No model training"}</h3><p>{profile.training_approach}</p></div>
                <div><span>Development evidence</span><h3>{profile.training_required ? "Training data" : "Benchmark data"}</h3><p>{profile.training_data}</p></div>
                <div><span>Ground truth or objective</span><h3>Target definition</h3><p>{profile.target_definition}</p></div>
                <div><span>Evaluation separation</span><h3>{profile.training_required ? "Train / validation / test" : "Tuning / benchmark split"}</h3><p>{profile.split_strategy}</p></div>
              </section>
              <section className="algorithm-list-section"><h3><TestTube2 size={16} aria-hidden="true" /> Test plan</h3><ol>{profile.testing.map((item) => <li key={item}>{item}</li>)}</ol></section>
            </div>
          ) : null}

          {tab === "metrics" ? (
            <div className="algorithm-metrics">
              <header><div><span>Evaluation contract</span><h3>Technical and business metrics</h3></div><p>Targets are proposed acceptance criteria for a future implementation, not achieved results from this synthetic demo.</p></header>
              <div className="algorithm-metric-table" role="table" aria-label={`${profile.title} metrics`}>
                <div className="algorithm-table-header" role="row"><span>Metric</span><span>Proposed target</span><span>Why it matters</span></div>
                {profile.metrics.map((metric) => (
                  <div role="row" key={metric.name}><strong>{metric.name}</strong><b data-label="Target">{metric.target}</b><p data-label="Why">{metric.why}</p></div>
                ))}
              </div>
              <div className="algorithm-monitoring-grid">
                <section className="algorithm-list-section"><h3><Activity size={16} aria-hidden="true" /> Production monitoring</h3><ul>{profile.monitoring.map((item) => <li key={item}>{item}</li>)}</ul></section>
                <section className="algorithm-list-section limitations"><h3><AlertTriangle size={16} aria-hidden="true" /> Limits and controls</h3><ul>{profile.limitations.map((item) => <li key={item}>{item}</li>)}</ul></section>
              </div>
            </div>
          ) : null}
        </div>
      </section>
    </div>
  );

  return createPortal(dialog, document.body);
}

function CustomerTracking({ order, onOpenMerchant, onShopAgain }: {
  order: OnlineOrder;
  onOpenMerchant: () => void;
  onShopAgain: () => void;
}) {
  return (
    <div className="customer-order-view">
      <section className="customer-order-summary">
        <div>
          <span className="eyebrow">Order confirmed</span>
          <h2>{order.display_id}</h2>
          <p>Thanks, {order.customer.name}. This page follows the same persisted order shown in Merchant Operations.</p>
        </div>
        <div className="customer-order-total"><span>Total</span><strong>{money(order.total_cents)}</strong></div>
      </section>
      <section className="customer-order-progress">
        <div className="order-section-heading"><Truck size={18} aria-hidden="true" /><div><span>Live order journey</span><strong>{statusLabels[order.status]}</strong></div></div>
        <StatusTrack order={order} />
      </section>
      <div className="customer-order-columns">
        <section>
          <div className="order-section-heading"><PackageCheck size={18} aria-hidden="true" /><div><span>Items</span><strong>{order.items.length} products</strong></div></div>
          <div className="customer-order-items">
            {order.items.map((item) => (
              <div key={item.product_id}><img src={item.product.image_url} alt="" /><div><strong>{item.product.name}</strong><span>Qty {item.quantity}</span></div><b>{money(item.unit_price_cents * item.quantity)}</b></div>
            ))}
          </div>
          <div className="customer-address"><MapPin size={17} aria-hidden="true" /><div><span>Deliver to</span><strong>{order.customer.address_line}</strong><p>{order.customer.city}, {order.customer.region} {order.customer.postal_code}</p></div></div>
        </section>
        <section>
          <div className="order-section-heading"><Clock3 size={18} aria-hidden="true" /><div><span>Updates</span><strong>Order activity</strong></div></div>
          <EventTimeline order={order} audience="customer" />
        </section>
      </div>
      <div className="order-view-actions">
        <button className="secondary-button" type="button" onClick={onShopAgain}><RotateCcw size={15} aria-hidden="true" /> Place another order</button>
        <button className="primary-button compact" type="button" onClick={onOpenMerchant}>Open Merchant Operations <ArrowRight size={15} aria-hidden="true" /></button>
      </div>
    </div>
  );
}

export default function OnlineOrderPage() {
  const search = new URLSearchParams(window.location.search);
  const requestedWorkspace = search.get("view");
  const initialWorkspace = (requestedWorkspace === "control" ? "scenario" : requestedWorkspace) as Workspace | null;
  const initialOrderId = search.get("order");
  const [workspace, setWorkspace] = useState<Workspace>(
    workspaceOptions.some((option) => option.id === initialWorkspace) ? initialWorkspace! : "customer",
  );
  const [products, setProducts] = useState<OrderProduct[]>([]);
  const [orders, setOrders] = useState<OnlineOrder[]>([]);
  const [selectedOrder, setSelectedOrder] = useState<OnlineOrder | null>(null);
  const [focusedDecisionId, setFocusedDecisionId] = useState<number | null>(null);
  const [algorithmDecision, setAlgorithmDecision] = useState<OrderDecision | null>(null);
  const [cart, setCart] = useState<Record<string, number>>({});
  const [customer, setCustomer] = useState({
    name: "Maya Chen",
    email: "maya@example.com",
    address: "451 Cedar Avenue",
    city: "Seattle",
    region: "WA",
    postalCode: "98101",
  });
  const [loading, setLoading] = useState(true);
  const [working, setWorking] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    void Promise.all([getOrderProducts(), getOrders()])
      .then(async ([productItems, orderItems]) => {
        if (cancelled) return;
        setProducts(productItems);
        setOrders(orderItems);
        const preferred = initialOrderId
          ? await getOrder(initialOrderId).catch(() => null)
          : initialWorkspace === "customer" || !initialWorkspace
            ? null
            : orderItems[0] ?? null;
        if (!cancelled) setSelectedOrder(preferred);
      })
      .catch((reason: Error) => setError(reason.message))
      .finally(() => setLoading(false));
    return () => { cancelled = true; };
  }, []);

  const selectedOrderId = selectedOrder?.id;
  const selectedOrderStatus = selectedOrder?.status;
  const latestEventId = selectedOrder?.events.at(-1)?.id ?? 0;
  useEffect(() => {
    if (!selectedOrderId || selectedOrderStatus === "delivered" || selectedOrderStatus === "cancelled") return;
    return subscribeToOrder(selectedOrderId, latestEventId, () => {
      void Promise.all([getOrder(selectedOrderId), getOrders()]).then(([order, orderItems]) => {
        setSelectedOrder(order);
        setOrders(orderItems);
      });
    });
  }, [selectedOrderId, selectedOrderStatus]);

  useEffect(() => {
    setFocusedDecisionId(null);
    setAlgorithmDecision(null);
  }, [selectedOrderId]);

  const cartItems = Object.entries(cart)
    .filter(([, quantity]) => quantity > 0)
    .map(([productId, quantity]) => ({ product: products.find((item) => item.id === productId)!, quantity }))
    .filter((item) => item.product);
  const cartSubtotal = cartItems.reduce((total, item) => total + item.product.price_cents * item.quantity, 0);

  const switchWorkspace = (next: Workspace, order = selectedOrder) => {
    setWorkspace(next);
    const nextUrl = `/online-order?view=${next}${order ? `&order=${encodeURIComponent(order.id)}` : ""}`;
    window.history.replaceState({}, "", nextUrl);
  };

  const openWorkspace = (next: Workspace, order = selectedOrder) => {
    const url = `/online-order?view=${next}${order ? `&order=${encodeURIComponent(order.id)}` : ""}`;
    window.open(url, `online-order-${next}`);
  };

  const updateCart = (productId: string, delta: number) => {
    setCart((current) => ({ ...current, [productId]: Math.max(0, (current[productId] ?? 0) + delta) }));
  };

  const placeOrder = async (event: React.FormEvent) => {
    event.preventDefault();
    if (!cartItems.length) return;
    setWorking(true);
    setError(null);
    try {
      const order = await submitOrder({
        customer_name: customer.name,
        customer_email: customer.email,
        address_line: customer.address,
        city: customer.city,
        region: customer.region,
        postal_code: customer.postalCode,
        items: cartItems.map((item) => ({ product_id: item.product.id, quantity: item.quantity })),
        scenario: "happy-path",
      });
      setSelectedOrder(order);
      setOrders((current) => [order, ...current]);
      setCart({});
      switchWorkspace("customer", order);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Order submission failed.");
    } finally {
      setWorking(false);
    }
  };

  const advance = async () => {
    if (!selectedOrder || selectedOrder.status === "delivered") return;
    setWorking(true);
    setError(null);
    try {
      const order = await advanceOrder(selectedOrder.id);
      setSelectedOrder(order);
      setOrders((current) => current.map((item) => item.id === order.id ? order : item));
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Order could not advance.");
    } finally {
      setWorking(false);
    }
  };

  if (loading) return <div className="route-loading">Loading Online Order Operations...</div>;

  const latestDecision = selectedOrder?.decisions.at(-1);
  const focusedDecision = selectedOrder?.decisions.find((decision) => decision.id === focusedDecisionId)
    ?? latestDecision;
  const selectedAiDecisions = selectedOrder?.decisions.filter((decision) => decision.method.startsWith("ai-")) ?? [];
  const delivered = orders.filter((order) => order.status === "delivered").length;
  const aiDecisions = orders.reduce(
    (total, order) => total + order.decisions.filter((decision) => decision.method.startsWith("ai-")).length,
    0,
  );

  return (
    <div className="page online-order-page">
      <button className="page-back-button" type="button" onClick={() => navigate("/showcase?industry=retail")}><ArrowLeft size={15} aria-hidden="true" /> Back to Industry Cases</button>
      <header className="online-order-header">
        <div><span className="eyebrow">Executable workflow · SQLite</span><h1>Online Order Operations</h1><p>One persisted order, viewed from the customer, merchant, and scenario perspectives.</p></div>
        <div className="online-order-live"><span /><div><strong>Local simulation</strong><small>Happy path · deterministic seed</small></div></div>
      </header>

      <nav className="order-workspace-switcher" aria-label="Order workspace">
        {workspaceOptions.map(({ id, label, detail, icon: Icon }) => (
          <button type="button" aria-label={`${label}: ${detail}`} className={workspace === id ? "active" : ""} onClick={() => switchWorkspace(id)} key={id}>
            <Icon size={18} aria-hidden="true" /><div><strong>{label}</strong><small>{detail}</small></div>
          </button>
        ))}
        <button className="open-workspace-button" type="button" onClick={() => openWorkspace(workspace)} title="Open this workspace in another window" aria-label="Open current workspace in another window"><ExternalLink size={17} /></button>
      </nav>

      {error ? <div className="error-banner">{error}</div> : null}

      {workspace === "customer" ? selectedOrder ? (
        <CustomerTracking order={selectedOrder} onOpenMerchant={() => switchWorkspace("operations")} onShopAgain={() => { setSelectedOrder(null); window.history.replaceState({}, "", "/online-order?view=customer"); }} />
      ) : (
        <div className="storefront-layout">
          <main className="storefront-main">
            <div className="storefront-heading"><div><span>Northline Supply</span><h2>Built for everyday movement</h2></div><small>{products.length} products · Synthetic inventory</small></div>
            <section className="storefront-grid" aria-label="Products">
              {products.map((product) => (
                <article className="storefront-product" key={product.id}>
                  <div className="storefront-product-image"><img src={product.image_url} alt={product.name} /></div>
                  <div className="storefront-product-copy"><span>{product.category}</span><strong>{product.name}</strong><p>{product.description}</p><div><b>{money(product.price_cents)}</b><small>{product.quantity_available} available</small></div></div>
                  <button type="button" onClick={() => updateCart(product.id, 1)}><Plus size={15} aria-hidden="true" /> Add to cart</button>
                </article>
              ))}
            </section>
          </main>
          <aside className="storefront-checkout">
            <div className="checkout-heading"><ShoppingBag size={18} aria-hidden="true" /><div><span>Cart</span><strong>{cartItems.reduce((total, item) => total + item.quantity, 0)} items</strong></div></div>
            {!cartItems.length ? <div className="empty-cart"><ShoppingBag size={28} aria-hidden="true" /><p>Add a product to begin a persisted order.</p></div> : (
              <div className="checkout-lines">{cartItems.map(({ product, quantity }) => (
                <div key={product.id}><img src={product.image_url} alt="" /><div><strong>{product.name}</strong><span>{money(product.price_cents)}</span></div><div className="quantity-stepper"><button type="button" onClick={() => updateCart(product.id, -1)} aria-label={`Remove one ${product.name}`}><Minus size={12} /></button><output>{quantity}</output><button type="button" onClick={() => updateCart(product.id, 1)} aria-label={`Add one ${product.name}`}><Plus size={12} /></button></div></div>
              ))}</div>
            )}
            <form className="checkout-form" onSubmit={placeOrder}>
              <label><span>Name</span><input required value={customer.name} onChange={(event) => setCustomer({ ...customer, name: event.target.value })} /></label>
              <label><span>Email</span><input required type="email" value={customer.email} onChange={(event) => setCustomer({ ...customer, email: event.target.value })} /></label>
              <label><span>Address</span><input required value={customer.address} onChange={(event) => setCustomer({ ...customer, address: event.target.value })} /></label>
              <div className="checkout-form-row"><label><span>City</span><input required value={customer.city} onChange={(event) => setCustomer({ ...customer, city: event.target.value })} /></label><label><span>Region</span><input required maxLength={3} value={customer.region} onChange={(event) => setCustomer({ ...customer, region: event.target.value })} /></label><label><span>Postal code</span><input required value={customer.postalCode} onChange={(event) => setCustomer({ ...customer, postalCode: event.target.value })} /></label></div>
              <div className="checkout-total"><span>Subtotal</span><strong>{money(cartSubtotal)}</strong><small>{cartSubtotal >= 10_000 ? "Free shipping" : "+ $8.00 shipping"}</small></div>
              <button className="primary-button" type="submit" disabled={!cartItems.length || working}>{working ? "Placing order..." : "Place order"}<ArrowRight size={16} aria-hidden="true" /></button>
            </form>
          </aside>
        </div>
      ) : null}

      {workspace === "operations" ? (
        <div className="operations-layout">
          <aside className="operations-queue">
            <div className="operations-panel-heading"><span>Order queue</span><strong>{orders.length} orders</strong></div>
            {!orders.length ? <p className="operations-empty">Place an order in the Customer workspace to populate this queue.</p> : orders.map((order) => (
              <button type="button" className={selectedOrder?.id === order.id ? "active" : ""} onClick={() => { setSelectedOrder(order); setFocusedDecisionId(null); }} key={order.id}>
                <div><strong>{order.display_id}</strong><span>{order.customer.name}</span></div><small>{statusLabels[order.status]}</small><b>{money(order.total_cents)}</b>
              </button>
            ))}
          </aside>
          <main className="operations-order">
            {selectedOrder ? <>
              <header><div><span>Selected order</span><h2>{selectedOrder.display_id}</h2><p>{selectedOrder.customer.name} · {selectedOrder.items.length} products · {money(selectedOrder.total_cents)}</p></div><button className="primary-button compact" type="button" disabled={working || selectedOrder.status === "delivered"} onClick={() => void advance()}><Play size={15} aria-hidden="true" /> {selectedOrder.status === "delivered" ? "Workflow complete" : working ? "Advancing..." : "Run to next step"}</button></header>
              <div className="operations-progress"><StatusTrack order={selectedOrder} /></div>
              <div className="order-section-heading"><Clock3 size={18} aria-hidden="true" /><div><span>Persisted events</span><strong>Live order timeline</strong></div></div>
              <EventTimeline order={selectedOrder} />
            </> : <div className="operations-empty">Select an order to inspect its workflow.</div>}
          </main>
          <aside className="operations-decision">
            <div className="operations-panel-heading"><span>Decision inspector</span><strong>{focusedDecisionId === null ? "Latest decision" : "Selected decision"}</strong></div>
            {selectedOrder?.decisions.length ? <nav className="order-decision-history" aria-label="Order decision history">
              {selectedOrder.decisions.map((decision, index) => (
                <button type="button" aria-pressed={focusedDecision?.id === decision.id} className={focusedDecision?.id === decision.id ? "active" : ""} onClick={() => setFocusedDecisionId(decision.id)} onDoubleClick={() => decision.algorithm_profile && setAlgorithmDecision(decision)} title={decision.algorithm_profile ? "Double-click to explore this algorithm" : undefined} key={decision.id}>
                  <span>{index + 1}</span><div><strong>{decision.decision_type.replaceAll("_", " ")}</strong><small>{decision.method.replaceAll("-", " ")}</small></div>{decision.impact ? <b>{decisionOutput(decision.impact.output_value, decision.impact.output_unit)}</b> : null}
                </button>
              ))}
            </nav> : null}
            <DecisionPanel decision={focusedDecision} onExplore={setAlgorithmDecision} />
            {selectedOrder ? <button className="secondary-button operations-customer-link" type="button" onClick={() => openWorkspace("customer", selectedOrder)}><ExternalLink size={15} aria-hidden="true" /> Open customer view</button> : null}
          </aside>
        </div>
      ) : null}

      {workspace === "scenario" ? (
        <div className="scenario-control-layout">
          <section className="scenario-summary">
            <div><span>Scenario</span><h2>Happy path</h2><p>A deterministic first slice: one order advances through every normal business transition while events and decisions remain inspectable.</p></div>
            <dl><div><dt>Seed</dt><dd>1042</dd></div><div><dt>Persistence</dt><dd>SQLite</dd></div><div><dt>Execution</dt><dd>One step at a time</dd></div></dl>
          </section>
          <section className="scenario-metrics" aria-label="Simulation metrics">
            <div><strong>{orders.length}</strong><span>orders created</span></div><div><strong>{orders.length - delivered}</strong><span>active orders</span></div><div><strong>{delivered}</strong><span>delivered</span></div><div><strong>{aiDecisions}</strong><span>AI decisions</span></div>
          </section>
          <section className="scenario-runner">
            <div className="order-section-heading"><SlidersHorizontal size={18} aria-hidden="true" /><div><span>Run control</span><strong>{selectedOrder ? selectedOrder.display_id : "No selected order"}</strong></div></div>
            {selectedOrder ? <><StatusTrack order={selectedOrder} /><div className="scenario-runner-actions"><button className="primary-button compact" type="button" disabled={working || selectedOrder.status === "delivered"} onClick={() => void advance()}><Play size={15} aria-hidden="true" /> Run to next step</button><button className="secondary-button" type="button" onClick={() => switchWorkspace("operations")}><ListChecks size={15} aria-hidden="true" /> Inspect merchant view</button><button className="secondary-button" type="button" onClick={() => openWorkspace("customer", selectedOrder)}><ExternalLink size={15} aria-hidden="true" /> Open customer window</button></div></> : <div className="scenario-empty"><UserRound size={24} aria-hidden="true" /><p>Create an order in the Customer workspace to start the simulation.</p><button className="secondary-button" type="button" onClick={() => switchWorkspace("customer")}><Store size={15} aria-hidden="true" /> Open storefront</button></div>}
          </section>
          <section className="scenario-ai-impact">
            <header><div><span>AI impact trace</span><h2>How model outputs changed this order</h2><p>Each card connects input signals to an output, the policy threshold that interpreted it, and the workflow branch that followed.</p></div><strong>{selectedAiDecisions.length} AI decisions</strong></header>
            {selectedAiDecisions.length ? <div className="scenario-ai-impact-grid">{selectedAiDecisions.map((decision) => <DecisionPanel decision={decision} onExplore={setAlgorithmDecision} key={decision.id} />)}</div> : <div className="scenario-ai-empty"><BrainCircuit size={24} aria-hidden="true" /><p>Advance the order through payment screening to populate the AI impact trace.</p></div>}
          </section>
          <section className="scenario-algorithm-heading">
            <div><span>Algorithm catalog</span><h2>Four decision engines, two trained models</h2><p>The address rule engine and allocation optimizer do not learn from labels. The payment classifier and delivery predictor require training, temporal testing, calibration, and production monitoring.</p></div>
            <strong>Open or double-click any engine</strong>
          </section>
          <section className="scenario-boundaries" aria-label="Decision algorithms">
            {algorithmCards.map(({ decisionType, label, detail, icon: Icon }) => {
              const decision = selectedOrder?.decisions.find((item) => item.decision_type === decisionType);
              return (
                <button
                  type="button"
                  disabled={!decision?.algorithm_profile}
                  onClick={() => decision?.algorithm_profile && setAlgorithmDecision(decision)}
                  onDoubleClick={() => decision?.algorithm_profile && setAlgorithmDecision(decision)}
                  title={decision?.algorithm_profile ? "Open algorithm details" : "Advance the order to unlock this algorithm"}
                  key={decisionType}
                >
                  <Icon size={18} aria-hidden="true" />
                  <strong>{label}</strong>
                  <span>{detail}</span>
                  <small>{decision?.algorithm_profile ? "Open details" : "Not reached"}</small>
                </button>
              );
            })}
          </section>
        </div>
      ) : null}
      {algorithmDecision?.algorithm_profile ? <AlgorithmDrilldown decision={algorithmDecision} onClose={() => setAlgorithmDecision(null)} /> : null}
    </div>
  );
}
