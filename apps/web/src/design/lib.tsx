import { useEffect, useState } from "react";
import { navigate } from "../router";
import { designApi, errorMessage, type Artifact, type Brief, type PipelineKey, type Reference, type StepSpec } from "./api";
import { Banner } from "./ui";

export const BASE_PATH = "/design-studio";

export function go(path: string) {
  navigate(path.startsWith("/") ? path : `${BASE_PATH}/${path}`);
  window.scrollTo({ top: 0 });
}

export function checkFlag(artifact: Artifact): { text: string; bad: boolean } | null {
  if (artifact.status === "blocked") return { text: "blocked", bad: true };
  if (artifact.status === "failed") return { text: "failed", bad: true };
  const content = artifact.checks.filter((check) => check.key !== "c2pa");
  const worst = content.find((check) => check.state === "bad") ?? content.find((check) => check.state === "warn");
  if (!worst) return null;
  const text = worst.key === "motion" ? "low motion" : worst.key === "audio" ? "audio?" : worst.key === "listen-back" ? "words differ" : worst.key === "c2pa" ? "C2PA" : worst.label;
  return { text, bad: worst.state === "bad" };
}

export function timeOf(iso: string): string {
  const date = new Date(iso);
  return date.toLocaleTimeString([], { hour: "numeric", minute: "2-digit" });
}

export function clockOf(iso: string): string {
  return new Date(iso).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", hour12: false });
}

export function when(iso: string): string {
  const date = new Date(iso);
  const today = new Date();
  const yesterday = new Date(today);
  yesterday.setDate(today.getDate() - 1);
  if (date.toDateString() === today.toDateString()) return `Today ${timeOf(iso)}`;
  if (date.toDateString() === yesterday.toDateString()) return `Yesterday ${timeOf(iso)}`;
  return date.toLocaleDateString([], { month: "short", day: "numeric" }) + ` ${timeOf(iso)}`;
}

export function bytes(value: number): string {
  if (value > 1e9) return `${(value / 1e9).toFixed(1)} GB`;
  if (value > 1e6) return `${(value / 1e6).toFixed(0)} MB`;
  return `${Math.round(value / 1e3)} KB`;
}

export const PREFILL_KEY = "design-studio:prefill";

export interface Prefill {
  pipeline: PipelineKey;
  title?: string;
  brief?: Partial<Brief>;
  references?: Array<Reference & { thumb_sha?: string }>;
  parent_run_id?: string;
  note?: string;
}

type RefItem = Reference & { thumb_sha?: string };

export function useUploader(onAdd: (items: RefItem[]) => void) {
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const upload = async (files: FileList | File[]) => {
    const list = Array.from(files).filter((file) => file.type.startsWith("image/"));
    if (!list.length) return;
    setUploading(true);
    setError(null);
    try {
      const added: RefItem[] = [];
      for (const file of list) {
        const result = await designApi.upload(file);
        added.push({ sha: result.sha, thumb_sha: result.thumb_sha, role: "subject", name: file.name.slice(0, 120) });
      }
      onAdd(added);
    } catch (problem) {
      setError(errorMessage(problem));
    } finally {
      setUploading(false);
    }
  };
  return { upload, uploading, error };
}

/** Wrap an async action: tracks busy state and surfaces errors in a toast. */
export function useAction() {
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  useEffect(() => {
    if (!error) return;
    const timer = window.setTimeout(() => setError(null), 9000);
    return () => window.clearTimeout(timer);
  }, [error]);
  const run = async <T,>(key: string, work: () => Promise<T>): Promise<T | undefined> => {
    setBusy(key);
    setError(null);
    try {
      return await work();
    } catch (problem) {
      setError(problem instanceof Error ? problem.message : String(problem));
      return undefined;
    } finally {
      setBusy(null);
    }
  };
  const toast = error ? (
    <div className="ds-toast">
      <Banner kind="error">
        {error}{" "}
        <button type="button" className="ds-btn sm ghost" onClick={() => setError(null)}>Dismiss</button>
      </Banner>
    </div>
  ) : null;
  return { busy, error, setError, run, toast };
}


const TOOLS: Record<string, string> = {
  shotlist: "no model · your lines as written",
  assemble: "automatic · ffmpeg",
  provenance: "automatic · c2patool",
  finish: "automatic · label + Content Credentials check",
  mix: "automatic · ffmpeg",
  setup: "you · images, questions and labels",
  check: "automatic · compares each answer with your labels",
  review: "you · each disagreement",
  desk: "you · approve, edit or reject each draft",
  policy: "you · the rules",
  report: "automatic · tables, CSV and JSON",
};

/** Who does a step: the model for its role (with the article checker), or the tool for automatic steps. */
export function stepWorker(step: { key: string; role: string | null }, model: (role: string) => string | undefined,
  pipeline: string): string {
  if (!step.role || step.role === "tool") return TOOLS[step.key] ?? "automatic";
  if (pipeline === "inspect" && step.key === "ask") return "the vision models you pick · all questions in one call";
  if (pipeline === "alerts" && step.key === "draft") return "the text models you pick · every language in one call";
  if (pipeline === "alerts" && step.key === "check") return `${model("text-judge") ?? "a second model"} back-translates · the app checks the rules`;
  const main = model(step.role) ?? step.role;
  if (pipeline === "article" && step.key === "draft") return `${main} · checked by ${model("text-judge") ?? "a second model"}`;
  if (pipeline === "voice" && step.key === "lines") return `${main} · listen-back check`;
  return main;
}

/** Video steps when the prompt helper is off: no text model and no keyframes; every shot is text → video. */
export function promptOnlySteps(steps: StepSpec[]): StepSpec[] {
  return steps.filter((step) => step.key !== "keyframes").map((step) => step.key === "shotlist"
    ? { ...step, title: "Your lines → shots", role: "tool", description: "Each line of your brief is one shot, sent to Sora as written. You can still edit the lines before any video is made." }
    : step);
}
