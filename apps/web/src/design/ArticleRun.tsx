import { useEffect, useMemo, useState } from "react";
import ReactMarkdown from "react-markdown";
import { Copy, Download, Pencil, Plus, Sparkles, Trash2 } from "lucide-react";
import { mediaUrl, type Artifact, type Claim } from "./api";
import type { RunViewProps } from "./RunPage";
import { Banner, Checks, Spinner } from "./ui";

type Point = { text: string; sources: number[] };

/** Word-level diff (longest common subsequence) between two texts. */
function diffWords(before: string, after: string): Array<{ kind: "same" | "del" | "ins"; text: string }> {
  const a = before.split(/(\s+)/).filter(Boolean);
  const b = after.split(/(\s+)/).filter(Boolean);
  const rows = a.length + 1;
  const cols = b.length + 1;
  const table = new Uint32Array(rows * cols);
  for (let i = a.length - 1; i >= 0; i -= 1) {
    for (let j = b.length - 1; j >= 0; j -= 1) {
      table[i * cols + j] = a[i] === b[j] ? table[(i + 1) * cols + j + 1] + 1 : Math.max(table[(i + 1) * cols + j], table[i * cols + j + 1]);
    }
  }
  const out: Array<{ kind: "same" | "del" | "ins"; text: string }> = [];
  const push = (kind: "same" | "del" | "ins", text: string) => {
    const last = out[out.length - 1];
    if (last && last.kind === kind) last.text += text;
    else out.push({ kind, text });
  };
  let i = 0;
  let j = 0;
  while (i < a.length && j < b.length) {
    if (a[i] === b[j]) { push("same", a[i]); i += 1; j += 1; }
    else if (table[(i + 1) * cols + j] >= table[i * cols + j + 1]) { push("del", a[i]); i += 1; }
    else { push("ins", b[j]); j += 1; }
  }
  while (i < a.length) { push("del", a[i]); i += 1; }
  while (j < b.length) { push("ins", b[j]); j += 1; }
  return out;
}

const VERDICT: Record<Claim["verdict"], string> = { supported: "ok", partly: "warn", unsupported: "bad" };

function OutlineEditor({ detail, act, busy, setApproveExtra }: RunViewProps) {
  const step = detail.steps.find((s) => s.key === "outline")!;
  const sources = detail.run.brief.sources ?? [];
  const [headline, setHeadline] = useState(step.data.headline ?? "");
  const [points, setPoints] = useState<Point[]>(step.data.points ?? []);
  const [note, setNote] = useState("");
  const dirty = headline !== (step.data.headline ?? "") || JSON.stringify(points) !== JSON.stringify(step.data.points ?? []);
  useEffect(() => { setHeadline(step.data.headline ?? ""); setPoints(step.data.points ?? []); }, [step.data.headline, step.data.points]);
  useEffect(() => {
    setApproveExtra(dirty ? () => ({ headline, points }) : null);
    return () => setApproveExtra(null);
  }, [dirty, headline, points, setApproveExtra]);
  return (
    <div className="ds-stack" style={{ gap: 8 }}>
      <label style={{ margin: 0 }}>Headline</label>
      <input aria-label="Headline" value={headline} onChange={(e) => setHeadline(e.target.value)} style={{ fontWeight: 650 }} />
      <label style={{ margin: "6px 0 0" }}>Points, in order</label>
      {points.map((point, index) => (
        <div key={index} className="ds-row" style={{ alignItems: "flex-start", flexWrap: "nowrap" }}>
          <span className="ds-mono ds-muted" style={{ paddingTop: 8 }}>{index + 1}</span>
          <textarea aria-label={`Point ${index + 1}`} value={point.text} onChange={(e) => setPoints(points.map((p, i) => (i === index ? { ...p, text: e.target.value } : p)))} style={{ minHeight: 44 }} />
          <span className="ds-chip" style={{ marginTop: 6 }} title={point.sources.map((s) => sources[s - 1]?.title).join("; ")}>{point.sources.length ? point.sources.map((s) => `[${s}]`).join("") : "no source"}</span>
          <button type="button" className="ds-btn sm ghost" aria-label={`Remove point ${index + 1}`} onClick={() => setPoints(points.filter((_, i) => i !== index))}><Trash2 size={13} aria-hidden="true" /></button>
        </div>
      ))}
      <div className="ds-row between">
        <div className="ds-row">
          <button type="button" className="ds-btn sm" onClick={() => setPoints([...points, { text: "", sources: [] }])}><Plus size={13} aria-hidden="true" /> Add point</button>
          <button type="button" className="ds-btn sm" disabled={!dirty || busy !== null} onClick={() => void act("update_outline", { headline, points })}>Save edits</button>
        </div>
        <span className="ds-chip model">{step.data.model} · draft {step.data.drafts}</span>
      </div>
      <form className="ds-row" onSubmit={(event) => { event.preventDefault(); if (note.trim()) void act("redraft_outline", { note }).then(() => setNote("")); }}>
        <input aria-label="Redraft note" value={note} onChange={(e) => setNote(e.target.value)} placeholder="Redraft with a note, e.g. “lead with the new launch date”" style={{ flex: 1 }} />
        <button type="submit" className="ds-btn" disabled={!note.trim() || busy !== null}>{busy === "redraft_outline" ? <Spinner /> : <Sparkles size={14} aria-hidden="true" />} Redraft</button>
      </form>
    </div>
  );
}

