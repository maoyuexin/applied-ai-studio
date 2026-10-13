import {
  BellRing,
  CircleCheck,
  CircleX,
  Clock3,
  FileText,
  Lock,
  MapPin,
  MessageSquareText,
  Search,
  ShieldCheck,
  UserRound,
} from "lucide-react";
import type { ReactNode } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import type { Run, RunEvent, ScenarioSpec, StageSpec } from "./types";

export interface VisualContext {
  scenario: ScenarioSpec;
  run: Run;
  stage: StageSpec;
  stageEvents: RunEvent[];
  seen: RunEvent[];
  onDecide?: (requestId: string, approved: boolean) => void;
  deciding?: string | null;
}

type Visual = (ctx: VisualContext) => ReactNode;

/* ---------- payload shapes (as returned by the tools) ---------- */
interface Transaction {
  merchant: string;
  location: string;
  amount_usd: number;
  category: string;
  occurred_at: string;
  amount_vs_card_average: string;
  card_transactions_last_24h: number;
  distance_from_home_km: number;
  card_last4: string;
}
interface Reason {
  feature: string;
  value: string;
  pushes: string;
  weight: number;
}
interface FraudScore {
  model: string;
  fraud_score: number;
  review_threshold: number;
  decision: string;
  top_reasons: Reason[];
  note?: string;
}
interface Patient {
  name: string;
  age: number;
  sex: string;
  home_city: string;
  max_travel_miles: number;
  summary: string;
  synthetic?: boolean;
}
interface TrialHit {
  nct_id: string;
  title: string;
  phase?: string;
}
interface SearchResult {
  search?: { condition?: string; keywords?: string; center?: string; radius_miles?: number };
  total_recruiting_matches: number;
  returned: number;
  trials: TrialHit[];
}
interface BasicCheck {
  nct_id: string;
  overall: string;
  checks: { check: string; result: string }[];
}
interface Trial {
  nct_id: string;
  title: string;
  phase?: string;
  overall_status?: string;
  nearest_open_site?: { facility?: string; city?: string; state?: string; miles?: number } | null;
}
interface Driver {
  signal: string;
  reading: string;
  normal: string;
  meaning: string;
}
interface MachineScore {
  asset: string;
  window: string;
  hours_with_data: number;
  policy: string;
  peak_score: number;
  peak_at: string;
  median_score: number;
  route_at_peak: string;
  hours_at_work_order_level: number;
  hours_in_watch_band: number;
  drivers: Driver[];
  note?: string;
}
interface Passage {
  citation: string;
  source: string;
  score: number;
  text: string;
}
interface WorkOrder {
  work_order_needed?: boolean;
  asset?: string;
  priority?: string;
  problem?: string;
  steps?: string[];
  safety?: string[];
  citations?: string[];
  due_within_hours?: number;
}
interface Forecast {
  product: string;
  unit_price: number;
  forecast_units: number;
  range_units: [number, number];
  expected_sales_usd: number;
}
interface ClaimsResult {
  passed: boolean;
  issues: { phrase: string; rule: string; fix: string }[];
}

/* ---------- helpers ---------- */
const last = <T,>(items: T[]): T | undefined => items[items.length - 1];

function messages(events: RunEvent[], agent?: string): RunEvent[] {
  return events.filter((e) => e.type === "message" && e.text && (!agent || e.agent === agent));
}

function results<T>(ctx: VisualContext, tool: string, scope: "stage" | "seen" = "stage"): T[] {
  const ids = new Set(ctx.stageEvents.filter((e) => e.type === "tool_call" && e.tool === tool).map((e) => e.call_id));
  const pool = ctx.seen.filter((e) => e.type === "tool_result" && e.tool === tool && e.ok !== false);
  const picked = scope === "stage" && ids.size ? pool.filter((e) => ids.has(e.call_id)) : pool;
  return picked.map((e) => e.result as T);
}

function pendingCalls(ctx: VisualContext, tool: string): number {
  const done = new Set(ctx.seen.filter((e) => e.type === "tool_result").map((e) => e.call_id));
  return ctx.stageEvents.filter((e) => e.type === "tool_call" && e.tool === tool && !done.has(e.call_id)).length;
}

function Pending({ label }: { label: string }) {
  return (
    <p className="awb-pending">
      <span className="awb-dots" aria-hidden="true">
        <i />
        <i />
        <i />
      </span>
      {label}
    </p>
  );
}

function Markdown({ text }: { text: string }) {
  return (
    <div className="aw-markdown">
      <ReactMarkdown remarkPlugins={[remarkGfm]}>{text}</ReactMarkdown>
    </div>
  );
}

