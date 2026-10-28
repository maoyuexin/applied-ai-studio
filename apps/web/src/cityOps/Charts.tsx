import { useMemo, useState, type PointerEvent } from "react";
import {
  CITY,
  HORIZON,
  MAIN,
  STAGES,
  axisLabel,
  ft,
  gaugeTone,
  seriesOf,
  timeAt,
  type GaugeState,
  type Reading,
  type StageKey,
  type Storm,
} from "./data";
import { useWidth } from "./hooks";

const pathOf = (points: Array<[number, number]>) =>
  points.map(([x, y], i) => `${i ? "L" : "M"}${x.toFixed(1)},${y.toFixed(1)}`).join("");

/** Observed level at Main St up to the clock, the 2-hour forecasts drawn at the time they are about, stage bands and the alert line. */
export function Hydrograph({ storm, step, line, compare }: { storm: Storm; step: number; line: number; compare: boolean }) {
  const { ref, width } = useWidth<HTMLDivElement>(720);
  const [hover, setHover] = useState<number | null>(null);
  const narrow = width < 560;
  const height = narrow ? 230 : 300;
  const m = { l: 38, r: narrow ? 12 : 64, t: 16, b: 30 };
  const main = seriesOf(storm, MAIN);
  const forecast = storm.forecast.model;
  const xMax = storm.steps - 1 + HORIZON;
  const values = main.filter((v): v is number => v !== null);
  const yMin = Math.floor(Math.min(...values) / 5) * 5 - (Math.min(...values) % 5 < 2 ? 5 : 0);
  const yMax = Math.max(50, Math.ceil(Math.max(...forecast) + 1));
  const x = (s: number) => m.l + (s / xMax) * (width - m.l - m.r);
  const y = (v: number) => m.t + (1 - (v - yMin) / (yMax - yMin)) * (height - m.t - m.b);

  const observed = useMemo(() => {
    const pts: Array<[number, number]> = [];
    for (let i = 0; i <= step; i += 1) { const v = main[i]; if (v !== null && v !== undefined) pts.push([i, v]); }
    return pts;
  }, [main, step]);
  const predicted = useMemo(() => forecast.slice(0, step + 1).map((v, j) => [j + HORIZON, v] as [number, number]), [forecast, step]);
  const baseline = useMemo(() => storm.forecast.noUpstream.slice(0, step + 1).map((v, j) => [j + HORIZON, v] as [number, number]), [storm, step]);

  const ticks: number[] = [];
  const every = narrow ? 48 : 24;
  const firstHour = (() => { for (let s = 0; s < storm.steps; s += 1) if (axisLabel(storm, s).match(/ (12 am|6 am|noon|6 pm)$/)) return s; return 0; })();
  for (let s = firstHour; s <= xMax; s += every) ticks.push(s);
  const yTicks: number[] = [];
  for (let v = Math.ceil(yMin / 5) * 5; v <= yMax; v += 5) yTicks.push(v);

  const bands: Array<{ from: number; to: number; key: StageKey }> = [
    { from: STAGES.action, to: STAGES.minor, key: "action" },
    { from: STAGES.minor, to: STAGES.moderate, key: "minor" },
    { from: STAGES.moderate, to: STAGES.major, key: "moderate" },
    { from: STAGES.major, to: yMax, key: "major" },
  ];
  const now = main[step];
  const nowF = forecast[step];

  const onMove = (event: PointerEvent<SVGSVGElement>) => {
    const box = event.currentTarget.getBoundingClientRect();
    const s = Math.round(((event.clientX - box.left - m.l) / (width - m.l - m.r)) * xMax);
    setHover(s >= 0 && s <= step ? s : null);
  };
  const hv = hover !== null ? main[hover] : null;
  const hoverMadeAt = hover !== null && hover - HORIZON >= 0 ? hover - HORIZON : null;

  return (
    <div ref={ref} className="co-chart">
      <svg width={width} height={height} role="img" aria-label={`Main St level, ${storm.name}`} onPointerMove={onMove} onPointerLeave={() => setHover(null)}>
        {bands.map((band) => (
          <rect key={band.key} className={`co-band co-band-${band.key}`} x={m.l} width={width - m.l - m.r} y={y(band.to)} height={y(band.from) - y(band.to)} />
        ))}
        {yTicks.map((v) => (
          <g key={v}>
            <line className="co-grid" x1={m.l} x2={width - m.r} y1={y(v)} y2={y(v)} />
            <text className="co-axis" x={m.l - 6} y={y(v) + 3.5} textAnchor="end">{v}</text>
          </g>
        ))}
        {ticks.map((s) => (
          <g key={s}>
            <line className="co-grid" x1={x(s)} x2={x(s)} y1={m.t} y2={height - m.b} />
            <text className="co-axis" x={x(s)} y={height - m.b + 16} textAnchor="middle">{axisLabel(storm, s)}</text>
          </g>
        ))}
        {!narrow && (
          <>
            <text className="co-band-label co-band-label-action" x={width - m.r + 6} y={y(STAGES.action) + 3.5}>Action {STAGES.action}</text>
            <text className="co-band-label co-band-label-major" x={width - m.r + 6} y={y(STAGES.major) - 2}>Major {STAGES.major}</text>
          </>
        )}
        <rect className="co-horizon" x={x(step)} width={Math.max(0, x(Math.min(xMax, step + HORIZON)) - x(step))} y={m.t} height={height - m.t - m.b} />
        <line className="co-alert-line" x1={m.l} x2={width - m.r} y1={y(line)} y2={y(line)} />
        <text className="co-alert-label" x={m.l + 6} y={y(line) - 5}>Alert line {line} ft</text>
        {compare && <path className="co-baseline" d={pathOf(baseline.map(([s, v]) => [x(s), y(v)]))} />}
        <path className="co-forecast" d={pathOf(predicted.map(([s, v]) => [x(s), y(v)]))} />
        <path className="co-observed" d={pathOf(observed.map(([s, v]) => [x(s), y(v)]))} />
        {storm.moments.map((moment) => (
          <path key={moment.moment} className={`co-moment-mark${moment.step <= step ? " is-past" : ""}`}
            d={`M${x(moment.step)},${height - m.b - 1} l-5,-8 h10 z`}>
            <title>Public alert request · {moment.name}</title>
          </path>
        ))}
        <line className="co-now" x1={x(step)} x2={x(step)} y1={m.t - 4} y2={height - m.b} />
        {now !== null && now !== undefined && <circle className="co-now-dot" cx={x(step)} cy={y(now)} r={4.5} />}
        {nowF !== undefined && step + HORIZON <= xMax && (
          <g>
            <circle className="co-forecast-dot" cx={x(step + HORIZON)} cy={y(nowF)} r={4} />
            <text className="co-forecast-label" x={x(step + HORIZON) + (x(step + HORIZON) > width - m.r - 80 ? -8 : 8)} y={y(nowF) - 8}
              textAnchor={x(step + HORIZON) > width - m.r - 80 ? "end" : "start"}>{ft(nowF)} by {timeAt(storm, step + HORIZON)}</text>
          </g>
        )}
        {hover !== null && (
          <line className="co-hover" x1={x(hover)} x2={x(hover)} y1={m.t} y2={height - m.b} />
        )}
      </svg>
      <div className="co-chart-foot">
        {hover !== null ? (
          <span className="co-readout">
            <b>{timeAt(storm, hover)}</b> observed {ft(hv, 2)}
            {hoverMadeAt !== null && <> · forecast made at {timeAt(storm, hoverMadeAt)}: {ft(forecast[hoverMadeAt])}</>}
          </span>
        ) : (
          <span className="co-legend">
            <span><i className="co-key co-key-observed" />Observed</span>
            <span><i className="co-key co-key-forecast" />2-hour forecast, drawn at the time it is about</span>
            {compare && <span><i className="co-key co-key-baseline" />Same model without upstream gauges</span>}
            <span><i className="co-key co-key-alert" />Alert line</span>
            <span><i className="co-key co-key-bands" />NWS stages {STAGES.action} / {STAGES.minor} / {STAGES.moderate} / {STAGES.major} ft</span>
          </span>
        )}
      </div>
    </div>
  );
}

