import {
  ArrowRight,
  BellRing,
  BookOpen,
  Bot,
  Braces,
  ChevronLeft,
  ChevronRight,
  CircleCheck,
  CircleX,
  Database,
  Gauge,
  Lock,
  Pause,
  Play,
  UserRound,
  X,
  type LucideIcon,
} from "lucide-react";
import { Fragment, useLayoutEffect, useMemo, useRef, useState } from "react";
import { cursorAfter, mapStages, plainWords, stageView, type StageMap, type StageView } from "./business";
import { formatSeconds } from "./replay";
import type { ActorKind, ActorSpec, BusinessSpec, Run, RunEvent, ScenarioSpec, StageSpec } from "./types";
import { StageVisual } from "./visuals";
import "./business.css";

const ACTOR_ICON: Record<ActorKind, LucideIcon> = {
  trigger: BellRing,
  agent: Bot,
  system: Database,
  model: Gauge,
  code: Braces,
  person: UserRound,
};

const ACTOR_KIND_LABEL: Record<ActorKind, string> = {
  trigger: "Starts it",
  agent: "AI agent",
  system: "System",
  model: "Predictive model",
  code: "Plain code",
  person: "Person",
};

function actorColor(scenario: ScenarioSpec, actor: ActorSpec): string {
  if (actor.kind === "agent") return scenario.agents.find((a) => a.id === actor.ref)?.color ?? "#e8913c";
  if (actor.kind === "person") return "#f0b429";
  if (actor.kind === "model") return "#a3be8c";
  if (actor.kind === "code") return "#b8bcc8";
  if (actor.kind === "system") return "#7eaeb8";
  return "#9396a6";
}

function ActorBadge({ scenario, actor, size = 16 }: { scenario: ScenarioSpec; actor: ActorSpec; size?: number }) {
  const Icon = ACTOR_ICON[actor.kind];
  return (
    <span className="awb-actor-icon" style={{ ["--actor" as string]: actorColor(scenario, actor) }} aria-hidden="true">
      <Icon size={size} />
    </span>
  );
}

/** Short names of the technical pieces a business stage maps to. */
function techTags(scenario: ScenarioSpec, stage: StageSpec): string[] {
  const tags = stage.match.map((m) => {
    if (m.tool) return scenario.tools.find((t) => t.id === m.tool)?.label ?? m.tool;
    if (m.type === "approval_request") return "Approval";
    if (m.type === "code_step") return "Code step";
    if (m.type === "run_start") return "Task message";
    if (m.type === "handoff") return "Handoff";
    if (m.type === "speaker") return "Chair's pick";
    if (m.agent) {
      const label = scenario.agents.find((a) => a.id === m.agent)?.label ?? m.agent;
      return /agent$/i.test(label) ? label : `${label} agent`;
    }
    return "";
  });
  return [...new Set(tags.filter(Boolean))];
}

/* ---------- 1. The case: shown before the run ---------- */
export function CaseBrief({ scenario, onStart, onClose, canStart }: { scenario: ScenarioSpec; onStart: () => void; onClose: () => void; canStart: boolean }) {
  const business = scenario.business;
  if (!business) return null;
  return (
    <div className="awb-brief" role="dialog" aria-label="The case">
      <button type="button" className="aw-icon-button awb-brief-close" onClick={onClose} aria-label="Close the case">
        <X size={16} />
      </button>
      <p className="aw-eyebrow">
        <BookOpen size={13} /> The case · {scenario.industry}
      </p>
      <h2>{business.question}</h2>
      <p className="awb-situation">{business.situation}</p>
      <div className="awb-brief-grid">
        <section>
          <h3>Who is involved</h3>
          <ul className="awb-cast">
            {business.actors.map((actor) => (
              <li key={actor.id}>
                <ActorBadge scenario={scenario} actor={actor} />
                <span>
                  <span>
                    <strong>{actor.label}</strong> <em>{ACTOR_KIND_LABEL[actor.kind]}</em>
                  </span>
                  <small>{actor.plain}</small>
                </span>
              </li>
            ))}
          </ul>
        </section>
        <section>
          <h3>Why it matters</h3>
          <ul className="awb-list">
            {business.stakes.map((item) => (
              <li key={item}>{item}</li>
            ))}
          </ul>
          <h3>Who decides</h3>
          <p>{business.decides}</p>
          <h3>What good looks like</h3>
          <ul className="awb-list is-good">
            {business.good.map((item) => (
              <li key={item}>{item}</li>
            ))}
          </ul>
        </section>
        <div className="awb-compare">
          <section>
            <h3>Today, by hand</h3>
            <ol>
              {business.today.map((item) => (
                <li key={item}>{item}</li>
              ))}
            </ol>
          </section>
          <ArrowRight className="awb-compare-arrow" size={22} aria-hidden="true" />
          <section className="is-agent">
            <h3>With agents</h3>
            <ol>
              {business.with_agent.map((item) => (
                <li key={item}>{item}</li>
              ))}
            </ol>
          </section>
        </div>
      </div>
      <div className="awb-brief-actions">
        {canStart ? (
          <button type="button" className="aw-run" onClick={onStart}>
            <Play size={15} /> Watch it run
          </button>
        ) : null}
        <button type="button" className="awb-ghost" onClick={onClose}>
          Show the workflow
        </button>
      </div>
    </div>
  );
}