function humanize(key: string): string {
  const text = key.replace(/_/g, " ");
  return text.charAt(0).toUpperCase() + text.slice(1);
}

function argValue(value: unknown): string {
  if (Array.isArray(value)) return value.join(", ");
  if (value && typeof value === "object") return JSON.stringify(value);
  return String(value ?? "");
}

function plainLines(text: string): string[] {
  return text
    .split("\n")
    .map((line) => line.replace(/^#+\s*/, "").replace(/\*\*/g, "").replace(/\s+$/, "").trim())
    .filter(Boolean);
}

function money(value: number, digits = 2): string {
  return `$${value.toLocaleString("en-US", { minimumFractionDigits: digits, maximumFractionDigits: digits })}`;
}

function score(value: number): string {
  return Number.isInteger(value) ? value.toFixed(1) : String(value);
}

function when(value: string): string {
  const date = new Date(value.replace(" ", "T"));
  if (Number.isNaN(date.getTime())) return value;
  return date.toLocaleString("en-US", { month: "short", day: "numeric", year: "numeric", hour: "numeric", minute: "2-digit" });
}

function Fact({ label, value, wide }: { label: string; value: ReactNode; wide?: boolean }) {
  return (
    <div className={wide ? "awb-fact is-wide" : "awb-fact"}>
      <dt>{label}</dt>
      <dd>{value}</dd>
    </div>
  );
}

/* ---------- visuals ---------- */
const alert: Visual = ({ run, scenario }) => (
  <div className="awb-alert">
    <span className="awb-alert-icon" aria-hidden="true">
      <BellRing size={26} />
    </span>
    <div>
      <p className="awb-kicker">New request · {scenario.industry}</p>
      <h4>{run.task.label}</h4>
      <blockquote>{run.task.prompt}</blockquote>
    </div>
  </div>
);

const receipt: Visual = (ctx) => {
  const r = last(results<Transaction>(ctx, "get_transaction"));
  if (!r) return <Pending label="Looking up the purchase…" />;
  return (
    <div className="awb-receipt">
      <div className="awb-receipt-main">
        <p className="awb-kicker">Card ending {r.card_last4}</p>
        <strong className="awb-amount">{money(r.amount_usd)}</strong>
        <span>{r.merchant}</span>
        <span className="awb-tag">{r.category}</span>
      </div>
      <dl className="awb-facts">
        <Fact label="When" value={when(r.occurred_at)} />
        <Fact label="Where" value={r.location} />
        <Fact label="Compared with this card's usual amount" value={<b>{r.amount_vs_card_average}</b>} />
        <Fact label="Purchases on this card in the last 24 h" value={r.card_transactions_last_24h} />
        <Fact label="Distance from home" value={`${r.distance_from_home_km.toLocaleString("en-US")} km`} />
      </dl>
    </div>
  );
};

function Meter({ value, cut, max = 1, label }: { value: number; cut: number; max?: number; label: string }) {
  const pct = (v: number) => `${Math.max(0, Math.min(100, (v / max) * 100))}%`;
  const above = value >= cut;
  return (
    <div className="awb-meter" role="img" aria-label={label}>
      <div className="awb-meter-track">
        <span className="awb-meter-zone is-low" style={{ width: pct(cut) }} />
        <span className="awb-meter-zone is-high" style={{ left: pct(cut), width: `calc(100% - ${pct(cut)})` }} />
        <span className="awb-meter-cut" style={{ left: pct(cut) }}>
          <em>cutoff {score(cut)}</em>
        </span>
        <span className={above ? "awb-meter-dot is-high" : "awb-meter-dot"} style={{ left: pct(value) }}>
          <em>{score(value)}</em>
        </span>
      </div>
      <div className="awb-meter-ends">
        <span>0 · normal</span>
        <span>review · {max}</span>
      </div>
    </div>
  );
}

function ReasonBars({ reasons }: { reasons: Reason[] }) {
  const top = Math.max(...reasons.map((r) => Math.abs(r.weight)), 0.0001);
  return (
    <ul className="awb-bars">
      {reasons.map((reason) => (
        <li key={reason.feature} className={reason.pushes.includes("review") ? "is-up" : "is-down"}>
          <span className="awb-bar-label">
            {reason.feature}: <b>{reason.value}</b>
          </span>
          <span className="awb-bar">
            <i style={{ width: `${(Math.abs(reason.weight) / top) * 100}%` }} />
          </span>
          <span className="awb-bar-note">{reason.pushes}</span>
        </li>
      ))}
    </ul>
  );
}

const risk: Visual = (ctx) => {
  const r = last(results<FraudScore>(ctx, "score_transaction"));
  if (!r) return <Pending label="Asking the fraud model for a score…" />;
  const review = r.decision === "review";
  return (
    <div className="awb-risk">
      <div className="awb-risk-head">
        <div>
          <p className="awb-kicker">{r.model} · fraud score</p>
          <strong className="awb-big">{score(r.fraud_score)}</strong>
        </div>
        <span className={review ? "awb-verdict is-high" : "awb-verdict is-low"}>{review ? "Review" : "Normal"}</span>
      </div>
      <Meter value={r.fraud_score} cut={r.review_threshold} label={`Score ${r.fraud_score}, cutoff ${r.review_threshold}`} />
      <p className="awb-caption">
        {r.fraud_score >= r.review_threshold ? "At or above" : "Below"} the bank's cutoff, so the model says <b>{review ? "review" : "normal"}</b>.
        The score ranks risk; it does not prove fraud.
      </p>
      <p className="awb-kicker is-gap">Why: what pushed the score</p>
      <ReasonBars reasons={r.top_reasons} />
    </div>
  );
};

function Slip({ ctx, event }: { ctx: VisualContext; event: RunEvent }) {
  const spec = ctx.scenario.tools.find((tool) => tool.id === event.tool);
  const args = (event.args ?? {}) as Record<string, unknown>;
  return (
    <div className="awb-slip">
      <p className="awb-kicker">
        <Lock size={12} /> Request · {spec?.label ?? event.tool}
      </p>
      <dl className="awb-facts is-single">
        {Object.entries(args).map(([key, value]) => (
          <Fact key={key} label={humanize(key)} value={argValue(value)} wide />
        ))}
      </dl>
    </div>
  );
}

const request: Visual = (ctx) => {
  const call = ctx.stageEvents.find((e) => e.type === "tool_call" && e.approval);
  if (!call) return <Pending label="Preparing the request…" />;
  return (
    <div className="awb-request">
      <Slip ctx={ctx} event={call} />
      <p className="awb-caption">
        <Lock size={13} /> Locked: nothing happens until a person approves.
      </p>
    </div>
  );
};

const approval: Visual = (ctx) => {
  const ask = ctx.stageEvents.find((e) => e.type === "approval_request") ?? last(ctx.seen.filter((e) => e.type === "approval_request"));
  const call = ctx.stageEvents.find((e) => e.type === "tool_call" && e.approval);
  if (!ask) return call ? <Slip ctx={ctx} event={call} /> : <Pending label="Preparing the request…" />;
  const answer = ctx.seen.find((e) => e.type === "approval_response" && e.request_id === ask.request_id);
  const person = ctx.scenario.business?.actors.find((a) => a.id === ctx.stage.actor)?.label ?? "A person";
  const state = !answer ? "waiting" : answer.approved ? "approved" : "rejected";
  return (
    <div className="awb-approval">
      <Slip ctx={ctx} event={ask} />
      <div className={`awb-stamp is-${state}`}>
        <span className="awb-stamp-person" aria-hidden="true">
          <UserRound size={28} />
        </span>
        <strong>{state === "waiting" ? "Waiting for a person" : state === "approved" ? "Approved" : "Rejected"}</strong>
        <small>{person}</small>
        {state === "waiting" && ctx.onDecide && ask.request_id ? (
          <span className="aw-approval-actions">
            <button type="button" className="aw-approve" disabled={ctx.deciding === ask.request_id} onClick={() => ctx.onDecide?.(ask.request_id as string, true)}>
              <CircleCheck size={15} /> Approve
            </button>
            <button type="button" className="aw-reject" disabled={ctx.deciding === ask.request_id} onClick={() => ctx.onDecide?.(ask.request_id as string, false)}>
              <CircleX size={15} /> Reject
            </button>
          </span>
        ) : null}
      </div>
    </div>
  );
};

const note: Visual = (ctx) => {
  const message = last(messages(ctx.stageEvents)) ?? last(messages(ctx.seen));
  if (!message?.text) return <Pending label="Writing…" />;
  const short = message.text.length < 40;
  return (
    <div className={short ? "awb-note is-short" : "awb-note"}>
      <p className="awb-kicker">
        <FileText size={12} /> Final message
      </p>
      {short ? <strong>{message.text}</strong> : <Markdown text={message.text} />}
    </div>
  );
};

const patient: Visual = (ctx) => {
  const r = last(results<Patient>(ctx, "get_patient"));
  if (!r) return <Pending label="Reading the patient record…" />;
  return (
    <div className="awb-person">
      <span className="awb-avatar" aria-hidden="true">
        <UserRound size={30} />
      </span>
      <div>
        <h4>
          {r.name} {r.synthetic ? <span className="awb-tag">synthetic</span> : null}
        </h4>
        <dl className="awb-facts">
          <Fact label="Age" value={r.age} />
          <Fact label="Sex" value={r.sex.charAt(0) + r.sex.slice(1).toLowerCase()} />
          <Fact label="Home" value={r.home_city} />
          <Fact label="Will travel" value={`up to ${r.max_travel_miles} miles`} />
        </dl>
        <p className="awb-summary">{r.summary}</p>
      </div>
    </div>
  );
};

const search: Visual = (ctx) => {
  const found = results<SearchResult>(ctx, "search_trials", "seen");
  const waiting = pendingCalls(ctx, "search_trials");
  if (!found.length) return <Pending label="Searching the registry…" />;
  const unique = new Map<string, TrialHit>();
  found.forEach((r) => r.trials.forEach((t) => unique.set(t.nct_id, t)));
  const empty = found.filter((r) => r.total_recruiting_matches === 0).length;
  const total = found.reduce((sum, r) => sum + r.total_recruiting_matches, 0);
  const steps = [
    { label: "Searches run", value: found.length },
    { label: "Recruiting matches found", value: total },
    { label: "Different trials to look at", value: unique.size },
  ];
  const top = Math.max(...steps.map((s) => s.value), 1);
  const latest = last(found)?.search;
  return (
    <div className="awb-search">
      <ul className="awb-funnel">
        {steps.map((step) => (
          <li key={step.label}>
            <span>{step.label}</span>
            <span className="awb-bar">
              <i style={{ width: `${(step.value / top) * 100}%` }} />
            </span>
            <b>{step.value}</b>
          </li>
        ))}
      </ul>
      {latest ? (
        <p className="awb-caption">
          <Search size={13} /> Latest search: <b>{latest.condition}</b>
          {latest.keywords ? <> + “{latest.keywords}”</> : null}
          {latest.radius_miles ? <> within {latest.radius_miles} miles of {latest.center}</> : null}
        </p>
      ) : null}
      {empty ? <p className="awb-caption">{empty} search{empty > 1 ? "es" : ""} found nothing, so the assistant tried other words.</p> : null}
      <ul className="awb-chips">
        {[...unique.values()].slice(0, 12).map((trial) => (
          <li key={trial.nct_id} title={trial.title}>
            {trial.nct_id}
          </li>
        ))}
      </ul>
      {waiting ? <Pending label={`${waiting} search${waiting > 1 ? "es" : ""} running…`} /> : null}
    </div>
  );
};

const checks: Visual = (ctx) => {
  const rows = results<BasicCheck>(ctx, "check_basics", "seen");
  if (!rows.length) return <Pending label="Checking the basics…" />;
  const columns = rows[0].checks.map((c) => c.check);
  return (
    <div className="awb-grid-wrap">
      <table className="awb-grid">
        <thead>
          <tr>
            <th>Trial</th>
            {columns.map((name) => (
              <th key={name}>{humanize(name)}</th>
            ))}
            <th>Overall</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => (
            <tr key={row.nct_id}>
              <td>{row.nct_id}</td>
              {row.checks.map((c) => (
                <td key={c.check} className={`is-${c.result}`}>
                  {c.result === "pass" ? <CircleCheck size={16} aria-label="pass" /> : c.result === "fail" ? <CircleX size={16} aria-label="fail" /> : c.result}
                </td>
              ))}
              <td className={`is-${row.overall}`}>{row.overall}</td>
            </tr>
          ))}
        </tbody>
      </table>
      <p className="awb-caption">Plain code, not AI: the same facts give the same answer every time.</p>
    </div>
  );
};

