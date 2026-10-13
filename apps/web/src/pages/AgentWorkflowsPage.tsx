import { BookOpen, CircleStop, Pause, Play, Radio, RotateCcw, SkipBack, SkipForward, Workflow } from "lucide-react";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { BusinessSection, CaseBrief } from "../agentWorkflows/BusinessView";
import { AboutPanel, Inspector, ResultPanel } from "../agentWorkflows/Panels";
import Timeline from "../agentWorkflows/Timeline";
import WorkflowCanvas, { type Selection } from "../agentWorkflows/WorkflowCanvas";
import {
  fetchHealth,
  fetchLiveAvailability,
  recordedChoices,
  savedLiveChoices,
  SCENARIOS,
  sendApproval,
  startLiveRun,
  stopLiveRun,
  streamLiveRun,
} from "../agentWorkflows/data";
import { deriveState, formatSeconds, schedule, STEPS, stepColor, TIMELINE_TYPES } from "../agentWorkflows/replay";
import type { Health, LiveAvailability, Run, RunChoice, RunEvent } from "../agentWorkflows/types";
import "../agentWorkflows/agentWorkflows.css";

const STEP_TYPES = new Set([...TIMELINE_TYPES, "approval_response"]);
const SPEEDS = [0.5, 1, 2, 4];
const PATTERN_ORDER = ["single", "sequential", "handoff", "group_chat", "concurrent"];

function initialScenario(): string {
  const wanted = new URLSearchParams(window.location.search).get("scenario");
  return SCENARIOS.some((s) => s.id === wanted) ? (wanted as string) : SCENARIOS[0]?.id ?? "";
}