/* ---------- 2. End to end: swimlanes ---------- */
function Journey({
  scenario,
  business,
  map,
  view,
  onJump,
}: {
  scenario: ScenarioSpec;
  business: BusinessSpec;
  map: StageMap;
  view: StageView;
  onJump: ((cursor: number) => void) | null;
}) {
  const box = useRef<HTMLDivElement>(null);
  const cards = useRef<(HTMLButtonElement | null)[]>([]);
  const [links, setLinks] = useState<{ d: string; done: boolean }[]>([]);
  const statusKey = view.statuses.join(",");

  useLayoutEffect(() => {
    const statuses = statusKey.split(",");
    const order = statuses.map((_, index) => index).filter((index) => statuses[index] !== "skipped");
    const measure = () => {
      const frame = box.current?.getBoundingClientRect();
      if (!frame) return;
      const next: { d: string; done: boolean }[] = [];
      for (let k = 0; k + 1 < order.length; k += 1) {
        const a = cards.current[order[k]]?.getBoundingClientRect();
        const b = cards.current[order[k + 1]]?.getBoundingClientRect();
        if (!a || !b) continue;
        const x1 = a.right - frame.left;
        const y1 = a.top + a.height / 2 - frame.top;
        const x2 = b.left - frame.left;
        const y2 = b.top + b.height / 2 - frame.top;
        const mid = Math.round((x1 + x2) / 2);
        next.push({ d: `M${x1},${y1} H${mid} V${y2} H${x2 - 2}`, done: statuses[order[k + 1]] !== "upcoming" });
      }
      setLinks(next);
    };
    measure();
    const observer = new ResizeObserver(measure);
    if (box.current) observer.observe(box.current);
    return () => observer.disconnect();
  }, [statusKey]);

  return (
    <div className="awb-journey-scroll">
      <div className="awb-journey" ref={box} style={{ gridTemplateColumns: `minmax(150px, 200px) repeat(${business.stages.length}, minmax(128px, 1fr))` }}>
        <svg className="awb-links" aria-hidden="true">
          <defs>
            <marker id="awb-arrow" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse">
              <path d="M0,0 L10,5 L0,10 z" fill="currentColor" />
            </marker>
          </defs>
          {links.map((link, index) => (
            <path key={index} d={link.d} className={link.done ? "is-done" : ""} markerEnd="url(#awb-arrow)" />
          ))}
        </svg>
        <div className="awb-corner">Who</div>
        {business.stages.map((stage, col) => (
          <div key={stage.id} className="awb-col-head" style={{ gridColumn: col + 2 }}>
            Step {col + 1}
          </div>
        ))}
        {business.actors.map((actor, row) => (
          <Fragment key={actor.id}>
            <div className="awb-lane-head" style={{ gridRow: row + 2 }}>
              <ActorBadge scenario={scenario} actor={actor} />
              <span>
                <strong>{actor.label}</strong>
                <small>{ACTOR_KIND_LABEL[actor.kind]}</small>
              </span>
            </div>
            <div className="awb-lane-band" style={{ gridRow: row + 2, gridColumn: `2 / span ${business.stages.length}` }} />
          </Fragment>
        ))}
        {business.stages.map((stage, col) => {
          const row = business.actors.findIndex((a) => a.id === stage.actor);
          const status = view.statuses[col];
          const first = map.visits.find((v) => v.stage === col);
          const actor = business.actors[row];
          return (
            <button
              key={stage.id}
              type="button"
              ref={(node) => {
                cards.current[col] = node;
              }}
              className={`awb-stage is-${status}`}
              style={{ gridRow: row + 2, gridColumn: col + 2, ["--actor" as string]: actor ? actorColor(scenario, actor) : "#9396a6" }}
              onClick={() => first && onJump?.(cursorAfter(first))}
              disabled={!first || !onJump}
              title={status === "skipped" ? stage.skipped : stage.plain}
            >
              <span className="awb-stage-top">
                <span className="awb-stage-num">{col + 1}</span>
                {view.entries[col] > 1 ? <span className="awb-again">×{view.entries[col]}</span> : null}
                {status === "done" ? <CircleCheck size={14} className="awb-stage-done" aria-label="done" /> : null}
              </span>
              <strong>{stage.title}</strong>
              <small className="awb-stage-tech">{status === "skipped" ? "Skipped in this run" : techTags(scenario, stage).join(" · ")}</small>
            </button>
          );
        })}
      </div>
    </div>
  );
}