const trials: Visual = (ctx) => {
  const list = results<Trial>(ctx, "get_trial", "seen");
  if (!list.length) return <Pending label="Opening the trials…" />;
  return (
    <ul className="awb-cards">
      {list.map((trial) => (
        <li key={trial.nct_id}>
          <p className="awb-kicker">
            {trial.nct_id} · {trial.phase?.replace(/PHASE/g, "Phase ")}
          </p>
          <strong>{trial.title}</strong>
          {trial.nearest_open_site ? (
            <span className="awb-caption">
              <MapPin size={12} /> {trial.nearest_open_site.city}, {trial.nearest_open_site.state}
              {trial.nearest_open_site.miles !== undefined ? ` · ${trial.nearest_open_site.miles} miles` : ""}
            </span>
          ) : null}
        </li>
      ))}
    </ul>
  );
};

const shortlist: Visual = (ctx) => {
  const message = last(messages(ctx.stageEvents));
  if (!message?.text) return <Pending label="Writing the shortlist…" />;
  return (
    <div className="awb-doc">
      <Markdown text={message.text} />
    </div>
  );
};

function thresholds(policy: string): { work: number; watch: number } | null {
  const work = /work order at a score of ([\d.]+)/i.exec(policy);
  const watch = /watch from ([\d.]+)/i.exec(policy);
  return work && watch ? { work: Number(work[1]), watch: Number(watch[1]) } : null;
}

