import raw from "./houston-storms.json";

export type Reading = number | null;

export interface GaugeInfo {
  key: string;
  usgs: string;
  name: string;
  short: string;
  role: string;
  lat?: number;
  lon?: number;
}

export interface StormMoment {
  moment: number;
  step: number;
  name: string;
  question: string;
}

export interface Storm {
  id: string;
  name: string;
  year: number;
  start: string;
  stepMinutes: number;
  steps: number;
  crossingStep: number;
  peakFt: number;
  series: Record<string, Reading[] | null | undefined>;
  forecast: { model: number[]; noUpstream: number[] };
  moments: StormMoment[];
}

export interface Stages {
  action: number;
  minor: number;
  moderate: number;
  major: number;
}

export interface CityData {
  about: string;
  stages: Stages;
  horizonMinutes: number;
  alertLines: number[];
  defaultLine: number;
  gauges: GaugeInfo[];
  channel: Record<string, Array<[number, number]>>;
  storms: Storm[];
  runs: { cameras: string; alerts: string };
}

export const CITY = raw as unknown as CityData;
export const STORMS = CITY.storms;
export const STAGES = CITY.stages;
/** Forecast horizon in replay steps (2 hours = 8 steps of 15 minutes). */
export const HORIZON = Math.round(CITY.horizonMinutes / (STORMS[0]?.stepMinutes ?? 15));
/** A gauge with no reading for this many steps (1 hour) is offline. */
export const OFFLINE_STEPS = 4;
export const MAIN = "main";

export function stormById(id: string | null | undefined): Storm {
  return STORMS.find((storm) => storm.id === id) ?? STORMS[0];
}

/** Gauges that have a series in this storm (White Oak exists for Harvey only). */
export function stormGauges(storm: Storm): GaugeInfo[] {
  return CITY.gauges.filter((gauge) => Array.isArray(storm.series[gauge.key]));
}

export function seriesOf(storm: Storm, key: string): Reading[] {
  return storm.series[key] ?? [];
}

// ---------- time ----------
// Storm times are local (CDT) wall-clock strings. They are kept as UTC dates and read back with UTC getters,
// so the viewer's own time zone never shifts them.

const DAYS = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"];
const MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];

export function stepDate(storm: Storm, step: number): Date {
  const [day, time] = storm.start.split("T");
  const [y, m, d] = day.split("-").map(Number);
  const [hh, mm] = time.split(":").map(Number);
  return new Date(Date.UTC(y, m - 1, d, hh, mm) + step * storm.stepMinutes * 60_000);
}

export function fmtTime(date: Date): string {
  const h = date.getUTCHours();
  const m = date.getUTCMinutes();
  return `${h % 12 || 12}:${String(m).padStart(2, "0")} ${h < 12 ? "am" : "pm"}`;
}

export function fmtDay(date: Date): string {
  return `${DAYS[date.getUTCDay()]} ${MONTHS[date.getUTCMonth()]} ${date.getUTCDate()}`;
}

export const timeAt = (storm: Storm, step: number) => fmtTime(stepDate(storm, step));
export const dayTimeAt = (storm: Storm, step: number) => `${fmtDay(stepDate(storm, step))} · ${fmtTime(stepDate(storm, step))}`;

/** Short axis label such as "Sat 6 pm". */
export function axisLabel(storm: Storm, step: number): string {
  const date = stepDate(storm, step);
  const h = date.getUTCHours();
  const hour = h === 0 ? "12 am" : h === 12 ? "noon" : `${h % 12} ${h < 12 ? "am" : "pm"}`;
  return `${DAYS[date.getUTCDay()]} ${hour}`;
}

export function duration(steps: number, stepMinutes = 15): string {
  const minutes = Math.abs(steps) * stepMinutes;
  if (minutes < 60) return `${minutes} min`;
  const h = Math.floor(minutes / 60);
  const m = minutes % 60;
  return m ? `${h} h ${m} min` : `${h} h`;
}

/** Real-world time of a recorded decision, in the viewer's time zone, in the same style as storm times. */
export function fmtRecorded(iso: string): string {
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return iso;
  const h = date.getHours();
  const time = `${h % 12 || 12}:${String(date.getMinutes()).padStart(2, "0")} ${h < 12 ? "am" : "pm"}`;
  return `${DAYS[date.getDay()]} ${MONTHS[date.getMonth()]} ${date.getDate()} · ${time}, ${date.getFullYear()}`;
}

// ---------- stages ----------

export type StageKey = "normal" | "action" | "minor" | "moderate" | "major";
export const STAGE_ORDER: StageKey[] = ["normal", "action", "minor", "moderate", "major"];
export const STAGE_LABEL: Record<StageKey, string> = {
  normal: "Below action stage",
  action: "Action stage",
  minor: "Minor flooding",
  moderate: "Moderate flooding",
  major: "Major flooding",
};

export function stageOf(level: number | null | undefined): StageKey {
  if (level === null || level === undefined) return "normal";
  if (level >= STAGES.major) return "major";
  if (level >= STAGES.moderate) return "moderate";
  if (level >= STAGES.minor) return "minor";
  if (level >= STAGES.action) return "action";
  return "normal";
}

export function stageFloor(stage: StageKey): number {
  return stage === "normal" ? -Infinity : STAGES[stage];
}

// ---------- gauges ----------

export interface GaugeState {
  key: string;
  /** Reading at this exact step, or null when the gauge sent nothing. */
  value: Reading;
  /** Most recent reading at or before the step. */
  last: { step: number; value: number } | null;
  /** Change over the hour up to the last reading. */
  change1h: number | null;
  offline: boolean;
  series: Reading[];
}

export function lastReading(series: Reading[], step: number): { step: number; value: number } | null {
  for (let i = Math.min(step, series.length - 1); i >= 0; i -= 1) {
    const value = series[i];
    if (value !== null && value !== undefined) return { step: i, value };
  }
  return null;
}

export function gaugeState(storm: Storm, key: string, step: number): GaugeState {
  const series = seriesOf(storm, key);
  const value = series[step] ?? null;
  const last = lastReading(series, step);
  const before = last ? series[last.step - OFFLINE_STEPS] : null;
  const change1h = last && before !== null && before !== undefined ? last.value - before : null;
  const offline = !last || step - last.step >= OFFLINE_STEPS;
  return { key, value, last, change1h, offline, series };
}

export const ft = (value: number | null | undefined, digits = 1) =>
  value === null || value === undefined ? "—" : `${value.toFixed(digits)} ft`;

export function signedFt(value: number | null): string {
  if (value === null) return "—";
  const rounded = Math.round(value * 10) / 10;
  if (rounded === 0) return "±0.0 ft";
  return `${rounded > 0 ? "+" : "−"}${Math.abs(rounded).toFixed(1)} ft`;
}

export type GaugeTone = "ok" | "rising" | "offline" | StageKey;

export function gaugeTone(key: string, state: GaugeState, stage: StageKey): GaugeTone {
  if (state.offline) return "offline";
  if (key === MAIN && stage !== "normal") return stage;
  if ((state.change1h ?? 0) >= 1) return "rising";
  return "ok";
}

