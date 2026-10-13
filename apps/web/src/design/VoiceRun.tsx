import { useEffect, useMemo, useState } from "react";
import { Download, Mic, Plus, Sparkles, Trash2 } from "lucide-react";
import { designApi, mediaUrl, useLoad, type Artifact, type ScriptLine } from "./api";
import type { RunViewProps } from "./RunPage";
import { Banner, Checks, ReviewTag, Spinner } from "./ui";

function ScriptEditor({ detail, act, busy, setApproveExtra, styles }: RunViewProps & { styles: Record<string, string[]> }) {
  const step = detail.steps.find((s) => s.key === "script")!;
  const speakers = detail.run.brief.speakers ?? [];
  const original = step.data.lines ?? [];
  const [lines, setLines] = useState<ScriptLine[]>(original);
  const [note, setNote] = useState("");
  const dirty = JSON.stringify(lines) !== JSON.stringify(original);
  useEffect(() => setLines(step.data.lines ?? []), [step.data.lines]);
  useEffect(() => {
    setApproveExtra(dirty ? () => ({ lines }) : null);
    return () => setApproveExtra(null);
  }, [dirty, lines, setApproveExtra]);
  const words = lines.reduce((total, line) => total + line.text.split(/\s+/).filter(Boolean).length, 0);
  const patch = (index: number, value: Partial<ScriptLine>) => setLines(lines.map((line, i) => (i === index ? { ...line, ...value } : line)));
  const nextId = () => {
    let n = lines.length + 1;
    while (lines.some((line) => line.id === `l${n}`)) n += 1;
    return `l${n}`;
  };
  return (
    <div className="ds-stack" style={{ gap: 6 }}>
      <p className="ds-small ds-muted">{lines.length} lines · {words} words · about {Math.round((words * 60) / 150)} s at the voices' pace (target {detail.run.brief.target_seconds} s)</p>
      {lines.map((line, index) => {
        const voice = speakers.find((s) => s.name === line.speaker)?.voice ?? "";
        const options = styles[voice] ?? [];
        return (
          <div key={line.id} className="ds-script-row">
            <select aria-label={`Line ${index + 1} speaker`} value={line.speaker} onChange={(e) => patch(index, { speaker: e.target.value, style: "" })}>
              {speakers.map((speaker) => <option key={speaker.name}>{speaker.name}</option>)}
            </select>
            <textarea aria-label={`Line ${index + 1} text`} value={line.text} onChange={(e) => patch(index, { text: e.target.value })} />
            <select aria-label={`Line ${index + 1} style`} value={line.style} onChange={(e) => patch(index, { style: e.target.value })} disabled={!options.length}>
              <option value="">{options.length ? "default style" : "no styles"}</option>
              {options.map((style) => <option key={style}>{style}</option>)}
            </select>
            <button type="button" className="ds-btn sm ghost" aria-label={`Remove line ${index + 1}`} disabled={lines.length <= 1} onClick={() => setLines(lines.filter((_, i) => i !== index))}><Trash2 size={13} aria-hidden="true" /></button>
          </div>
        );
      })}
      <div className="ds-row between">
        <div className="ds-row">
          <button type="button" className="ds-btn sm" onClick={() => setLines([...lines, { id: nextId(), speaker: speakers[0]?.name ?? "", text: "", style: "" }])}><Plus size={13} aria-hidden="true" /> Add line</button>
          <button type="button" className="ds-btn sm" disabled={!dirty || busy !== null || lines.some((line) => !line.text.trim())} onClick={() => void act("update_script", { lines })}>Save edits</button>
          {dirty && <button type="button" className="ds-btn sm ghost" onClick={() => setLines(original)}>Discard</button>}
        </div>
        <span className="ds-chip model">{step.data.model} · draft {step.data.drafts}</span>
      </div>
      <form className="ds-row" onSubmit={(event) => { event.preventDefault(); if (note.trim()) void act("redraft_script", { note }).then(() => setNote("")); }}>
        <input aria-label="Redraft note" value={note} onChange={(e) => setNote(e.target.value)} placeholder="Redraft with a note, e.g. “shorter, and let Ethan ask a question”" style={{ flex: 1 }} />
        <button type="submit" className="ds-btn" disabled={!note.trim() || busy !== null}>{busy === "redraft_script" ? <Spinner /> : <Sparkles size={14} aria-hidden="true" />} Redraft</button>
      </form>
    </div>
  );
}

