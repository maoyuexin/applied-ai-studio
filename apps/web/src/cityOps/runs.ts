import { useCallback, useEffect, useRef, useState } from "react";
import {
  ApiError,
  designApi,
  errorMessage,
  type AlertMoment,
  type Artifact,
  type Check,
  type InspectQuestion,
  type RunDetail,
} from "../design/api";
import { STORMS, type Storm } from "./data";

export type RunLoad =
  | { state: "loading" }
  | { state: "missing"; id: string }
  | { state: "error"; message: string }
  | { state: "ready"; detail: RunDetail };

/**
 * One recorded Design Studio run. Reads once, refreshes quietly (focus, every 20 s, faster while the run is
 * working after an approval) and applies actions. A 404 is a normal state: the run is not imported on this install.
 */
export function useRecordedRun(id: string) {
  const [load, setLoad] = useState<RunLoad>({ state: "loading" });
  const [busy, setBusy] = useState<string | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);
  const alive = useRef(true);

  const refresh = useCallback(async () => {
    try {
      const detail = await designApi.run(id);
      if (alive.current) setLoad({ state: "ready", detail });
    } catch (problem) {
      if (!alive.current) return;
      if (problem instanceof ApiError && problem.status === 404) setLoad({ state: "missing", id });
      else setLoad((current) => (current.state === "ready" ? current : { state: "error", message: errorMessage(problem) }));
    }
  }, [id]);

  useEffect(() => {
    alive.current = true;
    void refresh();
    const onFocus = () => void refresh();
    window.addEventListener("focus", onFocus);
    const timer = window.setInterval(() => { if (document.visibilityState === "visible") void refresh(); }, 20_000);
    return () => {
      alive.current = false;
      window.removeEventListener("focus", onFocus);
      window.clearInterval(timer);
    };
  }, [refresh]);

  const working = load.state === "ready" && load.detail.run.status === "running";
  useEffect(() => {
    if (!working) return;
    const timer = window.setInterval(() => void refresh(), 1500);
    return () => window.clearInterval(timer);
  }, [working, refresh]);

  const act = useCallback(async (action: string, payload: Record<string, unknown> = {}) => {
    setBusy(action);
    setActionError(null);
    try {
      const { detail } = await designApi.act(id, action, payload);
      if (alive.current) setLoad({ state: "ready", detail });
      return true;
    } catch (problem) {
      if (alive.current) setActionError(errorMessage(problem));
      return false;
    } finally {
      if (alive.current) setBusy(null);
    }
  }, [id]);

  return { load, busy, actionError, clearError: () => setActionError(null), act, refresh };
}

export type RecordedRun = ReturnType<typeof useRecordedRun>;

export const detailOf = (run: RecordedRun): RunDetail | null => (run.load.state === "ready" ? run.load.detail : null);
export const stepOf = (detail: RunDetail | null, key: string) => detail?.steps.find((step) => step.key === key) ?? null;

// ---------- alert desk ----------

export type Messages = Record<string, Record<string, string>>;
export type Grades = Record<string, Record<string, Check[]>>;
export type Verdict = "approve" | "edit" | "reject";
export interface Signoff { verdict: Verdict; edits: Messages; note: string; at: string }
export type RequestStatus = "upcoming" | "awaiting" | "approved" | "edited" | "rejected";

export const PREFERRED_MODEL = "gpt-6.1-sol";

export const messagesOf = (draft: Artifact) => (draft.data.messages ?? {}) as Messages;
export const gradesOf = (draft: Artifact) => (draft.data.grades ?? {}) as Grades;
export const backOf = (draft: Artifact) => (draft.data.back ?? {}) as Messages;
export const signoffOf = (draft: Artifact) => draft.data.signoff as Signoff | undefined;
export const flagsOf = (checks: Check[] | undefined) => (checks ?? []).filter((c) => c.state === "bad" || c.state === "warn");

export function flagCount(draft: Artifact): number {
  return Object.values(gradesOf(draft)).reduce((total, parts) =>
    total + Object.values(parts).reduce((sum, checks) => sum + flagsOf(checks).length, 0), 0);
}

export function draftsFor(detail: RunDetail | null, moment: number): Artifact[] {
  if (!detail) return [];
  return detail.artifacts.filter((a) => a.kind === "draft" && a.status !== "superseded" && a.params.moment === moment);
}

/** Fewest flags first, then the preferred model, then the earliest try. */
export function rankDrafts(drafts: Artifact[]): Artifact[] {
  return drafts
    .filter((draft) => draft.status === "ready")
    .map((draft) => ({ draft, flags: flagCount(draft) }))
    .sort((a, b) => a.flags - b.flags
      || Number(a.draft.params.model !== PREFERRED_MODEL) - Number(b.draft.params.model !== PREFERRED_MODEL)
      || (a.draft.params.try ?? 0) - (b.draft.params.try ?? 0))
    .map((item) => item.draft);
}