const machine: Visual = (ctx) => {
  const r = last(results<MachineScore>(ctx, "score_machine"));
  if (!r) return <Pending label="Scoring the sensor week…" />;
  const limits = thresholds(r.policy);
  const max = Math.max(r.peak_score * 1.15, (limits?.work ?? 1) * 1.6);
  const pct = (v: number) => `${Math.min(100, (v / max) * 100)}%`;
  const quiet = Math.max(0, r.hours_with_data - r.hours_at_work_order_level - r.hours_in_watch_band);
  const hours = [
    { label: "Work-order level", value: r.hours_at_work_order_level, cls: "is-high" },
    { label: "Watch", value: r.hours_in_watch_band, cls: "is-mid" },
    { label: "Normal", value: quiet, cls: "is-low" },
  ];
  return (
    <div className="awb-machine">
      <div className="awb-risk-head">
        <div>
          <p className="awb-kicker">{r.asset} · highest score this week</p>
          <strong className="awb-big">{r.peak_score}</strong>
        </div>
        <span className={r.route_at_peak.toLowerCase().includes("work order") ? "awb-verdict is-high" : r.route_at_peak.toLowerCase().includes("watch") ? "awb-verdict is-mid" : "awb-verdict is-low"}>
          {r.route_at_peak}
        </span>
      </div>
      {limits ? (
        <div className="awb-meter" role="img" aria-label={`Peak ${r.peak_score}; watch from ${limits.watch}; work order from ${limits.work}`}>
          <div className="awb-meter-track">
            <span className="awb-meter-zone is-low" style={{ width: pct(limits.watch) }} />
            <span className="awb-meter-zone is-mid" style={{ left: pct(limits.watch), width: `calc(${pct(limits.work)} - ${pct(limits.watch)})` }} />
            <span className="awb-meter-zone is-high" style={{ left: pct(limits.work), width: `calc(100% - ${pct(limits.work)})` }} />
            <span className="awb-meter-cut" style={{ left: pct(limits.watch) }}>
              <em>watch {limits.watch}</em>
            </span>
            <span className="awb-meter-cut" style={{ left: pct(limits.work) }}>
              <em>work order {limits.work}</em>
            </span>
            <span className="awb-meter-dot is-ghost" style={{ left: pct(r.median_score) }} title={`Typical hour: ${r.median_score}`} />
            <span className={r.peak_score >= limits.work ? "awb-meter-dot is-high" : "awb-meter-dot"} style={{ left: pct(r.peak_score) }}>
              <em>{r.peak_score}</em>
            </span>
          </div>
          <div className="awb-meter-ends">
            <span>0 · the machine's own normal</span>
            <span>typical hour this week: {r.median_score}</span>
          </div>
        </div>
      ) : null}
      <p className="awb-kicker">Hours this week ({r.hours_with_data} with data)</p>
      <div className="awb-stack" role="img" aria-label={hours.map((h) => `${h.label} ${h.value} h`).join(", ")}>
        {hours.map((h) => (h.value ? <i key={h.label} className={h.cls} style={{ flex: h.value }} title={`${h.label}: ${h.value} h`} /> : null))}
      </div>
      <ul className="awb-legend">
        {hours.map((h) => (
          <li key={h.label} className={h.cls}>
            {h.label}: <b>{h.value} h</b>
          </li>
        ))}
      </ul>
      <p className="awb-kicker">What looks different</p>
      <ul className="awb-drivers">
        {r.drivers.map((d) => (
          <li key={d.signal}>
            <span>{d.signal}</span>
            <b>{d.reading}</b>
            <small>normal: {d.normal}</small>
          </li>
        ))}
      </ul>
    </div>
  );
};

