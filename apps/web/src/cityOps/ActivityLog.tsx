import { useMemo, useState } from "react";
import type { RunDetail } from "../design/api";
import { dayTimeAt, fmtRecorded, stepDate, type Storm } from "./data";
import type { Incident } from "./incidents";
import { Panel } from "./ui";

interface Entry {
  key: string;
  at: number;
  when: string;
  source: "replay" | "cameras" | "alerts";
  tone: string;
  title: string;
  note?: string;
  group?: string;
}

const SOURCE_TEXT: Record<Entry["source"], string> = { replay: "Replay", cameras: "Camera desk", alerts: "Alert desk" };

function decisionEntries(detail: RunDetail | null, source: "cameras" | "alerts"): Entry[] {
  if (!detail) return [];
  const steps = Object.fromEntries(detail.steps.map((s) => [s.key, s.title]));
  const labels = Object.fromEntries(detail.artifacts.map((a) => [a.id, a.label ?? a.id]));
  const decisions: Entry[] = detail.decisions.map((d) => {
    const label = d.artifact_id ? labels[d.artifact_id] ?? d.artifact_id : "";
    const title = d.action === "approve"
      ? (d.step_key === "desk" ? "Closed the sign-off desk" : d.step_key === "policy" ? "Adopted the camera access policy" : `Approved: ${steps[d.step_key ?? ""] ?? d.step_key}`)
      : d.action === "sign" ? `Signed ${label}: ${d.verdict === "edit" ? "approved with edits" : d.verdict === "approve" ? "approved" : d.verdict}`
      : d.action === "resolve" ? `Review · ${label}: ${d.verdict}`
      : `${d.action}${label ? ` · ${label}` : ""}${d.verdict ? `: ${d.verdict}` : ""}`;
    const tone = d.verdict === "reject" ? "warning" : d.action === "approve" ? "ok" : d.verdict === "fixed" || d.verdict === "edit" ? "watch" : "info";
    return {
      key: `${source}-d${d.id}`, at: new Date(d.at).getTime(), when: fmtRecorded(d.at), source, tone, title,
      note: d.note ?? undefined, group: d.action === "resolve" || d.action === "sign" ? `${source}:${d.action}:${d.step_key}` : undefined,
    };
  });
  const events: Entry[] = detail.events
    .filter((e) => e.code === "policy" || e.code === "reopened")
    .map((e) => ({
      key: `${source}-e${e.id}`, at: new Date(e.at).getTime(), when: fmtRecorded(e.at), source, tone: "info",
      title: e.code === "policy" ? "Saved the camera access policy" : e.message,
    }));
  return [...decisions, ...events];
}

type Row = { kind: "one"; entry: Entry } | { kind: "group"; key: string; entries: Entry[] };

export default function ActivityLog({ storm, incidents, cameras, alerts }: {
  storm: Storm; incidents: Incident[]; cameras: RunDetail | null; alerts: RunDetail | null;
}) {
  const [filter, setFilter] = useState<"all" | "replay" | "desk">("all");
  const entries = useMemo(() => {
    const replay: Entry[] = incidents.map((incident) => ({
      key: `r-${incident.id}`, at: stepDate(storm, incident.step).getTime(), when: `${dayTimeAt(storm, incident.step)}, ${storm.year}`,
      source: "replay", tone: incident.severity, title: incident.title, note: incident.detail,
    }));
    const desk = [...decisionEntries(cameras, "cameras"), ...decisionEntries(alerts, "alerts")];
    const all = filter === "replay" ? replay : filter === "desk" ? desk : [...replay, ...desk];
    return all.sort((a, b) => b.at - a.at || b.key.localeCompare(a.key));
  }, [incidents, storm, cameras, alerts, filter]);

  // Runs of three or more review or sign-off decisions fold into one row.
  const rows: Row[] = [];
  for (const entry of entries) {
    const last = rows.at(-1);
    if (entry.group && last?.kind === "group" && last.key === entry.group) last.entries.push(entry);
    else if (entry.group && last?.kind === "one" && last.entry.group === entry.group) rows[rows.length - 1] = { kind: "group", key: entry.group, entries: [last.entry, entry] };
    else rows.push({ kind: "one", entry });
  }
  const flat: Row[] = rows.flatMap((row) => (row.kind === "group" && row.entries.length < 3 ? row.entries.map((entry) => ({ kind: "one" as const, entry })) : [row]));

  return (
    <Panel eyebrow="Activity log" title="Replay incidents and recorded desk decisions"
      aside={(
        <div className="co-seg" role="radiogroup" aria-label="Show">
          {([["all", "All"], ["replay", "Replay incidents"], ["desk", "Desk decisions"]] as const).map(([key, text]) => (
            <button key={key} type="button" role="radio" aria-checked={filter === key} className={filter === key ? "is-on" : ""} onClick={() => setFilter(key)}>{text}</button>
          ))}
        </div>
      )}>
      <p className="co-dim co-log-note">Newest first. Replay incidents carry storm time ({storm.name}, up to the replay clock); desk decisions carry the time they were recorded in the Design Studio. No user names are recorded.</p>
      {flat.length === 0 ? <p className="co-empty">Nothing yet.</p> : (
        <ol className="co-log">
          {flat.map((row) => row.kind === "one" ? (
            <li key={row.entry.key} className={`is-${row.entry.tone}`}>
              <time>{row.entry.when}</time>
              <span className={`co-source is-${row.entry.source}`}>{SOURCE_TEXT[row.entry.source]}</span>
              <div><strong>{row.entry.title}</strong>{row.entry.note && <p>{row.entry.note}</p>}</div>
            </li>
          ) : (
            <li key={`${row.key}-${row.entries[0].key}`} className="is-info">
              <time>{row.entries[0].when}</time>
              <span className={`co-source is-${row.entries[0].source}`}>{SOURCE_TEXT[row.entries[0].source]}</span>
              <details>
                <summary><strong>{row.entries.length} {row.entries[0].group?.includes(":sign:") ? "drafts signed" : "disagreements reviewed"}</strong> · {row.entries.at(-1)!.when} to {row.entries[0].when}</summary>
                <ul>{row.entries.map((e) => <li key={e.key}>{e.title}{e.note ? ` · ${e.note}` : ""}</li>)}</ul>
              </details>
            </li>
          ))}
        </ol>
      )}
    </Panel>
  );
}