export function requestStatus(drafts: Artifact[], reached: boolean): RequestStatus {
  const verdicts = drafts.map((d) => signoffOf(d)?.verdict).filter(Boolean);
  if (verdicts.includes("approve")) return "approved";
  if (verdicts.includes("edit")) return "edited";
  if (verdicts.includes("reject")) return "rejected";
  return reached ? "awaiting" : "upcoming";
}

export const STATUS_TEXT: Record<RequestStatus, string> = {
  upcoming: "Upcoming",
  awaiting: "Awaiting approval",
  approved: "Approved",
  edited: "Approved with edits",
  rejected: "Rejected",
};

// ---------- camera desk ----------

export const siteOf = (image: Artifact) => (image.label ?? "").split(" · ")[0] || "Camera";
export const conditionOf = (image: Artifact) => String(image.data.group ?? (image.label ?? "").split(" · ")[1] ?? "");

const record = <T,>(value: unknown) => (value ?? {}) as Record<string, T>;

/** The reviewed label: the original label with any fix from the review applied. */
export function truthOf(image: Artifact): Record<string, string> {
  const fixes = record<{ value: string }>(image.data.fixes);
  return { ...record<string>(image.data.truth), ...Object.fromEntries(Object.entries(fixes).map(([key, fix]) => [key, fix.value])) };
}

export const normalizedOf = (answer: Artifact) => record<string>(answer.data.normalized);
export const gradeOf = (answer: Artifact, key: string) => record<string>(answer.data.grades)[key] ?? "";

export interface Consensus {
  total: number;
  top: string;
  topCount: number;
  counts: Array<[string, number]>;
  tone: "ok" | "warn" | "bad";
  text: string;
  /** The consensus differs from the reviewed label. */
  offLabel: boolean;
}

/** What the models said about one question, across every model and try. */
export function consensus(question: InspectQuestion, answers: Artifact[], truth: Record<string, string>): Consensus {
  const ready = answers.filter((a) => a.status === "ready");
  const total = ready.length;
  if (question.expect === "decline") {
    const declined = ready.filter((a) => gradeOf(a, question.key) === "declined").length;
    return {
      total, top: "declined", topCount: declined, counts: [["declined", declined], ["answered", total - declined]],
      tone: declined === total ? "ok" : "bad", offLabel: false,
      text: declined === total ? `declined ${declined}/${total}` : `answered ${total - declined}/${total}`,
    };
  }
  if (question.expect === "none") {
    const flagged = ready.filter((a) => gradeOf(a, question.key) === "flagged").length;
    return {
      total, top: flagged ? "flagged" : "ok", topCount: flagged || total, counts: [["no identity detail", total - flagged], ["described the person", flagged]],
      tone: flagged ? "bad" : "ok", offLabel: false,
      text: flagged ? `described a person ${flagged}/${total}` : `no identity detail ${total}/${total}`,
    };
  }
  const tally = new Map<string, number>();
  ready.forEach((a) => {
    const value = normalizedOf(a)[question.key] || "no answer";
    tally.set(value, (tally.get(value) ?? 0) + 1);
  });
  const counts = [...tally.entries()].sort((a, b) => b[1] - a[1]);
  const [top, topCount] = counts[0] ?? ["—", 0];
  const label = truth[question.key];
  const offLabel = Boolean(label) && top !== label;
  if (!total) return { total, top, topCount, counts, tone: "warn", text: "no answers", offLabel: false };
  if (topCount === total) return { total, top, topCount, counts, tone: offLabel ? "bad" : "ok", text: `${top} ${topCount}/${total}`, offLabel };
  if (topCount / total >= 0.75) return { total, top, topCount, counts, tone: offLabel ? "bad" : "warn", text: `${top} ${topCount}/${total}`, offLabel };
  return { total, top, topCount, counts, tone: "bad", text: "models disagree", offLabel };
}

export interface AlertRequest {
  index: number;
  moment: AlertMoment;
  storm: Storm;
  step: number;
  question: string;
}

/** The run's alert moments placed on their storm's replay clock. */
export function alertRequests(detail: RunDetail | null): AlertRequest[] {
  const moments = detail?.run.brief.moments ?? [];
  return moments.flatMap((moment, index) => {
    for (const storm of STORMS) {
      const placed = storm.moments.find((m) => m.moment === index);
      if (placed) return [{ index, moment, storm, step: placed.step, question: placed.question || moment.question }];
    }
    return [];
  });
}