function Heard({ take }: { take: Artifact }) {
  if (take.metrics.transcript == null) return null;
  const diffs = take.metrics.diffs ?? [];
  return (
    <div className="heard">
      heard: “{take.metrics.transcript}”
      {diffs.length > 0 && (
        <div style={{ marginTop: 2 }}>
          {diffs.map((diff, index) => (
            <span key={index} style={{ marginRight: 8 }}>script <mark>{diff.script || "∅"}</mark> → heard <mark>{diff.heard || "∅"}</mark></span>
          ))}
        </div>
      )}
    </div>
  );
}

function LineRow({ line, takes, open, act, busy, styles }: { line: ScriptLine; takes: Artifact[]; open: boolean; act: RunViewProps["act"]; busy: string | null; styles: string[] }) {
  const kept = takes.find((take) => take.verdict === "keep") ?? takes[takes.length - 1];
  const [editing, setEditing] = useState(false);
  const [text, setText] = useState(line.text);
  const [style, setStyle] = useState(line.style);
  useEffect(() => { setText(line.text); setStyle(line.style); }, [line.text, line.style]);
  const check = kept?.checks.find((c) => c.key === "listen-back");
  const active = takes.some((take) => take.status === "queued" || take.status === "running");
  return (
    <div className="ds-line">
      <div className="spk">
        <b>{line.speaker}</b>
        <small>{kept?.params.voice?.split(":")[0].split("-").pop()}{line.style ? ` · ${line.style}` : ""}</small>
      </div>
      <div style={{ minWidth: 0 }}>
        {editing ? (
          <div className="ds-stack" style={{ gap: 6 }}>
            <textarea aria-label="Line text" value={text} onChange={(e) => setText(e.target.value)} style={{ minHeight: 52 }} />
            <div className="ds-row">
              <select aria-label="Style" value={style} onChange={(e) => setStyle(e.target.value)} disabled={!styles.length} style={{ width: "auto" }}>
                <option value="">{styles.length ? "default style" : "no styles"}</option>
                {styles.map((item) => <option key={item}>{item}</option>)}
              </select>
              <button type="button" className="ds-btn sm primary" disabled={busy !== null || !text.trim()} onClick={() => void act("regenerate_line", { line_id: line.id, text, style }).then(() => setEditing(false))}>Re-record</button>
              <button type="button" className="ds-btn sm ghost" onClick={() => setEditing(false)}>Cancel</button>
            </div>
          </div>
        ) : (
          <>
            <div>{line.text}</div>
            {kept && <Heard take={kept} />}
            {kept?.error && <div className="ds-tiny" style={{ color: "var(--red)" }}>{kept.error}</div>}
          </>
        )}
        <div className="ds-line-tools">
          {kept?.status === "ready" && kept.media_sha ? <audio controls preload="none" src={mediaUrl(kept.media_sha)} aria-label={`Line ${line.id.slice(1)} audio`} />
            : !active && <span className="ds-small ds-muted">{kept?.status ?? "not recorded"}</span>}
          {active && <span className="ds-chip info"><Spinner size={11} /> recording…</span>}
          {takes.filter((take) => take.status === "ready").length > 1 && (
            <select aria-label="Choose take" value={kept?.id} onChange={(e) => void act("decide", { artifact_id: e.target.value, verdict: "keep" })} style={{ width: "auto", fontSize: 12, padding: "4px 6px" }} disabled={!open}>
              {takes.filter((take) => take.status === "ready").map((take) => <option key={take.id} value={take.id}>{take.label}{take.verdict === "keep" ? " (kept)" : ""}</option>)}
            </select>
          )}
          {check && <span className={`ds-chip ${check.state === "ok" ? "ok" : check.state === "info" ? "" : check.state === "warn" ? "warn" : "bad"}`} title={check.basis}>{check.state === "ok" ? "✓ matches the script" : check.label.replace("Listen-back: ", "")}</span>}
          {open && !editing && (
            <>
              <button type="button" className="ds-btn sm" disabled={busy !== null} onClick={() => void act("regenerate_line", { line_id: line.id })} title="Record this line again"><Mic size={12} aria-hidden="true" /> Again</button>
              <button type="button" className="ds-btn sm ghost" onClick={() => setEditing(true)}>Edit</button>
            </>
          )}
        </div>
      </div>
    </div>
  );
}