/* ---------- 3. This step, explained ---------- */
const DOING = new Set(["tool_call", "message", "speaker", "agent_start"]);

function HoodChips({ scenario, actor, events }: { scenario: ScenarioSpec; actor: ActorSpec; events: RunEvent[] }) {
  // Model calls are counted only for agents doing this step's work, not for the next agent warming up.
  const own = new Set(events.filter((e) => e.agent && DOING.has(e.type)).map((e) => e.agent as string));
  if (actor.kind === "agent") own.add(actor.ref);
  const agents = [...own].map((id) => scenario.agents.find((a) => a.id === id)).filter((a) => a !== undefined);
  const tools = [...new Set(events.filter((e) => e.type === "tool_call").map((e) => e.tool as string))]
    .map((id) => scenario.tools.find((t) => t.id === id))
    .filter((t) => t !== undefined);
  const modelCalls = events.filter((e) => e.type === "model_call" && own.has(e.agent ?? "")).length;
  const code = events.some((e) => e.type === "code_step");
  return (
    <ul className="awb-hood-chips">
      {agents.map((agent) => (
        <li key={agent.id} style={{ ["--chip" as string]: agent.color }} title="Agent: model + instructions + tools">
          <Bot size={12} /> {agent.label}
        </li>
      ))}
      {tools.map((tool) => (
        <li key={tool.id} title={tool.description}>
          {tool.approval ? <Lock size={12} /> : <Database size={12} />} {tool.label} <code>{tool.id}</code>
        </li>
      ))}
      {code ? (
        <li title="Fixed rules, no model">
          <Braces size={12} /> Code step
        </li>
      ) : null}
      <li title="Each call sends the conversation so far to the language model">
        <Gauge size={12} /> {modelCalls ? `${modelCalls} model call${modelCalls === 1 ? "" : "s"}` : "No language model in this step"}
      </li>
    </ul>
  );
}

function Outcome({ business, run, view }: { business: BusinessSpec; run: Run; view: StageView }) {
  const answers = run.events.filter((e) => e.type === "approval_response");
  const skipped = business.stages.filter((_, index) => view.statuses[index] === "skipped");
  const stats = run.stats;
  return (
    <div className="awb-outcome">
      <div>
        <p className="aw-eyebrow">Outcome</p>
        <h3>{run.result?.headline ?? run.status}</h3>
        {run.result?.fields?.length ? (
          <ul className="awb-chips is-plain">
            {run.result.fields.map((field) => (
              <li key={field.label}>
                {field.label}: <b>{field.value}</b>
              </li>
            ))}
          </ul>
        ) : null}
        {skipped.map((stage) => (
          <p key={stage.id} className="awb-caption">
            {stage.skipped}
          </p>
        ))}
      </div>
      <div>
        <p className="aw-eyebrow">People</p>
        {answers.length ? (
          answers.map((answer) => (
            <p key={answer.seq} className={answer.approved ? "awb-person-line is-ok" : "awb-person-line is-bad"}>
              {answer.approved ? <CircleCheck size={15} /> : <CircleX size={15} />} {answer.approved ? "Approved" : "Rejected"} by a person
            </p>
          ))
        ) : (
          <p className="awb-caption">Nobody needed to approve anything.</p>
        )}
      </div>
      <div>
        <p className="aw-eyebrow">AI work</p>
        <p className="awb-caption">
          {formatSeconds(run.seconds ?? 0)} · {stats?.model_calls ?? 0} model calls · {stats?.tool_calls ?? 0} tool calls
        </p>
      </div>
      {run.task.truth ? (
        <div className="awb-truth">
          <p className="aw-eyebrow">What really happened (hidden from the agents)</p>
          <p>{run.task.truth}</p>
        </div>
      ) : null}
    </div>
  );
}