function ClaimsTable({ version, sourceTitles }: { version: Artifact; sourceTitles: string[] }) {
  const claims = version.data.claims ?? [];
  if (!claims.length) return <p className="ds-small ds-muted">{version.status === "ready" ? "No fact check for this version." : "Checking…"}</p>;
  const order = { unsupported: 0, partly: 1, supported: 2 };
  return (
    <div className="ds-claims">
      {[...claims].sort((x, y) => order[x.verdict] - order[y.verdict]).map((claim, index) => (
        <div key={index} className={`ds-claim ${claim.verdict}`}>
          <div className="ds-row" style={{ alignItems: "flex-start", flexWrap: "nowrap" }}>
            <span className={`ds-chip ${VERDICT[claim.verdict]}`}>{claim.verdict}</span>
            <span>{claim.claim}</span>
          </div>
          {claim.note && claim.verdict !== "supported" && <div className="ds-small" style={{ marginTop: 4 }}><b>Why:</b> {claim.note}</div>}
          {claim.evidence && <div className="ds-tiny ds-muted" style={{ marginTop: 4 }}>“{claim.evidence}”{claim.source ? ` — [${claim.source}] ${sourceTitles[claim.source - 1]?.slice(0, 60) ?? ""}` : ""}</div>}
        </div>
      ))}
    </div>
  );
}

