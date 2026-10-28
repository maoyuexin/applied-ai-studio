import { useState } from "react";
import { ArrowDownRight, ArrowRight, ArrowUpRight, BellRing, Siren } from "lucide-react";
import {
  CITY,
  MAIN,
  STAGE_LABEL,
  dayTimeAt,
  duration,
  fmtDay,
  ft,
  gaugeTone,
  signedFt,
  stepDate,
  stormGauges,
  timeAt,
  type GaugeState,
  type StageKey,
  type Storm,
} from "./data";
import { Hydrograph, MiniMap, Sparkline } from "./Charts";
import type { Incident, OpsState } from "./incidents";
import { STATUS_TEXT, type RequestStatus } from "./runs";
import { Panel } from "./ui";

interface Props {
  storm: Storm;
  step: number;
  line: number;
  setLine: (line: number) => void;
  ops: OpsState;
  states: Record<string, GaugeState>;
  alertStatus: (moment: number) => RequestStatus | null;
  onOpenAlert: (moment: number) => void;
}

export default function OperationsView({ storm, step, line, setLine, ops, states, alertStatus, onOpenAlert }: Props) {
  const [compare, setCompare] = useState(false);
  const [picked, setPicked] = useState<string | null>(null);
  return (
    <div className="co-ops">
      <div className="co-ops-main">
        <Panel eyebrow="Brays Bayou at Main St · forecast point" title="Level and 2-hour forecast"
          aside={(
            <label className="co-check">
              <input type="checkbox" checked={compare} onChange={(e) => setCompare(e.target.checked)} />
              Compare: no upstream gauges
            </label>
          )}>
          <Hydrograph storm={storm} step={step} line={line} compare={compare} />
        </Panel>
        <div className="co-ops-pair">
          <Panel eyebrow="Gauge map" title="Brays Bayou watershed">
            <MiniMap storm={storm} states={states} stage={ops.levelStage} onPick={setPicked} picked={picked} />
          </Panel>
          <Panel eyebrow="USGS gauges · 15-minute readings" title="Gauge board">
            <GaugeBoard storm={storm} step={step} states={states} stage={ops.levelStage} picked={picked} onPick={setPicked} />
          </Panel>
        </div>
      </div>
      <div className="co-ops-side">
        <AlertPolicy storm={storm} step={step} line={line} setLine={setLine} ops={ops} />
        <IncidentFeed storm={storm} incidents={ops.incidents} alertStatus={alertStatus} onOpenAlert={onOpenAlert} />
      </div>
    </div>
  );
}

function stageBadge(stage: StageKey) {
  return <span className={`co-stage is-${stage}`}>{STAGE_LABEL[stage]}</span>;
}

function GaugeBoard({ storm, step, states, stage, picked, onPick }: {
  storm: Storm; step: number; states: Record<string, GaugeState>; stage: StageKey; picked: string | null; onPick: (key: string) => void;
}) {
  const sameDay = (s: number) => fmtDay(stepDate(storm, s)) === fmtDay(stepDate(storm, step));
  const when = (s: number) => (sameDay(s) ? timeAt(storm, s) : dayTimeAt(storm, s));
  return (
    <ul className="co-gauges">
      {stormGauges(storm).map((gauge) => {
        const state = states[gauge.key];
        const tone = gaugeTone(gauge.key, state, stage);
        const change = state.change1h;
        const Arrow = change === null ? ArrowRight : change > 0.05 ? ArrowUpRight : change < -0.05 ? ArrowDownRight : ArrowRight;
        const status = state.value !== null
          ? <span className="co-gauge-status is-online">Online</span>
          : state.offline
            ? <span className="co-gauge-status is-offline">{state.last ? `Offline · no reading since ${when(state.last.step)}` : "No reading yet"}</span>
            : <span className="co-gauge-status is-late">No reading since {when(state.last!.step)}</span>;
        return (
          <li key={gauge.key} className={`co-gauge is-${tone}${picked === gauge.key ? " is-picked" : ""}`}>
            <button type="button" onClick={() => onPick(gauge.key)} aria-pressed={picked === gauge.key}>
              <span className="co-gauge-name">
                <strong>{gauge.short}</strong>
                <small title={`USGS ${gauge.usgs}`}>{gauge.role} · USGS {gauge.usgs}</small>
              </span>
              <span className="co-gauge-level">
                <b className={state.value === null ? "is-stale" : ""}>{ft(state.last?.value, 2)}</b>
                <small className={change !== null && change >= 1 ? "is-fast" : ""}><Arrow size={12} aria-hidden="true" />{signedFt(change)} / 1 h</small>
              </span>
              <Sparkline series={state.series} step={step} />
              <span className="co-gauge-meta">
                {gauge.key === MAIN ? stageBadge(stage) : gauge.key === "whiteoak"
                  ? <span className="co-muted-chip" title="White Oak Bayou is a separate bayou; our data has no flood stages for it.">No flood stages in our data</span>
                  : <span className="co-muted-chip" title="Upstream gauges read in their own datum; their feet are not comparable to Main St.">Own datum · no stages</span>}
                {status}
              </span>
            </button>
          </li>
        );
      })}
    </ul>
  );
}