export function BusinessSection({
  scenario,
  run,
  cursor,
  finished,
  live,
  playing,
  onJump,
  onTogglePlay,
  onDecide,
  deciding,
}: {
  scenario: ScenarioSpec;
  run: Run;
  cursor: number;
  finished: boolean;
  live: boolean;
  playing: boolean;
  onJump: (cursor: number) => void;
  onTogglePlay: () => void;
  onDecide?: (requestId: string, approved: boolean) => void;
  deciding?: string | null;
}) {
  const business = scenario.business;
  const events = run.events;
  const map = useMemo(() => (business ? mapStages(business, events) : null), [business, events]);
  if (!business || !map) return null;
  const view = stageView(business, map, cursor, finished);
  const visit = view.visit === null ? null : map.visits[view.visit];
  const stage = view.stage === null ? null : business.stages[view.stage];
  const actor = stage ? business.actors.find((a) => a.id === stage.actor) : undefined;
  const stageEvents = visit ? events.slice(visit.start, Math.min(visit.end + 1, cursor)) : [];
  const seen = events.slice(0, cursor);
  const words = plainWords(
    scenario.pattern,
    scenario.tools.some((t) => t.kind === "model"),
    scenario.nodes.some((n) => n.kind === "code") || scenario.tools.some((t) => t.kind === "check" || t.kind === "code"),
  );

  const next = () => {
    const k = view.visit;
    if (k !== null && cursor < cursorAfter(map.visits[k])) return onJump(cursorAfter(map.visits[k]));
    const target = map.visits[k === null ? 0 : k + 1];
    if (target) onJump(cursorAfter(target));
  };
  const previous = () => {
    const k = view.visit;
    if (k === null || k === 0) return onJump(0);
    onJump(cursorAfter(map.visits[k - 1]));
  };

  return (
    <section className="awb-section" aria-label="Business view">
      <header className="awb-head">
        <div>
          <p className="aw-eyebrow">Business view · end to end</p>
          <h2>{business.question}</h2>
        </div>
        <div className="awb-pager" role="group" aria-label="Business steps">
          <button type="button" className="aw-icon-button" onClick={previous} disabled={live || cursor === 0} aria-label="Previous business step">
            <ChevronLeft size={17} />
          </button>
          <button type="button" className="aw-play" onClick={onTogglePlay} disabled={live} aria-label={playing ? "Pause" : "Play"}>
            {playing ? <Pause size={18} /> : <Play size={18} />}
          </button>
          <button type="button" className="aw-icon-button" onClick={next} disabled={live || cursor >= events.length} aria-label="Next business step">
            <ChevronRight size={17} />
          </button>
          <span>{stage ? `Step ${business.stages.indexOf(stage) + 1} of ${business.stages.length}` : `${business.stages.length} steps`}</span>
        </div>
      </header>

      <Journey scenario={scenario} business={business} map={map} view={view} onJump={live ? null : onJump} />

      <div className="awb-explain">
        <div className="awb-explain-visual">
          {stage && run ? (
            <StageVisual scenario={scenario} run={run} stage={stage} stageEvents={stageEvents} seen={seen} onDecide={onDecide} deciding={deciding} />
          ) : (
            <div className="awb-start">
              <p>Press play, or click a step above, to follow the case one business step at a time.</p>
              <ol>
                {business.stages.map((item) => (
                  <li key={item.id}>{item.title}</li>
                ))}
              </ol>
            </div>
          )}
        </div>
        <aside className="awb-explain-side">
          {stage && actor ? (
            <>
              <p className="aw-eyebrow">
                Step {business.stages.indexOf(stage) + 1} of {business.stages.length}
                {view.stage !== null && view.entries[view.stage] > 1 ? ` · again (${view.entries[view.stage]}×)` : ""}
              </p>
              <h3>{stage.title}</h3>
              <span className="awb-actor-chip">
                <ActorBadge scenario={scenario} actor={actor} size={14} /> {actor.label} · {ACTOR_KIND_LABEL[actor.kind]}
              </span>
              <p className="awb-plain">{stage.plain}</p>
              <div className="awb-hood">
                <p className="aw-eyebrow">Under the hood</p>
                <p>{stage.tech}</p>
                <HoodChips scenario={scenario} actor={actor} events={stageEvents} />
              </div>
            </>
          ) : (
            <>
              <p className="aw-eyebrow">How to read this</p>
              <p className="awb-plain">The lanes are the people, agents and systems in the case. Each card is one business step; its small print names the technical piece behind it.</p>
            </>
          )}
        </aside>
      </div>

      {finished ? <Outcome business={business} run={run} view={view} /> : null}

      <div className="awb-words">
        <p className="aw-eyebrow">Plain words</p>
        <dl>
          {words.map((word) => (
            <div key={word.term}>
              <dt>{word.term}</dt>
              <dd>{word.plain}</dd>
            </div>
          ))}
        </dl>
      </div>
    </section>
  );
}