function DraftStep(props: RunViewProps) {
  const { detail, act, busy, setApproveExtra } = props;
  const step = detail.steps.find((s) => s.key === "draft")!;
  const open = step.status === "waiting" || step.status === "running";
  const versions = detail.artifacts.filter((a) => a.kind === "version" && a.status !== "superseded");
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const selected = versions.find((v) => v.id === selectedId) ?? versions[versions.length - 1];
  const parent = selected?.parent_id ? versions.find((v) => v.id === selected.parent_id) : null;
  const [showDiff, setShowDiff] = useState(true);
  const [note, setNote] = useState("");
  const [editing, setEditing] = useState(false);
  const [text, setText] = useState("");
  const sourceTitles = (detail.run.brief.sources ?? []).map((s) => s.title);
  const latestCount = versions.length;
  useEffect(() => { setSelectedId(null); }, [latestCount]);
  useEffect(() => {
    if (step.status !== "waiting" || !selected || selected.status !== "ready") return;
    setApproveExtra(() => ({ version_id: selected.id }));
    return () => setApproveExtra(null);
  }, [selected?.id, selected?.status, step.status, setApproveExtra]); // eslint-disable-line react-hooks/exhaustive-deps
  const diff = useMemo(() => (parent && selected ? diffWords(`${parent.data.headline}\n\n${parent.data.body}`, `${selected.data.headline}\n\n${selected.data.body}`) : null), [parent, selected]);
  if (!selected) return <p className="ds-muted"><Spinner /> Writing the first draft…</p>;
  const writing = selected.status === "queued" || selected.status === "running";

  return (
    <div className="ds-stack">
      <div className="ds-row between">
        <div className="ds-row" role="tablist" aria-label="Versions">
          {versions.map((version) => (
            <button key={version.id} type="button" role="tab" aria-selected={version.id === selected.id}
              className={`ds-btn sm${version.id === selected.id ? " on" : ""}`} onClick={() => setSelectedId(version.id)}>
              {version.label}{version.data.author === "you" ? " (you)" : ""}
              {version.status === "ready" && version.metrics.claims ? <span className={`ds-chip ${version.metrics.unsupported ? "bad" : version.metrics.partly ? "warn" : "ok"}`} style={{ padding: "0 6px" }}>{version.metrics.unsupported ?? 0}</span> : null}
              {(version.status === "queued" || version.status === "running") && <Spinner size={11} />}
            </button>
          ))}
        </div>
        {parent && <label className="ds-row" style={{ margin: 0, fontWeight: 500 }}><input type="checkbox" checked={showDiff} onChange={(e) => setShowDiff(e.target.checked)} /> Show changes from {parent.label}</label>}
      </div>
      <div className="ds-grid2" style={{ gridTemplateColumns: "minmax(0, 1.15fr) minmax(0, 1fr)", alignItems: "start" }}>
        <div className="ds-card tight">
          <div className="ds-row between" style={{ marginBottom: 6 }}>
            <h3 style={{ margin: 0 }}>{selected.label}{selected.params.note ? ` · ${selected.params.note === "edited by you" ? "edited by you" : "revised"}` : ""}</h3>
            <span className="ds-tiny ds-muted">{selected.metrics.words ?? 0} words{selected.data.author ? ` · written by ${selected.data.author}` : ""}</span>
          </div>
          {selected.params.note && selected.params.note !== "edited by you" && <p className="ds-small" style={{ marginBottom: 8 }}><b>Your note:</b> {selected.params.note}</p>}
          {writing && !selected.data.body ? <p className="ds-muted"><Spinner /> Writing {selected.label}…</p> : editing ? (
            <div className="ds-stack" style={{ gap: 8 }}>
              <textarea aria-label="Edit text" value={text} onChange={(e) => setText(e.target.value)} style={{ minHeight: 260 }} />
              <div className="ds-row">
                <button type="button" className="ds-btn primary" disabled={busy !== null || !text.trim()} onClick={() => void act("save_edit", { base_id: selected.id, body: text }).then(() => setEditing(false))}>Save as new version</button>
                <button type="button" className="ds-btn ghost" onClick={() => setEditing(false)}>Cancel</button>
              </div>
            </div>
          ) : diff && showDiff ? (
            <div className="ds-diff">
              {diff.map((part, index) => part.kind === "same" ? <span key={index}>{part.text}</span> : part.kind === "del" ? <del key={index}>{part.text}</del> : <ins key={index}>{part.text}</ins>)}
            </div>
          ) : (
            <div className="ds-article">
              <h2>{selected.data.headline}</h2>
              <ReactMarkdown>{selected.data.body ?? ""}</ReactMarkdown>
            </div>
          )}
          {selected.status === "failed" && <Banner kind="error">{selected.error}</Banner>}
        </div>
        <div className="ds-stack">
          <div className="ds-card tight">
            <h3>Fact check of {selected.label}</h3>
            {writing && selected.data.body ? <p className="ds-muted ds-small"><Spinner /> {selected.data.judge ?? "The judge model"} is checking claims…</p> : null}
            <Checks checks={selected.checks} />
            <div style={{ marginTop: 8 }}><ClaimsTable version={selected} sourceTitles={sourceTitles} /></div>
          </div>
          {open && selected.status === "ready" && (
            <div className="ds-card tight">
              <h3>Revise {selected.label}</h3>
              <textarea aria-label="Revision note" value={note} onChange={(e) => setNote(e.target.value)} style={{ minHeight: 70 }} placeholder="What should change? Flagged claims are fixed automatically; leave empty to only fix those." />
              <div className="ds-row" style={{ marginTop: 8 }}>
                <button type="button" className="ds-btn primary" disabled={busy !== null || (!note.trim() && !selected.metrics.unsupported && !selected.metrics.partly)}
                  onClick={() => void act("revise", { base_id: selected.id, note }).then(() => setNote(""))}>
                  {busy === "revise" ? <Spinner /> : <Sparkles size={14} aria-hidden="true" />} Make v{versions.length + 1}
                </button>
                <button type="button" className="ds-btn" onClick={() => { setText(selected.data.body ?? ""); setEditing(true); }}><Pencil size={13} aria-hidden="true" /> Edit it myself</button>
              </div>
              <p className="ds-tiny ds-muted" style={{ marginTop: 6 }}>Every version is kept and checked. Approve the one you want with “Approve & continue”: it approves the version you are viewing.</p>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

export default function ArticleRun(props: RunViewProps) {
  const { detail, act } = props;
  const steps = Object.fromEntries(detail.steps.map((step) => [step.key, step]));
  const sources = detail.run.brief.sources ?? [];
  const final = detail.artifacts.find((a) => a.kind === "final" && a.status !== "superseded");
  const [copied, setCopied] = useState(false);
  return (
    <div className="ds-stack">
      <section className="ds-card tight">
        <details>
          <summary className="ds-small" style={{ cursor: "pointer" }}><b>Brief and {sources.length} source{sources.length === 1 ? "" : "s"}</b> · {detail.run.brief.brief}</summary>
          <ol className="ds-small" style={{ marginTop: 8, paddingLeft: 20 }}>
            {sources.map((source, index) => (
              <li key={index} style={{ marginBottom: 6 }}>
                <b>{source.title}</b>{source.published ? ` · ${source.published}` : ""}{source.url ? <> · <a href={source.url} target="_blank" rel="noreferrer">link</a></> : null}
                <div className="ds-muted">{source.text.slice(0, 280)}…</div>
              </li>
            ))}
          </ol>
        </details>
      </section>
      <section id="step-outline" className="ds-card">
        <h3>Outline {steps.outline?.status === "waiting" ? "✋" : ""}</h3>
        {steps.outline?.status === "running" && !steps.outline.data.points && <p className="ds-muted"><Spinner /> Planning the outline…</p>}
        {steps.outline?.status === "waiting" ? <OutlineEditor {...props} /> : steps.outline?.data.points ? (
          <details>
            <summary className="ds-small ds-dim" style={{ cursor: "pointer" }}>“{steps.outline.data.headline}” · {steps.outline.data.points.length} points · approved{steps.outline.data.edited ? " with your edits" : ""}</summary>
            <ol className="ds-small" style={{ marginTop: 8, paddingLeft: 20 }}>{steps.outline.data.points.map((point, index) => <li key={index}>{point.text} <span className="ds-muted">{point.sources.map((s) => `[${s}]`).join("")}</span></li>)}</ol>
          </details>
        ) : null}
      </section>
      {steps.draft && steps.draft.status !== "pending" && (
        <section id="step-draft" className="ds-card">
          <h3>Draft → check → revise {steps.draft.status === "waiting" ? "✋" : ""}</h3>
          <DraftStep {...props} />
        </section>
      )}
      {final && (
        <section id="step-finish" className="ds-card hl">
          <div className="ds-row between" style={{ marginBottom: 8 }}>
            <h3 style={{ margin: 0 }}>Approved: {String(final.data.source_label ?? "")}</h3>
            <div className="ds-row">
              {final.data.markdown && <button type="button" className="ds-btn sm" onClick={() => { void navigator.clipboard.writeText(final.data.markdown ?? ""); setCopied(true); window.setTimeout(() => setCopied(false), 1500); }}><Copy size={13} aria-hidden="true" /> {copied ? "Copied" : "Copy markdown"}</button>}
              {final.media_sha && <a className="ds-btn sm" href={mediaUrl(final.media_sha, `${detail.run.title.replace(/[^\w .-]+/g, "")}.md`)}><Download size={13} aria-hidden="true" /> Download .md</a>}
            </div>
          </div>
          {final.status === "ready" ? (
            <div className="ds-grid2" style={{ gridTemplateColumns: "minmax(0, 1.3fr) minmax(0, 1fr)", alignItems: "start" }}>
              <div className="ds-article">
                <h2>{final.data.headline}</h2>
                <ReactMarkdown>{final.data.body ?? ""}</ReactMarkdown>
                {final.data.label && <p className="ds-muted" style={{ fontStyle: "italic" }}>{final.data.label}</p>}
              </div>
              <div className="ds-stack">
                <Checks checks={final.checks} />
                {steps.draft?.status === "done" && <button type="button" className="ds-btn sm" style={{ justifySelf: "start" }} onClick={() => void act("reopen", { step: "draft" })}>Back to drafts</button>}
              </div>
            </div>
          ) : <p className="ds-muted"><Spinner /> Finishing…</p>}
        </section>
      )}
    </div>
  );
}