function AlertPolicy({ storm, step, line, setLine, ops }: { storm: Storm; step: number; line: number; setLine: (v: number) => void; ops: OpsState }) {
  const lines = CITY.alertLines;
  const index = Math.max(0, lines.indexOf(line));
  const { watch } = ops;
  return (
    <Panel eyebrow="Alert policy" title="Flood watch trigger" className="co-policy"
      aside={watch.active
        ? <span className="co-pill is-watch"><BellRing size={13} aria-hidden="true" /> Watch active</span>
        : <span className="co-pill">No watch</span>}>
      <div className="co-policy-body">
        <label htmlFor="co-line">Raise a flood watch when the 2-hour forecast at Main St reaches</label>
        <div className="co-line-control">
          <input id="co-line" type="range" min={0} max={lines.length - 1} step={1} value={index}
            onChange={(e) => setLine(lines[Number(e.target.value)])} aria-valuetext={`${line} ft`} />
          <output htmlFor="co-line">{line.toFixed(1)} ft</output>
        </div>
        <div className="co-line-scale" aria-hidden="true"><span>{lines[0]} ft · earlier, more false alarms</span><span>{lines[lines.length - 1]} ft · later</span></div>
        <dl className="co-facts">
          <div><dt>Status</dt><dd>{watch.active && watch.since !== null ? `Active since ${timeAt(storm, watch.since)}` : "Not active"}</dd></div>
          <div><dt>Watches so far</dt><dd>{watch.issued}</dd></div>
          <div>
            <dt>Warning before action stage</dt>
            <dd>{watch.crossedAt === null
              ? "Main St has not reached action stage"
              : watch.leadSteps === null ? `None: no watch when Main St reached ${CITY.stages.action} ft`
              : watch.leadSteps === 0 ? "None: watch raised as Main St reached it"
              : `${duration(watch.leadSteps)} (reached ${CITY.stages.action} ft at ${timeAt(storm, watch.crossedAt)})`}</dd>
          </div>
        </dl>
        {step < 1 && <p className="co-hint">Changing the line re-derives every watch from the recorded forecasts.</p>}
      </div>
    </Panel>
  );
}

const KIND_LABEL: Record<Incident["kind"], string> = {
  watch: "Flood watch", "watch-up": "Forecast", "watch-lifted": "Flood watch", "stage-up": "Stage", "stage-down": "Stage",
  offline: "Gauge", online: "Gauge", alert: "Public alert",
};

function IncidentFeed({ storm, incidents, alertStatus, onOpenAlert }: {
  storm: Storm; incidents: Incident[]; alertStatus: (moment: number) => RequestStatus | null; onOpenAlert: (moment: number) => void;
}) {
  const ordered = [...incidents].reverse();
  let lastDay = "";
  return (
    <Panel eyebrow="Incident feed · derived from the replay clock" title={`${incidents.length} ${incidents.length === 1 ? "incident" : "incidents"}`} className="co-feed-panel">
      {ordered.length === 0 ? (
        <p className="co-empty">No incidents yet. Play the replay: watches, stage changes, gauge outages and public alert requests appear here as the storm unfolds.</p>
      ) : (
        <ol className="co-feed" aria-live="polite">
          {ordered.map((incident) => {
            const day = fmtDay(stepDate(storm, incident.step));
            const showDay = day !== lastDay;
            lastDay = day;
            const status = incident.moment !== undefined ? alertStatus(incident.moment) : null;
            return (
              <li key={incident.id} className={`co-incident is-${incident.severity}`}>
                {showDay && <span className="co-feed-day">{day}</span>}
                <div className="co-incident-row">
                  <time>{timeAt(storm, incident.step)}</time>
                  <div className="co-incident-body">
                    <span className="co-incident-kind">{incident.kind === "alert" ? <Siren size={11} aria-hidden="true" /> : null}{KIND_LABEL[incident.kind]}</span>
                    <strong>{incident.kind === "alert" && status && status !== "awaiting" ? `Public alert drafted · ${STATUS_TEXT[status].toLowerCase()}` : incident.title}</strong>
                    <p>{incident.detail}</p>
                    {incident.moment !== undefined && (
                      <button type="button" className="co-btn sm" onClick={() => onOpenAlert(incident.moment!)}>
                        Open in Alert desk {status && <span className={`co-status is-${status}`}>{STATUS_TEXT[status]}</span>}
                      </button>
                    )}
                  </div>
                </div>
              </li>
            );
          })}
        </ol>
      )}
    </Panel>
  );
}