const manual: Visual = (ctx) => {
  const found = results<{ passages: Passage[] }>(ctx, "search_procedures").flatMap((r) => r.passages ?? []);
  const route = last(messages(ctx.stageEvents, "diagnose"));
  const waiting = pendingCalls(ctx, "search_procedures");
  const headline = route?.text ? plainLines(route.text)[0] : null;
  if (!found.length && !headline) return <Pending label="Searching the maintenance manuals…" />;
  return (
    <div className="awb-manual">
      {headline ? <p className="awb-callout">{headline}</p> : null}
      {found.length ? (
        <ul className="awb-cards">
          {found.map((p) => (
            <li key={`${p.citation}-${p.text.slice(0, 20)}`}>
              <p className="awb-kicker">
                <FileText size={12} /> {p.citation} · {p.source}
              </p>
              <span className="awb-excerpt">{p.text}</span>
              <span className="awb-caption">wording match {p.score}</span>
            </li>
          ))}
        </ul>
      ) : headline ? (
        <p className="awb-caption">No manual search was needed for this week.</p>
      ) : null}
      {waiting ? <Pending label="Searching the manuals…" /> : null}
    </div>
  );
};

function parseJson<T>(text: string): T | null {
  const block = /```json\s*([\s\S]*?)```/.exec(text)?.[1] ?? text;
  try {
    return JSON.parse(block) as T;
  } catch {
    return null;
  }
}