// ---------- mini map ----------

type Point = [number, number];

const PAD = 30;

function useProjection(width: number, height: number) {
  return useMemo(() => {
    const coords: Point[] = [...Object.values(CITY.channel).flat(), ...CITY.gauges.filter((g) => g.lon !== undefined && g.lat !== undefined).map((g) => [g.lon!, g.lat!] as Point)];
    const lons = coords.map((c) => c[0]);
    const lats = coords.map((c) => c[1]);
    const [minLon, maxLon, minLat, maxLat] = [Math.min(...lons), Math.max(...lons), Math.min(...lats), Math.max(...lats)];
    const k = Math.cos(((minLat + maxLat) / 2) * (Math.PI / 180));
    const scale = Math.min((width - 2 * PAD) / ((maxLon - minLon) * k), (height - 2 * PAD - 16) / (maxLat - minLat));
    const offX = (width - (maxLon - minLon) * k * scale) / 2;
    const offY = (height - 16 - (maxLat - minLat) * scale) / 2;
    return ([lon, lat]: Point): Point => [offX + (lon - minLon) * k * scale, offY + (maxLat - lat) * scale];
  }, [width, height]);
}

/** Middle point of a stream line, for its label. */
const midOf = (coords: Point[]) => coords[Math.floor(coords.length / 2)] ?? [0, 0];

