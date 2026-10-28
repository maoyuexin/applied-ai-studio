import {
  HORIZON,
  MAIN,
  OFFLINE_STEPS,
  STAGE_LABEL,
  STAGE_ORDER,
  STAGES,
  duration,
  ft,
  seriesOf,
  stageFloor,
  stageOf,
  stormGauges,
  timeAt,
  type StageKey,
  type Storm,
} from "./data";

/** A forecast that stays below the line this long (6 hours) ends a flood watch. Same rule as the Flood Watch lab. */
export const WATCH_MERGE_STEPS = 24;
/** Falling back a stage needs the level this far below the stage line, so a level hovering at a line does not flap. */
const STAGE_HYSTERESIS_FT = 0.5;

export type Severity = "info" | "ok" | "watch" | "warning" | "critical";
export type IncidentKind = "watch" | "watch-up" | "watch-lifted" | "stage-up" | "stage-down" | "offline" | "online" | "alert";

export interface Incident {
  id: string;
  step: number;
  kind: IncidentKind;
  severity: Severity;
  title: string;
  detail: string;
  gauge?: string;
  moment?: number;
}

export interface OpsState {
  incidents: Incident[];
  watch: { active: boolean; since: number | null; issued: number; leadSteps: number | null; crossedAt: number | null };
  /** Stage used for announcements (with hysteresis, so a level hovering at a line does not flap). */
  stage: StageKey;
  /** Stage of the latest observed level, for badges and the map. */
  levelStage: StageKey;
  offline: string[];
}

const stageSeverity = (stage: StageKey): Severity =>
  stage === "major" || stage === "moderate" ? "critical" : stage === "minor" ? "warning" : stage === "action" ? "watch" : "ok";

/**
 * Everything the operations view shows, derived only from the recorded storm, the alert line and the clock.
 * Recomputed from step 0 every time, so scrubbing backwards gives the same answer as playing forwards.
 */
