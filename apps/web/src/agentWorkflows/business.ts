import type { BusinessSpec, Pattern, RunEvent, StageMatcher } from "./types";

export interface Visit {
  stage: number;
  start: number;
  end: number;
}

export interface StageMap {
  stageOf: number[];
  visits: Visit[];
}

export type StageStatus = "done" | "current" | "upcoming" | "skipped";

export interface StageView {
  statuses: StageStatus[];
  entries: number[];
  visit: number | null;
  stage: number | null;
}

function fieldsMatch(matcher: StageMatcher, event: RunEvent): boolean {
  return (
    (matcher.type === undefined || matcher.type === event.type) &&
    (matcher.agent === undefined || matcher.agent === event.agent) &&
    (matcher.tool === undefined || matcher.tool === event.tool) &&
    (matcher.node === undefined || matcher.node === event.node) &&
    (matcher.target === undefined || matcher.target === event.target)
  );
}

/** Stage index per event, and the visits (runs of consecutive events in one stage). Mirrors stage_of_events in specs.py. */
export function mapStages(business: BusinessSpec, events: RunEvent[]): StageMap {
  const hits = business.stages.map((stage) =>
    stage.match.map((matcher) => {
      const found: number[] = [];
      events.forEach((event, index) => fieldsMatch(matcher, event) && found.push(index));
      if (matcher.nth) return new Set(found.slice(matcher.nth - 1, matcher.nth));
      if (matcher.last) return new Set(found.slice(-1));
      return new Set(found);
    }),
  );
  const matched = events.map((_, index) => hits.findIndex((sets) => sets.some((set) => set.has(index))));
  // An agent's start belongs to the step it is preparing: its next matched event.
  const assigned = matched.map((stage, index) => {
    const event = events[index];
    if (stage >= 0 || !event.agent || event.type !== "agent_start") return stage;
    const next = matched.findIndex((value, later) => later > index && value >= 0);
    return next >= 0 && events[next].agent === event.agent ? matched[next] : -1;
  });
  const stageOf: number[] = [];
  const visits: Visit[] = [];
  let current = -1;
  events.forEach((_, index) => {
    if (assigned[index] >= 0) current = assigned[index];
    stageOf.push(current);
    if (current < 0) return;
    const last = visits[visits.length - 1];
    if (last && last.stage === current) last.end = index;
    else visits.push({ stage: current, start: index, end: index });
  });
  return { stageOf, visits };
}

export function stageView(business: BusinessSpec, map: StageMap, cursor: number, finished: boolean): StageView {
  const entries = business.stages.map(() => 0);
  let visit: number | null = null;
  map.visits.forEach((item, index) => {
    if (item.start < cursor) {
      entries[item.stage] += 1;
      visit = index;
    }
  });
  const stage = visit === null ? null : map.visits[visit].stage;
  const statuses = business.stages.map((_, index): StageStatus => {
    if (index === stage && !finished) return "current";
    if (entries[index] > 0) return "done";
    return finished ? "skipped" : "upcoming";
  });
  return { statuses, entries, visit, stage };
}

/** Cursor that shows a visit complete: every event of the visit has happened. */
export function cursorAfter(visit: Visit): number {
  return visit.end + 1;
}

export interface PlainWord {
  term: string;
  plain: string;
}

const WORDS: Record<string, PlainWord> = {
  agent: { term: "Agent", plain: "A worker with a job description (its instructions) and a few apps it may use (its tools). It decides the next step itself." },
  llm: { term: "Language model", plain: "The agent's reasoning engine. It reads, plans and writes in words." },
  tool: { term: "Tool", plain: "An app the agent is allowed to use: look something up, run a check, or take an action." },
  model: { term: "Predictive model", plain: "A specialist for one narrow question, trained on past data. It returns a score or a forecast, not a decision." },
  approval: { term: "Approval", plain: "A manager's signature. The run stops until a person says yes or no." },
  code: { term: "Code step", plain: "Fixed rules written by people. No AI, the same answer every time." },
  sequential: { term: "Sequential", plain: "An assembly line: each agent does one job, then passes the work to the next." },
  handoff: { term: "Handoff", plain: "Passing the case file to the right colleague, who decides what happens next." },
  chair: { term: "Chair", plain: "Runs the meeting: picks who speaks next and closes it when the work is done." },
  run: { term: "Run", plain: "One complete pass through the job, from the request to the result." },
};

export function plainWords(pattern: Pattern, hasModel: boolean, hasCode: boolean): PlainWord[] {
  const keys = ["agent", "llm", "tool"];
  if (hasModel) keys.push("model");
  if (hasCode) keys.push("code");
  keys.push("approval");
  if (pattern === "sequential") keys.push("sequential");
  if (pattern === "handoff") keys.push("handoff");
  if (pattern === "group_chat") keys.push("chair");
  keys.push("run");
  return keys.map((key) => WORDS[key]);
}

export function plainWord(key: "agent" | "llm" | "tool" | "model" | "approval" | "code"): string {
  return WORDS[key].plain;
}