export default function VoiceRun(props: RunViewProps) {
  const { detail, act, busy } = props;
  const steps = Object.fromEntries(detail.steps.map((step) => [step.key, step]));
  const voices = useLoad(() => designApi.voices(detail.run.brief.locale), detail.run.brief.locale ?? "");
  const styles = useMemo(() => Object.fromEntries((voices.data ?? []).map((voice) => [voice.name, voice.styles])), [voices.data]);
  const lines = steps.script?.data.lines ?? [];
  const recordings = detail.artifacts.filter((a) => a.kind === "line" && a.status !== "superseded");
  const mix = detail.artifacts.find((a) => a.kind === "final" && a.status !== "superseded");
  const linesOpen = steps.lines?.status === "running" || steps.lines?.status === "waiting";
  const speakers = detail.run.brief.speakers ?? [];
  const errors = recordings.filter((r) => r.verdict === "keep").reduce((total, r) => total + (r.metrics.word_errors ?? 0), 0);

  return (
    <div className="ds-stack">
      <section id="step-script" className="ds-card">
        <h3>Brief → script {steps.script?.status === "waiting" && <ReviewTag waiting />}</h3>
        <p className="ds-small ds-muted" style={{ marginBottom: 8 }}>
          <b>Cast:</b> {speakers.map((s) => `${s.name} (${s.voice.split(":")[0]}${s.style ? `, ${s.style}` : ""})`).join(" · ")} · {detail.run.brief.locale}
        </p>
        {steps.script?.status === "running" && !lines.length && <p className="ds-muted"><Spinner /> The text model is writing the script…</p>}
        {steps.script?.status === "waiting" ? <ScriptEditor {...props} styles={styles} /> : lines.length ? (
          <details>
            <summary className="ds-small ds-dim" style={{ cursor: "pointer" }}>{lines.length} lines · approved{steps.script?.data.edited ? " with your edits" : ""}</summary>
            <ol style={{ marginTop: 8, paddingLeft: 18 }} className="ds-small">{lines.map((line) => <li key={line.id}><b>{line.speaker}:</b> {line.text}</li>)}</ol>
          </details>
        ) : null}
      </section>
      {steps.lines && steps.lines.status !== "pending" && (
        <section id="step-lines" className="ds-card">
          <div className="ds-row between" style={{ marginBottom: 6 }}>
            <h3 style={{ margin: 0 }}>Lines · synthesize + listen-back {steps.lines.status === "waiting" && <ReviewTag waiting />}</h3>
            <span className={`ds-chip ${errors ? "warn" : "ok"}`}>{errors} word difference{errors === 1 ? "" : "s"} in kept takes</span>
          </div>
          <p className="ds-small ds-muted">Each line is its own call, so one bad line can be redone alone. The listen-back check transcribes each line and compares it with the script word by word; it flags, you decide.</p>
          <div className="ds-lines">
            {lines.map((line) => {
              const voice = speakers.find((s) => s.name === line.speaker)?.voice ?? "";
              return <LineRow key={line.id} line={line} takes={recordings.filter((r) => r.grp === line.id)} open={linesOpen} act={act} busy={busy} styles={styles[voice] ?? []} />;
            })}
          </div>
        </section>
      )}
      {mix && (
        <section id="step-mix" className="ds-card hl">
          <div className="ds-row between" style={{ marginBottom: 8 }}>
            <h3 style={{ margin: 0 }}>Final mix</h3>
            {mix.media_sha && <a className="ds-btn sm" href={mediaUrl(mix.media_sha, `${detail.run.title.replace(/[^\w .-]+/g, "")}.mp3`)}><Download size={13} aria-hidden="true" /> Download MP3</a>}
          </div>
          {mix.status === "ready" && mix.media_sha ? (
            <div className="ds-grid2" style={{ alignItems: "start" }}>
              <div className="ds-stack">
                <audio controls src={mediaUrl(mix.media_sha)} preload="metadata" />
                <dl className="ds-kv">
                  <dt>Length</dt><dd>{mix.metrics.duration?.toFixed(1)} s</dd>
                  <dt>Voices</dt><dd className="ds-mono ds-tiny">{(mix.data.voices ?? []).join(" · ")}</dd>
                </dl>
                <Checks checks={mix.checks} />
                {steps.lines?.status === "done" && <button type="button" className="ds-btn sm" style={{ justifySelf: "start" }} onClick={() => void act("reopen", { step: "lines" })}>Back to lines</button>}
              </div>
              <div>
                <h3>Transcript</h3>
                <div className="ds-promptbox ds-small">{(mix.data.transcript ?? []).map((row, index) => <div key={index}><b>{row.speaker}:</b> {row.text}</div>)}</div>
              </div>
            </div>
          ) : mix.status === "failed" ? <Banner kind="error">{mix.error}</Banner> : <p className="ds-muted"><Spinner /> Mixing…</p>}
        </section>
      )}
    </div>
  );
}
