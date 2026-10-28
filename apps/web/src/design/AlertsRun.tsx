import { useEffect, useMemo, useState } from "react";
import { createPortal } from "react-dom";
import { Check, Download, Pencil, X } from "lucide-react";
import { mediaUrl, type AlertLanguage, type AlertMoment, type AlertsReport, type Artifact, type Check as CheckItem } from "./api";
import type { RunViewProps } from "./RunPage";
import { Checks, Progress, ReviewTag, Spinner } from "./ui";

type Grades = Record<string, Record<string, CheckItem[]>>;
type Messages = Record<string, Record<string, string>>;
type Signoff = { verdict: "approve" | "edit" | "reject"; edits: Messages; note: string; at: string };

const PART_LABEL: Record<string, string> = { alert: "Alert", answer: "Answer to the resident" };
const VERDICT: Record<string, { text: string; tone: string }> = {
  approve: { text: "approved", tone: "ok" },
  edit: { text: "edited", tone: "or" },
  reject: { text: "rejected", tone: "bad" },
};
const pct = (part: number, whole: number) => (whole ? `${Math.round((100 * part) / whole)}%` : "—");

const messagesOf = (draft: Artifact) => (draft.data.messages ?? {}) as Messages;
const gradesOf = (draft: Artifact) => (draft.data.grades ?? {}) as Grades;
const backOf = (draft: Artifact) => (draft.data.back ?? {}) as Messages;
const signoffOf = (draft: Artifact) => draft.data.signoff as Signoff | undefined;
const flags = (checks: CheckItem[] | undefined) => (checks ?? []).filter((c) => c.state === "bad" || c.state === "warn");

function FlagChips({ checks }: { checks: CheckItem[] | undefined }) {
  const bad = flags(checks);
  if (!checks) return <span className="ds-chip"><Spinner size={11} /> checking</span>;
  if (!bad.length) return <span className="ds-chip ok">no flags</span>;
  return <>{bad.map((c) => <span key={c.key} className={`ds-chip ${c.state}`} title={c.label}>{c.key}</span>)}</>;
}

