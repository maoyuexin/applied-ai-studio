import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { ArrowLeft, Camera, ClipboardList, Gauge, Megaphone, Pause, Play, RotateCcw } from "lucide-react";
import { navigate } from "../router";
import ActivityLog from "../cityOps/ActivityLog";
import AlertDesk from "../cityOps/AlertDesk";
import CamerasView from "../cityOps/CamerasView";
import OperationsView from "../cityOps/OperationsView";
import {
  CITY,
  HORIZON,
  MAIN,
  STAGE_LABEL,
  STORMS,
  dayTimeAt,
  fmtDay,
  fmtTime,
  ft,
  gaugeState,
  stepDate,
  stormById,
  stormGauges,
  timeAt,
  type GaugeState,
} from "../cityOps/data";
import { deriveOps } from "../cityOps/incidents";
import { alertRequests, detailOf, draftsFor, requestStatus, useRecordedRun } from "../cityOps/runs";
import { RunGate } from "../cityOps/ui";
import "../cityOps/cityOps.css";

type View = "ops" | "cameras" | "alerts" | "log";
const VIEWS: Array<{ id: View; label: string; icon: typeof Gauge }> = [
  { id: "ops", label: "Operations", icon: Gauge },
  { id: "cameras", label: "Cameras", icon: Camera },
  { id: "alerts", label: "Alert desk", icon: Megaphone },
  { id: "log", label: "Activity log", icon: ClipboardList },
];
const SPEEDS: Array<{ value: number; label: string }> = [
  { value: 1, label: "1× · 15 min/s" },
  { value: 2, label: "2× · 30 min/s" },
  { value: 4, label: "4× · 1 h/s" },
  { value: 8, label: "8× · 2 h/s" },
];

function param(name: string): string | null {
  return new URLSearchParams(window.location.search).get(name);
}