const workorder: Visual = (ctx) => {
  const message = last(messages(ctx.stageEvents, "planner"));
  if (!message?.text) return <Pending label="Drafting the work order…" />;
  const order = parseJson<WorkOrder>(message.text);
  if (!order) return <Markdown text={message.text} />;
  if (!order.work_order_needed) {
    return (
      <div className="awb-form is-none">
        <p className="awb-kicker">Work order</p>
        <h4>No work order needed</h4>
        <p>{order.problem}</p>
      </div>
    );
  }
  return (
    <div className="awb-form">
      <div className="awb-form-head">
        <div>
          <p className="awb-kicker">Work order · {order.asset}</p>
          <h4>{order.problem}</h4>
        </div>
        <span className={`awb-verdict is-${order.priority === "high" ? "high" : order.priority === "medium" ? "mid" : "low"}`}>
          {order.priority} priority
        </span>
      </div>
      <p className="awb-caption">
        <Clock3 size={13} /> Due within {order.due_within_hours} hours
      </p>
      <div className="awb-form-cols">
        <div>
          <p className="awb-kicker">Steps</p>
          <ol>
            {(order.steps ?? []).map((step) => (
              <li key={step}>{step}</li>
            ))}
          </ol>
        </div>
        <div>
          <p className="awb-kicker">
            <ShieldCheck size={12} /> Safety first
          </p>
          <ul>
            {(order.safety ?? []).map((step) => (
              <li key={step}>{step}</li>
            ))}
          </ul>
          <p className="awb-kicker">Sources</p>
          <ul className="awb-chips">
            {(order.citations ?? []).map((c) => (
              <li key={c}>{c}</li>
            ))}
          </ul>
        </div>
      </div>
    </div>
  );
};

const fieldcheck: Visual = (ctx) => {
  const step = last(ctx.stageEvents.filter((e) => e.type === "code_step"));
  if (!step?.checks) return <Pending label="Checking…" />;
  return (
    <div className="awb-checklist">
      <h4 className={step.passed ? "is-ok" : "is-bad"}>
        {step.passed ? <CircleCheck size={18} /> : <CircleX size={18} />} {step.checks.filter((c) => c.ok).length} of {step.checks.length} checks passed
      </h4>
      <ul>
        {step.checks.map((c) => (
          <li key={c.check} className={c.ok ? "is-ok" : "is-bad"}>
            {c.ok ? <CircleCheck size={15} /> : <CircleX size={15} />} {c.check}
            {c.detail ? <small> · {c.detail}</small> : null}
          </li>
        ))}
      </ul>
      <p className="awb-caption">Plain code, not AI. If a rule fails, the dispatcher may not file the order.</p>
    </div>
  );
};

const ticket: Visual = (ctx) => {
  const message = last(messages(ctx.stageEvents));
  if (!message?.text) return <Pending label="Writing the spec…" />;
  return (
    <div className="awb-doc is-ticket">
      <p className="awb-kicker">
        <FileText size={12} /> {ctx.run.task.label}
      </p>
      <Markdown text={message.text} />
    </div>
  );
};

const code: Visual = (ctx) => {
  const message = last(messages(ctx.stageEvents, "developer"));
  if (!message?.text) return <Pending label="Writing the code…" />;
  const block = /```(?:python)?\s*([\s\S]*?)```/.exec(message.text)?.[1] ?? message.text;
  const rest = message.text.replace(/```[\s\S]*?```/, "").trim();
  return (
    <div className="awb-code">
      <ol>
        {block.replace(/\s+$/, "").split("\n").map((line, index) => (
          <li key={index}>
            <code>{line || " "}</code>
          </li>
        ))}
      </ol>
      {rest ? <p className="awb-caption">{rest}</p> : null}
    </div>
  );
};

interface TestRow {
  id: string;
  call: string;
  expected: string;
  got: string;
  pass: boolean;
}