export function MiniMap({ storm, states, stage, onPick, picked }: {
  storm: Storm; states: Record<string, GaugeState>; stage: StageKey; onPick: (key: string) => void; picked: string | null;
}) {
  const { ref, width } = useWidth<HTMLDivElement>(480);
  const height = Math.round(Math.min(320, Math.max(220, width * 0.55)));
  const project = useProjection(width, height);
  const lines = Object.entries(CITY.channel).map(([name, coords]) => ({ name, d: pathOf(coords.map((c) => project(c))), mid: project(midOf(coords)), start: project(coords[0] ?? [0, 0]) }));
  const placed = CITY.gauges.filter((g) => g.lon !== undefined && g.lat !== undefined && states[g.key]);
  const offMap = CITY.gauges.filter((g) => (g.lon === undefined || g.lat === undefined) && states[g.key]);
  // Label placement per gauge so names and values never sit on a stream label or on each other.
  const SIDE: Record<string, "above" | "below" | "right"> = { alief: "above", main: "above", gessner: "right", keegans: "below" };
  return (
    <div ref={ref} className="co-map">
      <svg width={width} height={height} role="img" aria-label={`Gauge map, ${storm.name}`}>
        {lines.map((line) => <path key={line.name} className={`co-stream co-stream-${line.name}`} d={line.d} />)}
        {lines.map((line) => (
          <text key={line.name} className="co-map-note" x={line.name === "brays" ? line.mid[0] : line.start[0]} y={line.name === "brays" ? line.mid[1] - 12 : line.start[1] - 10}
            textAnchor={line.name === "brays" ? "middle" : "start"}>
            {line.name === "brays" ? "Brays Bayou" : "Keegans Bayou"}
          </text>
        ))}
        <text className="co-map-note" x={width - 8} y={height - 8} textAnchor="end">flows east toward downtown →</text>
        {placed.map((gauge) => {
          const [cx, cy] = project([gauge.lon!, gauge.lat!]);
          const state = states[gauge.key];
          const tone = gaugeTone(gauge.key, state, stage);
          const side = SIDE[gauge.key] ?? "above";
          const anchor = side === "right" ? "start" : cx > width - 60 ? "end" : cx < 60 ? "start" : "middle";
          const tx = side === "right" ? cx + 12 : anchor === "end" ? cx + 8 : anchor === "start" ? cx - 8 : cx;
          const [ly, vy] = side === "right" ? [cy - 1, cy + 13] : side === "below" ? [cy + 22, cy + 36] : [cy - 28, cy - 14];
          return (
            <g key={gauge.key} className={`co-gauge-pin is-${tone}${picked === gauge.key ? " is-picked" : ""}`} role="button" tabIndex={0}
              aria-label={`${gauge.name}: ${state.offline ? "offline" : ft(state.last?.value, 2)}`}
              onClick={() => onPick(gauge.key)} onKeyDown={(event) => { if (event.key === "Enter" || event.key === " ") { event.preventDefault(); onPick(gauge.key); } }}>
              {gauge.key === MAIN && tone !== "ok" && tone !== "rising" && <circle className="co-pin-pulse" cx={cx} cy={cy} r={11} />}
              <circle className="co-pin" cx={cx} cy={cy} r={gauge.key === MAIN ? 8 : 6.5} />
              {state.offline && <path className="co-pin-x" d={`M${cx - 3.5},${cy - 3.5}l7,7m0,-7l-7,7`} />}
              <text className="co-pin-label" x={tx} y={ly} textAnchor={anchor}>{gauge.short}</text>
              <text className={`co-pin-value${state.offline ? " is-offline" : ""}`} x={tx} y={vy} textAnchor={anchor}>
                {state.offline ? "offline" : ft(state.last?.value)}
              </text>
            </g>
          );
        })}
      </svg>
      {offMap.length > 0 && (
        <p className="co-map-off">
          {offMap.map((g) => <span key={g.key}>{g.name} is a separate bayou north of this map; see the gauge board.</span>)}
        </p>
      )}
    </div>
  );
}

export function Sparkline({ series, step, span = 24 }: { series: Reading[]; step: number; span?: number }) {
  const from = Math.max(0, step - span);
  const pts: Point[] = [];
  for (let i = from; i <= step; i += 1) { const v = series[i]; if (v !== null && v !== undefined) pts.push([i, v]); }
  if (pts.length < 2) return <svg className="co-spark" width={84} height={24} aria-hidden="true" />;
  const vs = pts.map((p) => p[1]);
  const lo = Math.min(...vs);
  const hi = Math.max(...vs);
  const range = Math.max(hi - lo, 0.5);
  const d = pathOf(pts.map(([s, v]) => [((s - from) / span) * 82 + 1, 22 - ((v - lo) / range) * 20]));
  return <svg className="co-spark" width={84} height={24} aria-hidden="true"><path d={d} /></svg>;
}