export function deriveOps(storm: Storm, line: number, upTo: number): OpsState {
  const incidents: Incident[] = [];
  const main = seriesOf(storm, MAIN);
  const forecast = storm.forecast.model;
  const gauges = stormGauges(storm);
  const names = Object.fromEntries(gauges.map((g) => [g.key, g.short]));

  let watchActive = false;
  let watchSince: number | null = null;
  let lastAbove = -1;
  let watchStage: StageKey = "normal";
  let issued = 0;
  let leadSteps: number | null = null;
  let crossedAt: number | null = null;
  let stage: StageKey = "normal";
  const lastSeen: Record<string, number | null> = {};
  const isOffline: Record<string, boolean> = {};
  gauges.forEach((g) => { lastSeen[g.key] = null; isOffline[g.key] = false; });

  for (let i = 0; i <= upTo && i < storm.steps; i += 1) {
    // Flood watch: the 2-hour forecast made now reaches the alert line.
    const f = forecast[i];
    if (f !== undefined && f >= line) {
      lastAbove = i;
      const target = timeAt(storm, i + HORIZON);
      const fStage = stageOf(f);
      if (!watchActive) {
        watchActive = true;
        watchSince = i;
        watchStage = fStage;
        issued += 1;
        incidents.push({
          id: `watch-${i}`, step: i, kind: "watch", severity: "watch",
          title: `Flood watch: Main St forecast ${ft(f)} by ${target}`,
          detail: `The 2-hour forecast made at ${timeAt(storm, i)} reached the ${line} ft alert line.`,
        });
      } else if (STAGE_ORDER.indexOf(fStage) > STAGE_ORDER.indexOf(watchStage) && fStage !== "normal") {
        watchStage = fStage;
        incidents.push({
          id: `watch-up-${i}`, step: i, kind: "watch-up", severity: stageSeverity(fStage),
          title: `Forecast: ${STAGE_LABEL[fStage].toLowerCase()} at Main St by ${target}`,
          detail: `2-hour forecast ${ft(f)}; ${fStage} stage starts at ${STAGES[fStage as keyof typeof STAGES]} ft.`,
        });
      }
    } else if (watchActive && i - lastAbove > WATCH_MERGE_STEPS) {
      watchActive = false;
      watchSince = null;
      watchStage = "normal";
      incidents.push({
        id: `lifted-${i}`, step: i, kind: "watch-lifted", severity: "ok",
        title: "Flood watch lifted",
        detail: `The 2-hour forecast has stayed below ${line} ft for ${duration(WATCH_MERGE_STEPS)}.`,
      });
    }

    // Observed stage at Main St.
    const level = main[i];
    if (level !== null && level !== undefined) {
      const raw = stageOf(level);
      const up = STAGE_ORDER.indexOf(raw) > STAGE_ORDER.indexOf(stage);
      let next: StageKey = stage;
      if (up) next = raw;
      else {
        while (next !== "normal" && level < stageFloor(next) - STAGE_HYSTERESIS_FT) next = STAGE_ORDER[STAGE_ORDER.indexOf(next) - 1];
      }
      if (next !== stage) {
        if (up) {
          if (crossedAt === null) {
            crossedAt = i;
            leadSteps = watchActive && watchSince !== null ? i - watchSince : null;
          }
          incidents.push({
            id: `stage-${i}`, step: i, kind: "stage-up", severity: stageSeverity(next), gauge: MAIN,
            title: `Main St: ${STAGE_LABEL[next].toLowerCase()} · ${ft(level, 2)}`,
            detail: `Observed level passed ${STAGES[next as keyof typeof STAGES]} ft (${next} stage).`,
          });
        } else {
          incidents.push({
            id: `stage-down-${i}`, step: i, kind: "stage-down", severity: "ok", gauge: MAIN,
            title: next === "normal" ? `Main St back below action stage · ${ft(level, 2)}` : `Main St down to ${STAGE_LABEL[next].toLowerCase()} · ${ft(level, 2)}`,
            detail: `Observed level fell below ${STAGES[stage as keyof typeof STAGES]} ft.`,
          });
        }
        stage = next;
      }
    }

    // Gauges going dark and coming back.
    for (const gauge of gauges) {
      const value = seriesOf(storm, gauge.key)[i];
      const seen = lastSeen[gauge.key];
      if (value !== null && value !== undefined) {
        if (isOffline[gauge.key]) {
          isOffline[gauge.key] = false;
          incidents.push({
            id: `online-${gauge.key}-${i}`, step: i, kind: "online", severity: "ok", gauge: gauge.key,
            title: `Gauge back online: ${names[gauge.key]} · ${ft(value, 2)}`,
            detail: seen === null ? "First reading of this replay." : `No data for ${duration(i - seen)} before this reading.`,
          });
        }
        lastSeen[gauge.key] = i;
      } else if (!isOffline[gauge.key] && seen !== null && i - seen >= OFFLINE_STEPS) {
        isOffline[gauge.key] = true;
        incidents.push({
          id: `offline-${gauge.key}-${i}`, step: i, kind: "offline", severity: "warning", gauge: gauge.key,
          title: `Gauge offline: ${names[gauge.key]}`,
          detail: `No reading since ${timeAt(storm, seen)}. Its last value may not be the current level.`,
        });
      }
    }

    // Public alert requests recorded for this storm.
    for (const moment of storm.moments) {
      if (moment.step !== i) continue;
      incidents.push({
        id: `alert-${moment.moment}`, step: i, kind: "alert", severity: "info", moment: moment.moment,
        title: "Public alert drafted · awaiting approval",
        detail: `Resident asks: “${moment.question}”`,
      });
    }
  }

  let latest: number | null = null;
  for (let i = Math.min(upTo, main.length - 1); i >= 0 && latest === null; i -= 1) latest = main[i] ?? null;
  return {
    incidents,
    watch: { active: watchActive, since: watchSince, issued, leadSteps, crossedAt },
    stage,
    levelStage: stageOf(latest),
    offline: gauges.filter((g) => isOffline[g.key]).map((g) => g.key),
  };
}