function testRows(text: string): TestRow[] {
  return text
    .split("\n")
    .filter((line) => line.trim().startsWith("|"))
    .map((line) => line.split("|").slice(1, -1).map((cell) => cell.trim().replace(/`/g, "")))
    .filter((cells) => cells.length >= 5 && /^\d+$/.test(cells[0]))
    .map((cells) => ({ id: cells[0], call: cells[1], expected: cells[2], got: cells[3], pass: /pass/i.test(cells[4]) }));
}

const tests: Visual = (ctx) => {
  const message = last(messages(ctx.stageEvents, "tester"));
  const cases = last(results<unknown[]>(ctx, "get_acceptance_tests"));
  const rows = message?.text ? testRows(message.text) : [];
  if (!rows.length) {
    if (!cases) return <Pending label="Fetching the acceptance tests…" />;
    return (
      <div className="awb-tests">
        <ul className="awb-tiles">
          {cases.map((_, index) => (
            <li key={index} className="is-wait">
              {index + 1}
            </li>
          ))}
        </ul>
        <Pending label={`Running ${cases.length} tests in the sandbox…`} />
      </div>
    );
  }
  const passed = rows.filter((row) => row.pass).length;
  return (
    <div className="awb-tests">
      <h4 className={passed === rows.length ? "is-ok" : "is-bad"}>
        {passed} of {rows.length} tests passed
      </h4>
      <ul className="awb-tiles">
        {rows.map((row) => (
          <li key={row.id} className={row.pass ? "is-ok" : "is-bad"} title={`${row.call} → expected ${row.expected}, got ${row.got}`}>
            {row.pass ? <CircleCheck size={16} /> : <CircleX size={16} />}
            <span>{row.id}</span>
          </li>
        ))}
      </ul>
      <dl className="awb-facts is-single">
        {rows.slice(0, 4).map((row) => (
          <Fact key={row.id} label={`Test ${row.id}`} value={`${row.call} → ${row.got}`} wide />
        ))}
      </dl>
      <p className="awb-caption">People wrote these tests before the agents started. The developer never saw them.</p>
    </div>
  );
};

function Bubble({ who, text }: { who: string; text: string }) {
  return (
    <div className="awb-bubble">
      <span className="awb-bubble-who">
        <MessageSquareText size={13} /> {who}
      </span>
      <Markdown text={text} />
    </div>
  );
}

const review: Visual = (ctx) => {
  const message = last(messages(ctx.stageEvents, "reviewer"));
  if (!message?.text) return <Pending label="Reading the code and the results…" />;
  return <Bubble who="Reviewer" text={message.text} />;
};

const meeting: Visual = (ctx) => {
  const turns = ctx.seen.filter((e) => e.type === "speaker" && e.agent);
  const members = ctx.scenario.agents.filter((a) => a.kind !== "chair");
  const current = last(turns)?.agent;
  return (
    <div className="awb-meeting">
      <div className="awb-table">
        <span className="awb-chair">Chair</span>
        {members.map((agent) => (
          <span key={agent.id} className={agent.id === current ? "awb-seat is-on" : "awb-seat"} style={{ ["--agent" as string]: agent.color }}>
            {agent.label}
          </span>
        ))}
      </div>
      <ol className="awb-turns">
        {turns.map((turn, index) => {
          const agent = ctx.scenario.agents.find((a) => a.id === turn.agent);
          return (
            <li key={turn.seq} style={{ ["--agent" as string]: agent?.color ?? "#9396a6" }}>
              Turn {index + 1}: <b>{agent?.label ?? turn.agent}</b>
            </li>
          );
        })}
      </ol>
      <p className="awb-caption">Everyone sees the whole conversation; the chair decides who speaks next.</p>
    </div>
  );
};

const products: Visual = (ctx) => {
  const list = results<Forecast>(ctx, "forecast_demand", "seen");
  if (!list.length) return <Pending label="Checking expected demand…" />;
  const pick = last(messages(ctx.seen, "merchandiser"))?.text ?? "";
  const top = Math.max(...list.map((f) => f.range_units[1]), 1);
  const sorted = [...list].sort((a, b) => b.expected_sales_usd - a.expected_sales_usd);
  return (
    <div className="awb-products">
      <ul className="awb-range-bars">
        {sorted.map((f) => {
          const picked = pick.includes(f.product);
          return (
            <li key={f.product} className={picked ? "is-picked" : ""}>
              <span className="awb-bar-label">
                {f.product} <small>{money(f.unit_price)}</small>
              </span>
              <span className="awb-range" title={`Range ${f.range_units[0]}–${f.range_units[1]} units`}>
                <i className="awb-range-span" style={{ left: `${(f.range_units[0] / top) * 100}%`, width: `${((f.range_units[1] - f.range_units[0]) / top) * 100}%` }} />
                <i className="awb-range-mid" style={{ left: `${(f.forecast_units / top) * 100}%` }} />
              </span>
              <b>
                {f.forecast_units} units · {money(f.expected_sales_usd, 0)}
              </b>
              {picked ? <span className="awb-tag is-on">picked</span> : null}
            </li>
          );
        })}
      </ul>
      <p className="awb-caption">Bar = the forecast's range for next week; tick = its middle estimate. A starting point, not a promise.</p>
    </div>
  );
};

function bannerParts(text: string) {
  const lines = plainLines(text);
  const offer = lines.find((line) => /%/.test(line) && line.length < 30) ?? null;
  const rest = lines.filter((line) => line !== offer);
  return { headline: rest[0] ?? "", body: rest.slice(1, -1), cta: rest.length > 1 ? rest[rest.length - 1] : null, offer, lines };
}

const banner: Visual = (ctx) => {
  const drafts = messages(ctx.seen, "copywriter");
  const mine = last(messages(ctx.stageEvents, "copywriter"));
  if (!mine?.text) return <Pending label="Drafting the banner…" />;
  const index = drafts.findIndex((d) => d.seq === mine.seq);
  const previous = index > 0 ? drafts[index - 1] : null;
  const parts = bannerParts(mine.text);
  const before = previous?.text ? plainLines(previous.text) : [];
  const changed = previous ? parts.lines.filter((line) => !before.includes(line)) : [];
  const removed = previous ? before.filter((line) => !parts.lines.includes(line)) : [];
  const mark = (line: string) => (changed.includes(line) ? "is-changed" : "");
  return (
    <div className="awb-banner-wrap">
      <div className="awb-banner">
        <div>
          <h4 className={mark(parts.headline)}>{parts.headline}</h4>
          {parts.body.map((line) => (
            <p key={line} className={mark(line)}>
              {line}
            </p>
          ))}
          {parts.cta ? <span className={`awb-cta ${mark(parts.cta)}`}>{parts.cta}</span> : null}
        </div>
        {parts.offer ? <span className={`awb-offer ${mark(parts.offer)}`}>{parts.offer}</span> : null}
      </div>
      {previous ? (
        <p className="awb-caption">
          Draft {index + 1}. Changed after the review: {removed.map((line) => `“${line}”`).join(", ") || "nothing"} →{" "}
          {changed.map((line) => `“${line}”`).join(", ") || "nothing"}
        </p>
      ) : (
        <p className="awb-caption">Draft 1, shown as it would look on the homepage.</p>
      )}
    </div>
  );
};

const claims: Visual = (ctx) => {
  const result = last(results<ClaimsResult>(ctx, "check_claims"));
  const reviewer = last(messages(ctx.stageEvents, "brand_reviewer"));
  const rules = ctx.scenario.tools.find((tool) => tool.id === "check_claims")?.description;
  if (!result && !reviewer) return <Pending label="Checking every claim…" />;
  return (
    <div className="awb-claims">
      <div className="awb-claims-col">
        <p className="awb-kicker">Rules in code</p>
        {result ? (
          <h4 className={result.passed ? "is-ok" : "is-bad"}>
            {result.passed ? <CircleCheck size={18} /> : <CircleX size={18} />} {result.passed ? "All rules passed" : `${result.issues.length} rule${result.issues.length > 1 ? "s" : ""} broken`}
          </h4>
        ) : (
          <Pending label="Running the rules…" />
        )}
        {result?.issues.length ? (
          <ul className="awb-issues">
            {result.issues.map((issue) => (
              <li key={`${issue.rule}-${issue.phrase}`}>
                “{issue.phrase}”: {issue.rule}. <small>{issue.fix}</small>
              </li>
            ))}
          </ul>
        ) : null}
        {rules ? <p className="awb-caption">{rules}</p> : null}
      </div>
      <div className="awb-claims-col">
        <p className="awb-kicker">Judgment by the agent</p>
        {reviewer?.text ? <Bubble who="Brand reviewer" text={reviewer.text} /> : <Pending label="Judging the tone…" />}
      </div>
    </div>
  );
};

const VISUALS: Record<string, Visual> = {
  alert,
  receipt,
  risk,
  request,
  approval,
  note,
  patient,
  search,
  checks,
  trials,
  shortlist,
  machine,
  manual,
  workorder,
  fieldcheck,
  ticket,
  code,
  tests,
  review,
  meeting,
  products,
  banner,
  claims,
};

export function StageVisual(ctx: VisualContext) {
  const render = VISUALS[ctx.stage.visual];
  return <>{render ? render(ctx) : <Markdown text={last(messages(ctx.stageEvents))?.text ?? ""} />}</>;
}