function DraftDialog({ draft, moment, languages, open, act, busy, onClose }: {
  draft: Artifact; moment: AlertMoment; languages: AlertLanguage[]; open: boolean; act: RunViewProps["act"]; busy: string | null; onClose: () => void;
}) {
  const messages = messagesOf(draft);
  const grades = gradesOf(draft);
  const back = backOf(draft);
  const signoff = signoffOf(draft);
  const parts = Object.keys(messages);
  const [editing, setEditing] = useState(false);
  const [edits, setEdits] = useState<Messages>({});
  const [note, setNote] = useState(signoff?.note ?? "");
  useEffect(() => {
    const onKey = (event: KeyboardEvent) => { if (event.key === "Escape") onClose(); };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);
  const textOf = (code: string, part: string) => edits[code]?.[part] ?? signoff?.edits?.[code]?.[part] ?? messages[part]?.[code] ?? "";
  const sign = async (verdict: Signoff["verdict"]) => {
    const payload: Record<string, unknown> = { draft_id: draft.id, verdict, note };
    if (verdict === "edit") {
      payload.edits = Object.fromEntries(languages.map((lang) => [lang.code, Object.fromEntries(parts.map((part) => [part, textOf(lang.code, part)]))]));
    }
    await act("sign", payload);
    setEditing(false);
  };
  return createPortal(
    <div className="ds">
      <div className="ds-dialog-backdrop" role="presentation" onMouseDown={(event) => { if (event.target === event.currentTarget) onClose(); }}>
        <div className="ds-dialog ds-ins-dialog" role="dialog" aria-modal="true" aria-label={draft.label ?? "Draft"}>
          <div className="ds-row between">
            <h2 style={{ margin: 0 }}>{draft.label}</h2>
            <div className="ds-row">
              {signoff && <span className={`ds-chip ${VERDICT[signoff.verdict].tone}`}>{VERDICT[signoff.verdict].text}</span>}
              <button type="button" className="ds-btn sm ghost" onClick={onClose} aria-label="Close"><X size={15} aria-hidden="true" /></button>
            </div>
          </div>
          <div className="ds-ins-dialog-body">
            <div className="ds-stack" style={{ gap: 8 }}>
              <div className="ds-promptbox" style={{ whiteSpace: "pre-wrap" }}><b>Facts</b>{"\n"}{moment.facts}</div>
              {moment.question && <div className="ds-promptbox"><b>Resident asks:</b> {moment.question}</div>}
              {moment.note && <p className="ds-tiny ds-muted">{moment.note}</p>}
              {open && (
                <div className="ds-card tight">
                  <h3>Sign this draft</h3>
                  <p className="ds-tiny ds-muted">Nothing is sent. Your decision and any edits are the record.</p>
                  <input aria-label="Sign-off note" value={note} onChange={(e) => setNote(e.target.value)} placeholder="Note (optional): why" />
                  <div className="ds-row" style={{ marginTop: 8 }}>
                    <button type="button" className="ds-btn sm good" disabled={busy !== null} onClick={() => void sign("approve")}><Check size={13} aria-hidden="true" /> Approve as written</button>
                    {editing
                      ? <button type="button" className="ds-btn sm warn" disabled={busy !== null} onClick={() => void sign("edit")}><Pencil size={13} aria-hidden="true" /> Save edits</button>
                      : <button type="button" className="ds-btn sm" disabled={busy !== null} onClick={() => setEditing(true)}><Pencil size={13} aria-hidden="true" /> Edit</button>}
                    <button type="button" className="ds-btn sm danger" disabled={busy !== null} onClick={() => void sign("reject")}><X size={13} aria-hidden="true" /> Reject</button>
                  </div>
                </div>
              )}
              {signoff?.note && <p className="ds-tiny ds-muted">Note: {signoff.note}</p>}
              <details>
                <summary className="ds-small ds-dim" style={{ cursor: "pointer" }}>Exact model output</summary>
                <div className="ds-promptbox ds-tiny" style={{ marginTop: 6, whiteSpace: "pre-wrap" }}>{String(draft.data.raw ?? draft.error ?? draft.status)}</div>
              </details>
            </div>
            <div className="ds-stack" style={{ gap: 10, minWidth: 0 }}>
              {languages.map((lang) => (
                <div key={lang.code} className="ds-card tight">
                  <h3>{lang.name} <span className="ds-chip">{lang.code}</span></h3>
                  {parts.map((part) => {
                    const original = messages[part]?.[lang.code] ?? "";
                    const edited = signoff?.edits?.[lang.code]?.[part];
                    const english = back[lang.code]?.[part];
                    return (
                      <div key={part} className="ds-stack" style={{ gap: 4, marginBottom: 8 }}>
                        <label>{PART_LABEL[part] ?? part}</label>
                        {editing
                          ? <textarea aria-label={`${lang.name} ${part}`} value={textOf(lang.code, part)} onChange={(e) => setEdits({ ...edits, [lang.code]: { ...edits[lang.code], [part]: e.target.value } })} style={{ minHeight: 60 }} />
                          : <div className="ds-al-msg">{edited ? <><s>{original}</s><br /><b>{edited}</b></> : original || <i className="ds-muted">missing</i>}</div>}
                        {english && lang.code !== "en" && <div className="ds-tiny ds-muted">Back-translation: {english}</div>}
                        <Checks checks={grades[lang.code]?.[part] ?? []} />
                      </div>
                    );
                  })}
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>
    </div>,
    document.body,
  );
}

function Summary({ report, models, languages }: { report: AlertsReport; models: string[]; languages: AlertLanguage[] }) {
  const keys = ["length", "disclosure", "numbers", "watch", "reviewer"];
  return (
    <div className="ds-stack">
      <div className="ds-scroll-x">
        <table className="ds-table ds-ins-table">
          <thead>
            <tr><th>Model</th><th>Drafts</th><th>Messages flagged</th>{keys.map((k) => <th key={k}>{k}</th>)}<th>Median s</th></tr>
          </thead>
          <tbody>
            {models.map((model) => {
              const row = report.models[model];
              if (!row) return null;
              return (
                <tr key={model}>
                  <td className="ds-mono ds-small">{model}</td>
                  <td>{row.drafts}</td>
                  <td className={row.flagged ? "ds-ins-bad" : ""}><b>{pct(row.flagged, row.messages)}</b> <small className="ds-muted">{row.flagged}/{row.messages}</small></td>
                  {keys.map((k) => <td key={k} className={row.checks[k] ? "ds-ins-bad" : ""}>{row.checks[k] ?? 0}</td>)}
                  <td>{row.median_seconds ?? "—"}</td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
      <div className="ds-row ds-small">
        {languages.map((lang) => {
          const row = report.languages[lang.code] ?? { messages: 0, flagged: 0 };
          return <span key={lang.code} className={`ds-chip ${row.flagged ? "warn" : "ok"}`}>{lang.name}: {row.flagged} of {row.messages} flagged</span>;
        })}
      </div>
    </div>
  );
}

export default function AlertsRun(props: RunViewProps) {
  const { detail, act, busy } = props;
  const brief = detail.run.brief;
  const moments = useMemo(() => brief.moments ?? [], [brief.moments]);
  const languages = useMemo(() => brief.languages ?? [], [brief.languages]);
  const models = useMemo(() => brief.models ?? [], [brief.models]);
  const steps = Object.fromEntries(detail.steps.map((step) => [step.key, step]));
  const drafts = detail.artifacts.filter((a) => a.kind === "draft" && a.status !== "superseded");
  const report = steps.check?.data.report as AlertsReport | undefined;
  const [lang, setLang] = useState(languages[0]?.code ?? "en");
  const [momentIndex, setMomentIndex] = useState(0);
  const [selected, setSelected] = useState<string | null>(null);
  const deskOpen = steps.desk?.status === "waiting";
  const setupWaiting = steps.setup?.status === "waiting";
  const prompts = steps.setup?.data.prompts ?? [];
  const moment = moments[momentIndex];
  const shown = drafts.filter((d) => d.params.moment === momentIndex)
    .sort((a, b) => models.indexOf(a.params.model ?? "") - models.indexOf(b.params.model ?? "") || (a.params.try ?? 0) - (b.params.try ?? 0));
  const finished = drafts.filter((a) => a.status !== "queued" && a.status !== "running").length;
  const signedCount = drafts.filter((d) => signoffOf(d)).length;
  const selectedDraft = drafts.find((d) => d.id === selected) ?? null;
  const reportArt = detail.artifacts.find((a) => a.kind === "report" && a.status !== "superseded");
  const table = detail.artifacts.find((a) => a.kind === "table" && a.status !== "superseded");

  return (
    <div className="ds-stack">
      <section id="step-setup" className="ds-card">
        <h3>Facts, languages, rules {setupWaiting && <ReviewTag waiting />}</h3>
        <p className="ds-small" style={{ marginBottom: 8 }}><b>Brief:</b> {brief.brief}</p>
        <div className="ds-row ds-small" style={{ marginBottom: 8 }}>
          <span className="ds-chip info">{moments.length} moments</span>
          {languages.map((l) => <span key={l.code} className="ds-chip" title={`Disclosure: ${l.disclosure}`}>{l.name}</span>)}
          {models.map((m) => <span key={m} className="ds-chip model">{m}</span>)}
          <span className="ds-chip">{brief.tries ?? 1} {(brief.tries ?? 1) === 1 ? "try" : "tries"} each</span>
          <span className="ds-chip">alerts ≤ {brief.max_chars ?? 160} characters</span>
          {steps.setup?.data.calls ? <span className="ds-chip">{steps.setup.data.calls} calls</span> : null}
        </div>
        {(brief.watch_terms ?? []).length > 0 && <p className="ds-tiny ds-muted">Watch terms (flagged when the facts never mention them): {(brief.watch_terms ?? []).join(", ")}</p>}
        {prompts.length > 0 && (
          <details open={setupWaiting}>
            <summary className="ds-small ds-dim" style={{ cursor: "pointer" }}>What each model is sent</summary>
            <div className="ds-promptbox scroll" style={{ marginTop: 6, whiteSpace: "pre-wrap" }}><b>Instructions:</b> {steps.setup?.data.system}{"\n\n"}{prompts[momentIndex] ?? prompts[0]}</div>
          </details>
        )}
      </section>

      {steps.draft && steps.draft.status !== "pending" && (
        <section id="step-desk" className="ds-card">
          <div className="ds-row between">
            <h3 style={{ margin: 0 }}>Drafts {steps.draft.status === "running" && <Spinner />} {deskOpen && <ReviewTag waiting />}</h3>
            <span className="ds-small ds-muted">{finished} of {drafts.length} drafted · {signedCount} signed</span>
          </div>
          {steps.draft.status === "running" && <div style={{ marginTop: 8 }}><Progress value={drafts.length ? (100 * finished) / drafts.length : 0} /></div>}
          <div className="ds-ins-bar-top" style={{ marginTop: 10 }}>
            <div className="ds-seg" role="radiogroup" aria-label="Moment">
              {moments.map((m, i) => <button key={m.name} type="button" role="radio" aria-checked={i === momentIndex} className={i === momentIndex ? "on" : ""} onClick={() => setMomentIndex(i)}>{m.name}</button>)}
            </div>
            <div className="ds-seg" role="radiogroup" aria-label="Language">
              {languages.map((l) => <button key={l.code} type="button" role="radio" aria-checked={l.code === lang} className={l.code === lang ? "on" : ""} onClick={() => setLang(l.code)}>{l.name}</button>)}
            </div>
          </div>
          {moment && (
            <div className="ds-al-facts">
              <div className="ds-promptbox" style={{ whiteSpace: "pre-wrap" }}><b>Facts</b>{"\n"}{moment.facts}</div>
              {moment.question && <div className="ds-promptbox"><b>Resident asks:</b> {moment.question}</div>}
            </div>
          )}
          {deskOpen && <p className="ds-tiny ds-muted">Open a draft to see every language, its back-translation and the checks, then approve, edit or reject it.</p>}
          <div className="ds-al-grid">
            {shown.map((draft) => {
              const messages = messagesOf(draft);
              const grades = gradesOf(draft)[lang];
              const signoff = signoffOf(draft);
              const pending = draft.status === "queued" || draft.status === "running";
              return (
                <button key={draft.id} type="button" className="ds-al-card" onClick={() => setSelected(draft.id)} aria-label={`Open ${draft.label}`} disabled={pending}>
                  <span className="ds-row between ds-small">
                    <span className="ds-mono">{draft.params.model} · try {draft.params.try}</span>
                    {signoff && <span className={`ds-chip ${VERDICT[signoff.verdict].tone}`}>{VERDICT[signoff.verdict].text}</span>}
                  </span>
                  {pending ? <span className="ds-muted"><Spinner /> drafting…</span> : draft.status !== "ready" ? <span style={{ color: "var(--red)" }}>{draft.error ?? draft.status}</span> : (
                    <>
                      <span className="ds-al-msg">{messages.alert?.[lang] || <i className="ds-muted">missing</i>}</span>
                      <span className="ds-row" style={{ gap: 4 }}><FlagChips checks={grades?.alert} /></span>
                      {messages.answer && (
                        <>
                          <span className="ds-tiny ds-dim">Answer</span>
                          <span className="ds-al-msg small">{messages.answer[lang]}</span>
                          <span className="ds-row" style={{ gap: 4 }}><FlagChips checks={grades?.answer} /></span>
                        </>
                      )}
                    </>
                  )}
                </button>
              );
            })}
          </div>
          {report && steps.check?.status === "done" && (
            <div style={{ marginTop: 14 }}>
              <h3>By model</h3>
              <Summary report={report} models={models} languages={languages} />
            </div>
          )}
        </section>
      )}

      {reportArt && (
        <section id="step-report" className="ds-card hl">
          <div className="ds-row between" style={{ marginBottom: 8 }}>
            <h3 style={{ margin: 0 }}>Report</h3>
            <div className="ds-row">
              {reportArt.media_sha && <a className="ds-btn sm" href={mediaUrl(reportArt.media_sha, `${detail.run.title.replace(/[^\w .-]+/g, "")}.json`)}><Download size={13} aria-hidden="true" /> Report (JSON)</a>}
              {table?.media_sha && <a className="ds-btn sm" href={mediaUrl(table.media_sha, `${detail.run.title.replace(/[^\w .-]+/g, "")}.csv`)}><Download size={13} aria-hidden="true" /> Every message (CSV)</a>}
            </div>
          </div>
          {reportArt.status === "ready" ? <Checks checks={reportArt.checks} /> : <p className="ds-muted"><Spinner /> Writing the report…</p>}
          {steps.desk?.status === "done" && <button type="button" className="ds-btn sm" style={{ marginTop: 10 }} onClick={() => void act("reopen", { step: "desk" })}>Reopen the desk</button>}
        </section>
      )}

      {selectedDraft && moments[selectedDraft.params.moment ?? 0] && (
        <DraftDialog draft={selectedDraft} moment={moments[selectedDraft.params.moment ?? 0]} languages={languages} open={deskOpen}
          act={act} busy={busy} onClose={() => setSelected(null)} />
      )}
    </div>
  );
}