export default function CityOperationsPage() {
  const [stormId, setStormId] = useState(() => stormById(param("storm")).id);
  const storm = stormById(stormId);
  const [view, setView] = useState<View>(() => (VIEWS.some((v) => v.id === param("view")) ? (param("view") as View) : "ops"));
  const [step, setStep] = useState(0);
  const [playing, setPlaying] = useState(false);
  const [speed, setSpeed] = useState(1);
  const [line, setLine] = useState(CITY.defaultLine);
  const [showAll, setShowAll] = useState(false);
  const [moment, setMoment] = useState<number | null>(null);
  const cameras = useRecordedRun(CITY.runs.cameras);
  const alerts = useRecordedRun(CITY.runs.alerts);
  const last = storm.steps - 1;
  const position = useRef(0);

  useEffect(() => {
    const url = new URL(window.location.href);
    url.searchParams.set("storm", storm.id);
    url.searchParams.set("view", view);
    window.history.replaceState(window.history.state, "", url);
  }, [storm.id, view]);

  // The replay clock: `speed` steps of 15 minutes per real second.
  useEffect(() => {
    if (!playing) return;
    let frame = 0;
    let previous = performance.now();
    const tick = (now: number) => {
      position.current = Math.min(last, position.current + ((now - previous) / 1000) * speed);
      previous = now;
      const next = Math.floor(position.current);
      setStep((current) => (current === next ? current : next));
      if (position.current >= last) { setPlaying(false); return; }
      frame = requestAnimationFrame(tick);
    };
    frame = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(frame);
  }, [playing, speed, last]);

  const seek = useCallback((target: number) => {
    const next = Math.max(0, Math.min(last, Math.round(target)));
    position.current = next;
    setStep(next);
  }, [last]);

  const togglePlay = useCallback(() => {
    if (!playing && step >= last) seek(0);
    else position.current = step;
    setPlaying(!playing);
  }, [playing, step, last, seek]);

  useEffect(() => {
    const onKey = (event: KeyboardEvent) => {
      const target = event.target as HTMLElement | null;
      if (event.code !== "Space" || !target || target.closest("input, textarea, select, button, summary, [contenteditable=true]")) return;
      event.preventDefault();
      togglePlay();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [togglePlay]);

  const pickStorm = (id: string) => {
    if (id === storm.id) return;
    setPlaying(false);
    setStormId(id);
    position.current = 0;
    setStep(0);
    setMoment(null);
  };

  const jump = (stormTo: string, target: number) => {
    if (stormTo !== storm.id) { setStormId(stormTo); setMoment(null); }
    setPlaying(false);
    seek(target);
  };

  const ops = useMemo(() => deriveOps(storm, line, step), [storm, line, step]);
  const states = useMemo(() => Object.fromEntries(stormGauges(storm).map((g) => [g.key, gaugeState(storm, g.key, step)])) as Record<string, GaugeState>, [storm, step]);
  const alertsDetail = detailOf(alerts);
  const cameraDetail = detailOf(cameras);
  const requests = useMemo(() => alertRequests(alertsDetail), [alertsDetail]);
  const statusOf = useCallback((index: number) => {
    const request = requests.find((r) => r.index === index);
    if (!request || !alertsDetail) return null;
    return requestStatus(draftsFor(alertsDetail, index), request.storm.id !== storm.id || step >= request.step);
  }, [requests, alertsDetail, storm.id, step]);
  const awaiting = requests.filter((r) => r.storm.id === storm.id && step >= r.step && statusOf(r.index) === "awaiting").length;

  const gauges = stormGauges(storm);
  const reporting = gauges.filter((g) => !states[g.key].offline).length;
  const main = states[MAIN];
  const forecast = storm.forecast.model[step];
  const openIncidents = (ops.watch.active ? 1 : 0) + (ops.levelStage !== "normal" ? 1 : 0) + ops.offline.length + awaiting;
  const now = stepDate(storm, step);
  const jumps = [
    { label: `Start · ${dayTimeAt(storm, 0)}`, step: 0 },
    ...storm.moments.map((m) => ({ label: `Alert request · ${m.name}`, step: m.step })),
    { label: `Main St reaches action stage · ${timeAt(storm, storm.crossingStep)}`, step: storm.crossingStep },
  ].sort((a, b) => a.step - b.step);

  const openAlert = (index: number) => { setMoment(index); setView("alerts"); window.scrollTo({ top: 0, behavior: "smooth" }); };

  return (
    <div className="page co-page">
      <button className="page-back-button" type="button" onClick={() => navigate("/showcase")}><ArrowLeft size={15} aria-hidden="true" /> Back to Industry Workflows</button>
      <header className="co-head">
        <div>
          <span className="eyebrow">Public sector · flood operations</span>
          <h1>City Operations · Houston</h1>
          <p>Brays Bayou flood desk: gauges, 2-hour forecasts, cameras and public alerts for a recorded storm.</p>
        </div>
        <div className="co-storms" role="radiogroup" aria-label="Storm">
          {STORMS.map((s) => (
            <button key={s.id} type="button" role="radio" aria-checked={s.id === storm.id} className={s.id === storm.id ? "is-on" : ""} onClick={() => pickStorm(s.id)}>
              <strong>{s.name.replace("Hurricane ", "")} {s.year}</strong>
              <small>{fmtDay(stepDate(s, 0))} · {s.steps / 4} h · peak {s.peakFt.toFixed(1)} ft</small>
            </button>
          ))}
        </div>
      </header>

      <div className="co-transport">
        <span className="co-replay" title={CITY.about}><span className="co-replay-dot" aria-hidden="true" />Replay · recorded data · no live models</span>
        <div className="co-clock" aria-live="off">
          <span>{fmtDay(now)}, {storm.year}</span>
          <strong>{fmtTime(now)}</strong>
          <small>CDT</small>
        </div>
        <div className="co-buttons">
          <button type="button" className="co-icon-btn" onClick={() => { setPlaying(false); seek(0); }} aria-label="Restart"><RotateCcw size={15} aria-hidden="true" /></button>
          <button type="button" className="co-play" onClick={togglePlay} aria-label={playing ? "Pause" : "Play"}>{playing ? <Pause size={17} aria-hidden="true" /> : <Play size={17} aria-hidden="true" />}</button>
          <select aria-label="Replay speed" value={speed} onChange={(e) => setSpeed(Number(e.target.value))}>
            {SPEEDS.map((s) => <option key={s.value} value={s.value}>{s.label}</option>)}
          </select>
        </div>
        <div className="co-scrub">
          <input type="range" min={0} max={last} step={1} value={step} aria-label="Replay time" aria-valuetext={dayTimeAt(storm, step)}
            onChange={(e) => { setPlaying(false); seek(Number(e.target.value)); }} />
          <div className="co-ticks" aria-hidden="true">
            {storm.moments.map((m) => <i key={m.moment} className="is-alert" style={{ left: `${(m.step / last) * 100}%` }} title={`Alert request · ${m.name}`} />)}
            <i className="is-cross" style={{ left: `${(storm.crossingStep / last) * 100}%` }} title="Main St reaches action stage" />
          </div>
        </div>
        <select className="co-jump" aria-label="Jump to" value="" onChange={(e) => { if (e.target.value !== "") jump(storm.id, Number(e.target.value)); }}>
          <option value="">Jump to…</option>
          {jumps.map((j) => <option key={`${j.label}-${j.step}`} value={j.step}>{j.label}</option>)}
        </select>
      </div>

      <section className="co-kpis" aria-label="Status now">
        <div>
          <span>Gauges reporting</span>
          <strong>{reporting} of {gauges.length}</strong>
          <small>{ops.offline.length ? `${ops.offline.map((k) => gauges.find((g) => g.key === k)?.short).join(", ")} offline` : "all online"}</small>
        </div>
        <div className={`is-${ops.levelStage}`}>
          <span>Main St level</span>
          <strong>{ft(main.last?.value, 2)}</strong>
          <small><span className={`co-stage is-${ops.levelStage}`}>{STAGE_LABEL[ops.levelStage]}</span></small>
        </div>
        <div className={forecast !== undefined && forecast >= line ? "is-watch" : ""}>
          <span>2-hour forecast · Main St</span>
          <strong>{ft(forecast)}</strong>
          <small>for {timeAt(storm, step + HORIZON)} · alert line {line} ft</small>
        </div>
        <div className={openIncidents ? "is-watch" : ""}>
          <span>Open incidents</span>
          <strong>{openIncidents}</strong>
          <small>{[ops.watch.active && "watch", ops.levelStage !== "normal" && "stage", ops.offline.length && `${ops.offline.length} gauge${ops.offline.length > 1 ? "s" : ""}`, awaiting && `${awaiting} alert${awaiting > 1 ? "s" : ""}`].filter(Boolean).join(" · ") || "none"}</small>
        </div>
        <button type="button" className={awaiting ? "is-alert" : ""} onClick={() => setView("alerts")}>
          <span>Alerts awaiting approval</span>
          <strong>{alertsDetail ? awaiting : "—"}</strong>
          <small>{alertsDetail ? (awaiting ? "open the Alert desk" : "none waiting") : alerts.load.state === "missing" ? "run not imported" : alerts.load.state === "error" ? "service unavailable" : "loading"}</small>
        </button>
      </section>

      <nav className="co-tabs" role="tablist" aria-label="Views">
        {VIEWS.map(({ id, label, icon: Icon }) => (
          <button key={id} type="button" role="tab" aria-selected={view === id} className={view === id ? "is-on" : ""} onClick={() => setView(id)}>
            <Icon size={15} aria-hidden="true" /> {label}
            {id === "alerts" && awaiting > 0 && <b className="co-tab-count">{awaiting}</b>}
          </button>
        ))}
      </nav>

      <div className="co-view">
        {view === "ops" && (
          <OperationsView storm={storm} step={step} line={line} setLine={setLine} ops={ops} states={states}
            alertStatus={statusOf} onOpenAlert={openAlert} />
        )}
        {view === "cameras" && (
          <RunGate run={cameras} what="camera desk">
            {cameraDetail && <CamerasView run={cameras} detail={cameraDetail} />}
          </RunGate>
        )}
        {view === "alerts" && (
          <RunGate run={alerts} what="alert drafts">
            {alertsDetail && (
              <AlertDesk run={alerts} detail={alertsDetail} storm={storm} step={step} showAll={showAll} setShowAll={setShowAll}
                selected={moment} setSelected={setMoment} onJump={jump} />
            )}
          </RunGate>
        )}
        {view === "log" && <ActivityLog storm={storm} incidents={ops.incidents} cameras={cameraDetail} alerts={alertsDetail} />}
      </div>

      <footer className="co-about">{CITY.about}</footer>
    </div>
  );
}
