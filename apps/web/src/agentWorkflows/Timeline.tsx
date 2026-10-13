import { ArrowRight, Check, CircleAlert, Code2, Flag, Gavel, Lock, Play, ShieldCheck, User, X } from "lucide-react";
import { useEffect, useMemo, useRef } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { stepColor, TIMELINE_TYPES } from "./replay";
import type { RunEvent, ScenarioSpec, Step } from "./types";

function StepTag({ step }: { step?: Step | null }) {
  if (!step) return null;
  return (
    <span className="aw-step-tag" style={{ ["--step" as string]: stepColor(step) }}>
      {step}
    </span>
  );
}

function pretty(value: unknown): string {
  if (typeof value === "string") return value;
  return JSON.stringify(value, null, 2);
}

function shortArgs(value: unknown): string {
  if (!value || typeof value !== "object") return typeof value === "string" ? value : "";
  const entries = Object.entries(value as Record<string, unknown>).filter(([key]) => key !== "code");
  return entries
    .map(([key, v]) => `${key}: ${typeof v === "string" ? v : JSON.stringify(v)}`)
    .join(" · ")
    .slice(0, 160);
}

export default function Timeline({
  scenario,
  events,
  cursor,
  live,
  onApprove,
  approving,
}: {
  scenario: ScenarioSpec;
  events: RunEvent[];
  cursor: number;
  live: boolean;
  onApprove?: (requestId: string, approved: boolean) => void;
  approving?: string | null;
}) {
  const agents = useMemo(() => Object.fromEntries(scenario.agents.map((agent) => [agent.id, agent])), [scenario]);
  const tools = useMemo(() => Object.fromEntries(scenario.tools.map((tool) => [tool.id, tool])), [scenario]);
  const human = scenario.nodes.find((node) => node.kind === "human");
  const shown = events.slice(0, cursor);
  const results = new Map<string, RunEvent>();
  const responses = new Map<string, RunEvent>();
  for (const event of shown) {
    if (event.type === "tool_result" && event.call_id) results.set(event.call_id, event);
    if (event.type === "approval_response" && event.request_id) responses.set(event.request_id, event);
  }
  const visible = shown.filter((event) => TIMELINE_TYPES.has(event.type));
  const listRef = useRef<HTMLOListElement>(null);
  const stick = useRef(true);

  useEffect(() => {
    const list = listRef.current;
    if (list && stick.current) list.scrollTop = list.scrollHeight;
  }, [visible.length]);

  const agentName = (id?: string) => (id && agents[id] ? agents[id].label : id ?? "");
  const agentColor = (id?: string) => (id && agents[id] ? agents[id].color : "#9396a6");

  return (
    <ol
      className="aw-timeline"
      ref={listRef}
      onScroll={(event) => {
        const el = event.currentTarget;
        stick.current = el.scrollHeight - el.scrollTop - el.clientHeight < 80;
      }}
      aria-live="polite"
    >
      {visible.length === 0 ? <li className="aw-empty">Press play to watch the run.</li> : null}
      {visible.map((event) => {
        switch (event.type) {
          case "run_start":
            return (
              <li key={event.seq} className="aw-card aw-card-task">
                <header>
                  <Play size={13} /> Task
                </header>
                <p>{event.prompt}</p>
              </li>
            );
          case "agent_start":
            return (
              <li key={event.seq} className="aw-divider" style={{ ["--agent" as string]: agentColor(event.agent) }}>
                {agents[event.agent ?? ""]?.kind === "chair" ? <Gavel size={12} /> : null}
                <span>{agentName(event.agent)}</span> is working
              </li>
            );
          case "speaker":
            return (
              <li key={event.seq} className="aw-divider is-route">
                <Gavel size={12} /> Chair gives the floor to <strong>{agentName(event.agent)}</strong>
              </li>
            );
          case "handoff":
            return (
              <li key={event.seq} className="aw-divider is-route">
                <strong style={{ color: agentColor(event.source) }}>{agentName(event.source)}</strong>
                <ArrowRight size={13} /> hands the task to
                <strong style={{ color: agentColor(event.target) }}>{agentName(event.target)}</strong>
              </li>
            );
          case "message":
            return (
              <li key={event.seq} className="aw-card aw-card-message" style={{ ["--agent" as string]: agentColor(event.agent) }}>
                <header>
                  <span className="aw-dot" />
                  {agentName(event.agent)}
                  <StepTag step={event.step} />
                  <time>{event.t.toFixed(1)} s</time>
                </header>
                <div className="aw-markdown">
                  <ReactMarkdown remarkPlugins={[remarkGfm]}>{event.text ?? ""}</ReactMarkdown>
                </div>
              </li>
            );
          case "tool_call": {
            const result = event.call_id ? results.get(event.call_id) : undefined;
            const tool = tools[event.tool ?? ""];
            const code = (event.args as { code?: string } | undefined)?.code;
            return (
              <li key={event.seq} className="aw-card aw-card-tool" style={{ ["--step" as string]: stepColor(event.step) }}>
                <header>
                  {event.tool === "run_python" ? <Code2 size={13} /> : <ShieldCheck size={13} />}
                  <span>
                    {agentName(event.agent)} calls <strong>{tool?.label ?? event.tool}</strong>
                  </span>
                  {event.approval ? <Lock size={12} /> : null}
                  <StepTag step={event.step} />
                  <time>{event.t.toFixed(1)} s</time>
                </header>
                {code ? <pre className="aw-code">{code}</pre> : <p className="aw-args">{shortArgs(event.args) || "(no inputs)"}</p>}
                {result ? (
                  <details className={result.ok === false ? "is-error" : undefined}>
                    <summary>{result.ok === false ? "Tool error" : event.approval ? "Result after the decision" : "Result"}</summary>
                    <pre>{pretty(result.result)}</pre>
                  </details>
                ) : event.approval ? (
                  <p className="aw-waiting">Waiting for a person…</p>
                ) : (
                  <p className="aw-waiting">Running…</p>
                )}
              </li>
            );
          }
          case "approval_request": {
            const response = event.request_id ? responses.get(event.request_id) : undefined;
            const tool = tools[event.tool ?? ""];
            return (
              <li key={event.seq} className={`aw-card aw-card-approval${response ? (response.approved ? " is-approved" : " is-rejected") : " is-pending"}`}>
                <header>
                  <User size={13} /> {human?.label ?? "A person"} must decide
                  <StepTag step="ask" />
                  <time>{event.t.toFixed(1)} s</time>
                </header>
                <p>
                  <strong>{agentName(event.agent)}</strong> asks to run <strong>{tool?.label ?? event.tool}</strong>
                </p>
                <pre>{pretty(event.args)}</pre>
                {response ? (
                  <p className="aw-decision">
                    {response.approved ? <Check size={14} /> : <X size={14} />} {response.approved ? "Approved" : "Rejected"} by{" "}
                    {human?.label?.toLowerCase() ?? "a person"}
                  </p>
                ) : live && onApprove && event.request_id ? (
                  <div className="aw-approval-actions">
                    <button type="button" className="aw-approve" disabled={approving === event.request_id} onClick={() => onApprove(event.request_id!, true)}>
                      <Check size={14} /> Approve
                    </button>
                    <button type="button" className="aw-reject" disabled={approving === event.request_id} onClick={() => onApprove(event.request_id!, false)}>
                      <X size={14} /> Reject
                    </button>
                  </div>
                ) : (
                  <p className="aw-waiting">Waiting for the decision…</p>
                )}
              </li>
            );
          }
          case "code_step":
            return (
              <li key={event.seq} className={`aw-card aw-card-code ${event.passed ? "is-pass" : "is-fail"}`}>
                <header>
                  <Code2 size={13} /> {event.title ?? "Code step"} <span className="aw-pill">plain code, not an agent</span>
                  <StepTag step="check" />
                  <time>{event.t.toFixed(1)} s</time>
                </header>
                <ul>
                  {(event.checks ?? []).map((check) => (
                    <li key={check.check} className={check.ok ? "ok" : "bad"}>
                      {check.ok ? <Check size={13} /> : <X size={13} />} {check.check}
                      {check.detail ? <em> ({check.detail})</em> : null}
                    </li>
                  ))}
                </ul>
              </li>
            );
          case "run_end":
            return (
              <li key={event.seq} className={`aw-card aw-card-end${event.status === "completed" ? "" : " is-error"}`}>
                <header>
                  {event.status === "completed" ? <Flag size={13} /> : <CircleAlert size={13} />} Run {event.status}
                  <time>{event.t.toFixed(1)} s</time>
                </header>
                {event.error ? <p>{event.error}</p> : null}
              </li>
            );
          default:
            return null;
        }
      })}
    </ol>
  );
}