export default function AgentWorkflowsPage() {
  const [scenarioId, setScenarioId] = useState(initialScenario);
  const scenario = SCENARIOS.find((s) => s.id === scenarioId) ?? SCENARIOS[0];
  const [mode, setMode] = useState<"replay" | "live">("replay");
  const [choices, setChoices] = useState<RunChoice[]>([]);
  const [choiceKey, setChoiceKey] = useState<string>("");
  const [run, setRun] = useState<Run | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [cursor, setCursor] = useState(0);
  const [playing, setPlaying] = useState(false);
  const [speed, setSpeed] = useState(1);
  const clock = useRef(0);
  const loadedKey = useRef<string | null>(null);
  const [tab, setTab] = useState<"timeline" | "result" | "about">("timeline");
  const [selection, setSelection] = useState<Selection>(null);
  const [health, setHealth] = useState<Health | null>(null);
  const [availability, setAvailability] = useState<Record<string, LiveAvailability>>({});
  const [liveTask, setLiveTask] = useState(scenario.tasks[0]?.id ?? "");
  const [liveRunId, setLiveRunId] = useState<string | null>(null);
  const [liveState, setLiveState] = useState<"idle" | "running" | "done">("idle");
  const [liveError, setLiveError] = useState<string | null>(null);
  const [approving, setApproving] = useState<string | null>(null);
  const [briefOpen, setBriefOpen] = useState(true);
  const closeStream = useRef<(() => void) | null>(null);

  const events = useMemo(() => run?.events ?? [], [run]);
  const times = useMemo(() => schedule(events), [events]);
  const view = useMemo(() => deriveState(scenario, events, cursor), [scenario, events, cursor]);
  const finished = cursor >= events.length && events.length > 0 && (mode === "replay" || liveState === "done");

  const refreshLive = useCallback(async () => {
    const [h, a] = await Promise.all([fetchHealth(), fetchLiveAvailability()]);
    setHealth(h);
    setAvailability(a);
  }, []);

  useEffect(() => {
    void refreshLive();
  }, [refreshLive]);

  useEffect(() => {
    const url = new URL(window.location.href);
    url.searchParams.set("scenario", scenario.id);
    window.history.replaceState(window.history.state, "", url);
  }, [scenario.id]);

  const loadChoices = useCallback(async (id: string, prefer?: string) => {
    const recorded = recordedChoices(id);
    setChoices(recorded);
    const first = prefer ?? recorded[0]?.key ?? "";
    setChoiceKey(first);
    const live = await savedLiveChoices(id);
    setChoices([...recorded, ...live]);
    return [...recorded, ...live];
  }, []);

  useEffect(() => {
    setPlaying(false);
    setSelection(null);
    setLiveTask(scenario.tasks[0]?.id ?? "");
    setTab("timeline");
    setBriefOpen(true);
    void loadChoices(scenario.id);
  }, [scenario.id, scenario.tasks, loadChoices]);

  useEffect(() => {
    if (mode !== "replay") return;
    const choice = choices.find((c) => c.key === choiceKey);
    // The choice list grows when saved live runs arrive; only a different selection reloads.
    if (!choice || loadedKey.current === choiceKey) return;
    let cancelled = false;
    setLoadError(null);
    choice
      .load()
      .then((loaded) => {
        if (cancelled) return;
        loadedKey.current = choiceKey;
        setRun(loaded);
        setCursor(0);
        clock.current = 0;
        setPlaying(false);
      })
      .catch((error: Error) => !cancelled && setLoadError(error.message));
    return () => {
      cancelled = true;
    };
  }, [choiceKey, choices, mode]);

  useEffect(() => {
    if (!playing || mode !== "replay") return;
    let frame = 0;
    let last = performance.now();
    const tick = (now: number) => {
      clock.current += ((now - last) / 1000) * speed;
      last = now;
      let next = 0;
      while (next < times.length && times[next] <= clock.current) next += 1;
      setCursor(next);
      if (next >= times.length) {
        setPlaying(false);
        return;
      }
      frame = requestAnimationFrame(tick);
    };
    frame = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(frame);
  }, [playing, speed, times, mode]);

  useEffect(() => {
    if (mode === "live") setCursor(events.length);
  }, [events.length, mode]);

  useEffect(() => () => closeStream.current?.(), []);

  const jumpTo = useCallback(
    (index: number) => {
      const bounded = Math.max(0, Math.min(index, events.length));
      setCursor(bounded);
      clock.current = bounded > 0 ? times[bounded - 1] : 0;
    },
    [events.length, times],
  );

  const stepForward = useCallback(() => {
    setPlaying(false);
    for (let i = cursor; i < events.length; i += 1) {
      if (STEP_TYPES.has(events[i].type)) return jumpTo(i + 1);
    }
    jumpTo(events.length);
  }, [cursor, events, jumpTo]);

  const stepBack = useCallback(() => {
    setPlaying(false);
    for (let i = cursor - 2; i >= 0; i -= 1) {
      if (STEP_TYPES.has(events[i].type)) return jumpTo(i + 1);
    }
    jumpTo(0);
  }, [cursor, events, jumpTo]);

  const togglePlay = useCallback(() => {
    if (mode !== "replay") return;
    setBriefOpen(false);
    if (cursor >= events.length) jumpTo(0);
    setPlaying((value) => !value);
  }, [cursor, events.length, jumpTo, mode]);

  useEffect(() => {
    const onKey = (event: KeyboardEvent) => {
      const target = event.target as HTMLElement | null;
      if (target && ["INPUT", "SELECT", "TEXTAREA", "BUTTON"].includes(target.tagName)) return;
      if (event.key === " ") {
        event.preventDefault();
        togglePlay();
      } else if (event.key === "ArrowRight") stepForward();
      else if (event.key === "ArrowLeft") stepBack();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [togglePlay, stepForward, stepBack]);

  const liveInfo = availability[scenario.id];
  const liveAvailable = Boolean(health?.live_ready && liveInfo?.available);
  const liveReason = !health
    ? "Live runs need the agent workflow service (npm run dev:agent-workflows)."
    : !health.live_ready
      ? "Live runs need a Foundry project and model in the service settings."
      : liveInfo?.reason || (scenario.has_live ? "" : "This scenario is replay-only.");

  async function runLive() {
    setLiveError(null);
    setPlaying(false);
    setBriefOpen(false);
    closeStream.current?.();
    try {
      const id = await startLiveRun(scenario.id, liveTask);
      const task = scenario.tasks.find((t) => t.id === liveTask) ?? scenario.tasks[0];
      setMode("live");
      setLiveRunId(id);
      setLiveState("running");
      setTab("timeline");
      setRun({ id, scenario: scenario.id, task, mode: "live", model: health?.model, status: "running", events: [] });
      setCursor(0);
      closeStream.current = streamLiveRun(
        id,
        (event: RunEvent) => setRun((current) => (current && current.id === id ? { ...current, events: [...current.events, event] } : current)),
        (done) => {
          setRun((current) => (current && current.id === id ? { ...current, ...done, events: current.events } : current));
          setLiveState("done");
          void loadChoices(scenario.id, choiceKey);
        },
        (message) => {
          setLiveError(message);
          setLiveState("done");
        },
      );
    } catch (error) {
      setLiveError((error as Error).message);
    }
  }

  async function decide(requestId: string, approved: boolean) {
    if (!liveRunId) return;
    setApproving(requestId);
    try {
      await sendApproval(liveRunId, requestId, approved);
    } catch (error) {
      setLiveError((error as Error).message);
    } finally {
      setApproving(null);
    }
  }

  function backToReplay() {
    closeStream.current?.();
    loadedKey.current = null;
    setMode("replay");
    setLiveState("idle");
    setLiveRunId(null);
    setLiveError(null);
  }

  function enterLive() {
    setPlaying(false);
    setMode("live");
    setRun(null);
    setCursor(0);
    setTab("timeline");
  }

  const sortedScenarios = [...SCENARIOS].sort((a, b) => PATTERN_ORDER.indexOf(a.pattern) - PATTERN_ORDER.indexOf(b.pattern));
  const tokens = run?.stats ? run.stats.input_tokens + run.stats.output_tokens : null;

  return (
    <div className="aw-page">
      <header className="aw-head">
        <div className="aw-title">
          <p className="aw-eyebrow">
            <Workflow size={13} /> Agent Workflows
          </p>
          <h1>Watch agents use models and tools, alone and in teams</h1>
        </div>
        <nav className="aw-scenarios" aria-label="Scenarios">
          {sortedScenarios.map((item) => (
            <button
              key={item.id}
              type="button"
              className={item.id === scenario.id ? "aw-scenario is-current" : "aw-scenario"}
              onClick={() => mode === "live" && liveState === "running" ? undefined : setScenarioId(item.id)}
              disabled={mode === "live" && liveState === "running" && item.id !== scenario.id}
              aria-pressed={item.id === scenario.id}
            >
              <span className={`aw-pattern aw-pattern-${item.pattern}`}>{item.pattern_label}</span>
              <strong>{item.title}</strong>
              <small>{item.industry}</small>
            </button>
          ))}
        </nav>
      </header>

      <div className="aw-toolbar">
        <div className="aw-mode" role="group" aria-label="Mode">
          <button type="button" className={mode === "replay" ? "is-on" : ""} onClick={backToReplay} disabled={mode === "replay"}>
            Replay
          </button>
          <button type="button" className={mode === "live" ? "is-on" : ""} onClick={enterLive} disabled={(!liveAvailable && mode !== "live") || mode === "live"} title={liveReason}>
            <Radio size={13} /> Live
          </button>
        </div>

        {mode === "replay" ? (
          <>
            <label className="aw-select">
              <span>Run</span>
              <select value={choiceKey} onChange={(event) => setChoiceKey(event.target.value)}>
                {choices.map((choice) => (
                  <option key={choice.key} value={choice.key}>
                    {choice.source === "live" ? "● " : ""}
                    {choice.label} — {choice.detail}
                  </option>
                ))}
              </select>
            </label>
            <div className="aw-transport" role="group" aria-label="Playback">
              <button type="button" className="aw-icon-button" onClick={() => { setPlaying(false); jumpTo(0); }} aria-label="Restart">
                <RotateCcw size={16} />
              </button>
              <button type="button" className="aw-icon-button" onClick={stepBack} aria-label="Previous step">
                <SkipBack size={16} />
              </button>
              <button type="button" className="aw-play" onClick={togglePlay} aria-label={playing ? "Pause" : "Play"}>
                {playing ? <Pause size={18} /> : <Play size={18} />}
              </button>
              <button type="button" className="aw-icon-button" onClick={stepForward} aria-label="Next step">
                <SkipForward size={16} />
              </button>
              <select value={speed} onChange={(event) => setSpeed(Number(event.target.value))} aria-label="Speed">
                {SPEEDS.map((value) => (
                  <option key={value} value={value}>
                    {value}×
                  </option>
                ))}
              </select>
            </div>
            <input
              className="aw-scrubber"
              type="range"
              min={0}
              max={events.length}
              value={cursor}
              onChange={(event) => { setPlaying(false); jumpTo(Number(event.target.value)); }}
              aria-label="Position in the run"
            />
          </>
        ) : (
          <>
            <label className="aw-select">
              <span>Task</span>
              <select value={liveTask} onChange={(event) => setLiveTask(event.target.value)} disabled={liveState === "running"}>
                {scenario.tasks.map((task) => (
                  <option key={task.id} value={task.id}>
                    {task.label}
                  </option>
                ))}
              </select>
            </label>
            {liveState === "running" ? (
              <button type="button" className="aw-stop" onClick={() => liveRunId && void stopLiveRun(liveRunId)}>
                <CircleStop size={15} /> Stop
              </button>
            ) : (
              <button type="button" className="aw-run" onClick={() => void runLive()} disabled={!liveAvailable}>
                <Play size={15} /> Run live
              </button>
            )}
            <span className="aw-live-status">
              {liveState === "running" ? (
                <>
                  <span className="aw-live-dot" /> Running on {health?.model ?? "the model"}…
                </>
              ) : liveReason ? (
                liveReason
              ) : (
                `Live on ${health?.model ?? "the configured model"} · ${health?.framework ?? ""}`
              )}
            </span>
          </>
        )}
      </div>
      {loadError || liveError ? <p className="aw-error">{loadError ?? liveError}</p> : null}

      <div className="aw-main">
        <section className="aw-stage" aria-label="Workflow">
          <div className="aw-stage-head">
            <span className={`aw-pattern aw-pattern-${scenario.pattern}`}>{scenario.pattern_label}</span>
            <strong>{scenario.title}</strong>
            <span>{scenario.tagline}</span>
            {scenario.business ? (
              <button type="button" className="awb-ghost aw-case-button" onClick={() => setBriefOpen((open) => !open)} aria-pressed={briefOpen}>
                <BookOpen size={14} /> The case
              </button>
            ) : null}
          </div>
          <div className="aw-canvas">
            <WorkflowCanvas scenario={scenario} view={view} selection={selection} onSelect={setSelection} />
            <Inspector scenario={scenario} selection={selection} model={run?.model ?? health?.model} onClose={() => setSelection(null)} />
          </div>
          <footer className="aw-stats">
            <ol className="aw-steps" aria-label="Five steps">
              {STEPS.map((step) => (
                <li
                  key={step.id}
                  className={`${view.stepCounts[step.id] ? "is-lit" : ""}${view.currentStep === step.id && !view.finished ? " is-current" : ""}`}
                  style={{ ["--step" as string]: stepColor(step.id) }}
                  title={step.hint}
                >
                  <span>{step.label}</span>
                  <b>{view.stepCounts[step.id]}</b>
                </li>
              ))}
            </ol>
            <dl className="aw-counters">
              <div>
                <dt>Model calls</dt>
                <dd>{view.modelCalls}</dd>
              </div>
              <div>
                <dt>Tool calls</dt>
                <dd>{view.toolCalls}</dd>
              </div>
              {scenario.pattern === "handoff" ? (
                <div>
                  <dt>Handoffs</dt>
                  <dd>{view.handoffs}</dd>
                </div>
              ) : null}
              <div>
                <dt>Approvals</dt>
                <dd>{view.approvals}</dd>
              </div>
              <div>
                <dt>Time</dt>
                <dd>{formatSeconds(view.elapsed)}</dd>
              </div>
              <div>
                <dt>Tokens</dt>
                <dd>{finished && tokens !== null ? tokens.toLocaleString() : "…"}</dd>
              </div>
            </dl>
          </footer>
        </section>

        <aside className="aw-side">
          <div className="aw-tabs" role="tablist">
            {(["timeline", "result", "about"] as const).map((name) => (
              <button key={name} type="button" role="tab" aria-selected={tab === name} className={tab === name ? "is-on" : ""} onClick={() => setTab(name)}>
                {name === "timeline" ? "What is happening" : name === "result" ? "Result" : "About"}
              </button>
            ))}
          </div>
          <div className="aw-tab-body">
            {tab === "timeline" && run ? (
              <Timeline scenario={scenario} events={events} cursor={cursor} live={mode === "live" && liveState === "running"} onApprove={decide} approving={approving} />
            ) : null}
            {tab === "timeline" && !run ? (
              <p className="aw-empty">{mode === "live" ? "Pick a task and press Run live. Approvals will appear here." : "Loading…"}</p>
            ) : null}
            {tab === "result" ? <ResultPanel scenario={scenario} run={run} finished={finished} /> : null}
            {tab === "about" ? <AboutPanel scenario={scenario} /> : null}
          </div>
        </aside>
        {briefOpen && scenario.business ? (
          <CaseBrief
            scenario={scenario}
            canStart={mode === "replay" && events.length > 0}
            onStart={() => {
              setBriefOpen(false);
              jumpTo(0);
              setPlaying(true);
            }}
            onClose={() => setBriefOpen(false)}
          />
        ) : null}
      </div>

      {run && scenario.business ? (
        <BusinessSection
          scenario={scenario}
          run={run}
          cursor={cursor}
          finished={finished}
          live={mode === "live"}
          playing={playing}
          onJump={(index) => {
            setPlaying(false);
            setBriefOpen(false);
            jumpTo(index);
          }}
          onTogglePlay={togglePlay}
          onDecide={mode === "live" && liveState === "running" ? (requestId, approved) => void decide(requestId, approved) : undefined}
          deciding={approving}
        />
      ) : null}
    </div>
  );
}
