import { useEffect, useMemo, useState } from "react";
import { Download, Plus, RefreshCw, Sparkles } from "lucide-react";
import { mediaUrl, type Artifact, type Shot } from "./api";
import type { RunViewProps } from "./RunPage";
import { Banner, Checks, Dialog, MediaPreview, ReviewTag, Spinner } from "./ui";

function ShotListEditor({ detail, act, busy, setApproveExtra }: RunViewProps) {
  const step = detail.steps.find((s) => s.key === "shotlist")!;
  const original = step.data.shots ?? [];
  const [shots, setShots] = useState<Shot[]>(original);
  const [note, setNote] = useState("");
  const hasRefs = detail.artifacts.some((a) => a.kind === "reference");
  const helper = detail.run.brief.prompt_helper !== false;
  const dirty = JSON.stringify(shots) !== JSON.stringify(original);

  useEffect(() => setShots(step.data.shots ?? []), [step.data.shots]);
  useEffect(() => {
    setApproveExtra(dirty ? () => ({ shots }) : null);
    return () => setApproveExtra(null);
  }, [dirty, shots, setApproveExtra]);

  const patch = (index: number, value: Partial<Shot>) => setShots((current) => current.map((shot, i) => (i === index ? { ...shot, ...value } : shot)));
  return (
    <div className="ds-stack">
      {step.data.notes && <p className="ds-dim ds-small">{helper && <b>Story arc: </b>}{step.data.notes}</p>}
      {shots.map((shot, index) => (
        <div key={shot.id} className="ds-shot-edit">
          <div className="head">
            <div className="ds-row" style={{ flex: 1, minWidth: 220 }}>
              <b className="ds-mono">{index + 1}</b>
              <input aria-label={`Shot ${index + 1} title`} value={shot.title} onChange={(e) => patch(index, { title: e.target.value })} style={{ maxWidth: 320 }} />
            </div>
            <div className="ds-row">
              <select aria-label={`Shot ${index + 1} subject`} value={shot.subject} onChange={(e) => patch(index, { subject: e.target.value as Shot["subject"], mode: e.target.value === "people" ? "t2v" : shot.mode })} style={{ width: "auto" }}>
                <option value="product">product</option><option value="people">people</option><option value="scene">scene</option>
              </select>
              <select aria-label={`Shot ${index + 1} source`} value={shot.mode} disabled={!hasRefs || shot.subject === "people"} onChange={(e) => patch(index, { mode: e.target.value as Shot["mode"] })} style={{ width: "auto" }}>
                <option value="i2v">keyframe → video</option><option value="t2v">text → video</option>
              </select>
            </div>
          </div>
          <textarea aria-label={`Shot ${index + 1} prompt`} value={shot.prompt} onChange={(e) => patch(index, { prompt: e.target.value })} />
          {shot.mode === "i2v" && (
            <label style={{ margin: 0 }}>Keyframe instruction (image edit from your references)
              <textarea value={shot.keyframe_prompt} onChange={(e) => patch(index, { keyframe_prompt: e.target.value })} style={{ minHeight: 52, marginTop: 4 }} />
            </label>
          )}
          <div className="ds-row">
            <span className="ds-tiny ds-muted">Sound</span>
            <input aria-label={`Shot ${index + 1} sound`} value={shot.sound} onChange={(e) => patch(index, { sound: e.target.value })} style={{ flex: 1 }} />
          </div>
        </div>
      ))}
      <div className="ds-row between">
        <div className="ds-row">
          <button type="button" className="ds-btn sm" disabled={!dirty || busy !== null} onClick={() => void act("update_shots", { shots })}>Save edits</button>
          {dirty && <button type="button" className="ds-btn sm ghost" onClick={() => setShots(original)}>Discard</button>}
          {dirty && <span className="ds-tiny ds-muted">Unsaved edits are included when you approve.</span>}
        </div>
        <span className="ds-chip model">{helper ? `${step.data.model} · draft ${step.data.drafts}` : "no text model · your lines as written"}</span>
      </div>
      {helper && (
        <form className="ds-row" onSubmit={(event) => { event.preventDefault(); if (note.trim()) void act("redraft_shots", { note }).then(() => setNote("")); }}>
          <input aria-label="Redraft note" value={note} onChange={(e) => setNote(e.target.value)} placeholder="Redraft with a note, e.g. “make shot 2 a drone shot; more motion in shot 4”" style={{ flex: 1 }} />
          <button type="submit" className="ds-btn" disabled={!note.trim() || busy !== null}>{busy === "redraft_shots" ? <Spinner /> : <Sparkles size={14} aria-hidden="true" />} Redraft</button>
        </form>
      )}
    </div>
  );
}

function ShotListReadOnly({ shots }: { shots: Shot[] }) {
  return (
    <ol className="ds-stack" style={{ paddingLeft: 18, margin: 0, gap: 8 }}>
      {shots.map((shot) => (
        <li key={shot.id} className="ds-small">
          <b>{shot.title}</b> <span className="ds-chip">{shot.mode === "i2v" ? "keyframe → video" : "text → video"}</span>
          <div className="ds-muted">{shot.prompt}</div>
        </li>
      ))}
    </ol>
  );
}

function TakeCard({ take, act, busy, openReview, onRemix, portrait, open }: { take: Artifact; act: RunViewProps["act"]; busy: string | null; openReview: (id: string) => void; onRemix: (take: Artifact) => void; portrait: boolean; open: boolean }) {
  const motion = take.metrics.motion;
  const verdictClass = take.verdict === "keep" ? " keep" : take.verdict === "regenerate" ? " regenerate" : "";
  const ready = take.status === "ready";
  return (
    <div className={`ds-take${verdictClass}`}>
      <button type="button" className="ds-media-btn" style={{ cursor: ready || take.status === "failed" || take.status === "blocked" ? "pointer" : "default" }} onClick={() => take.status !== "queued" && take.status !== "running" && openReview(take.id)} aria-label={`Review ${take.label}`}>
        <MediaPreview artifact={take} portrait={portrait} />
      </button>
      <div className="ds-meta">
        <div className="ds-row between">
          <b className="ds-mono">{take.label}</b>
          <span className="ds-muted">{take.gen_seconds ? `${Math.round(take.gen_seconds)} s` : take.params.mode === "remix" ? `remix of ${take.params.remix_of_label}` : ""}</span>
        </div>
        {ready && motion != null && <span className={`ds-chip ${motion < 0.6 ? "warn" : "ok"}`} style={{ justifySelf: "start" }}>motion {motion.toFixed(1)}</span>}
        {(take.status === "failed" || take.status === "blocked") && <span className="ds-tiny" style={{ color: "var(--red)" }}>{take.error}</span>}
      </div>
      <div className="ds-acts">
        {ready && !open ? (
          take.verdict ? <span className={`ds-chip ${take.verdict === "keep" ? "ok" : take.verdict === "regenerate" ? "warn" : ""}`}>{take.verdict === "keep" ? "kept" : take.verdict}</span> : null
        ) : ready ? (
          <>
            <button type="button" className={`ds-btn sm${take.verdict === "keep" ? " good" : ""}`} disabled={busy !== null} onClick={() => void act("decide", { artifact_id: take.id, verdict: take.verdict === "keep" ? null : "keep" })}>Keep</button>
            <button type="button" className={`ds-btn sm${take.verdict === "regenerate" ? " warn" : ""}`} disabled={busy !== null} onClick={() => void act("decide", { artifact_id: take.id, verdict: "regenerate" }).then(() => act("regenerate_take", { shot_id: take.grp }))}>Regen</button>
            <button type="button" className="ds-btn sm" disabled={busy !== null || !take.vendor_job_id} onClick={() => onRemix(take)}>Remix</button>
          </>
        ) : (take.status === "failed" || take.status === "blocked") && open ? (
          <button type="button" className="ds-btn sm" disabled={busy !== null} onClick={() => openReview(take.id)}>Reword & retry</button>
        ) : null}
      </div>
    </div>
  );
}

export default function VideoRun(props: RunViewProps) {
  const { detail, act, busy, openReview } = props;
  const steps = Object.fromEntries(detail.steps.map((step) => [step.key, step]));
  const shots = steps.shotlist?.data.shots ?? [];
  const items = detail.artifacts.filter((a) => a.status !== "superseded");
  const keyframes = items.filter((a) => a.kind === "keyframe");
  const takes = items.filter((a) => a.kind === "take");
  const final = items.find((a) => a.kind === "final");
  const report = items.find((a) => a.kind === "report");
  const voiceover = items.find((a) => a.kind === "voiceover");
  const [remix, setRemix] = useState<Artifact | null>(null);
  const [remixNote, setRemixNote] = useState("");
  const [kfNote, setKfNote] = useState<Record<string, string>>({});
  const vertical = detail.run.brief.size === "720x1280";
  const takesOpen = steps.takes && (steps.takes.status === "running" || steps.takes.status === "waiting");
  const kfOpen = steps.keyframes && (steps.keyframes.status === "running" || steps.keyframes.status === "waiting");

  const counts = useMemo(() => ({
    kept: takes.filter((t) => t.verdict === "keep").length,
    regen: takes.filter((t) => t.verdict === "regenerate").length,
    undecided: takes.filter((t) => t.status === "ready" && !t.verdict).length,
    active: takes.filter((t) => t.status === "queued" || t.status === "running").length,
  }), [takes]);

  return (
    <div className="ds-stack">
      <section id="step-shotlist" className="ds-card">
        <h3>Shot list {steps.shotlist?.status === "waiting" && <ReviewTag waiting />}</h3>
        {steps.shotlist?.status === "running" && !shots.length && <p className="ds-muted"><Spinner /> The text model is writing the shot list…</p>}
        {steps.shotlist?.status === "waiting" ? <ShotListEditor {...props} /> : shots.length ? (
          <details open={!takes.length}>
            <summary className="ds-small ds-dim" style={{ cursor: "pointer" }}>{shots.length} shots · approved{steps.shotlist?.data.edited ? " with your edits" : ""}</summary>
            <div style={{ marginTop: 10 }}><ShotListReadOnly shots={shots} /></div>
          </details>
        ) : null}
      </section>

      {steps.keyframes && steps.keyframes.status !== "pending" && steps.keyframes.status !== "skipped" && (
        <section id="step-keyframes" className="ds-card">
          <h3>Keyframes for product shots {steps.keyframes.status === "waiting" && <ReviewTag waiting />}</h3>
          <p className="ds-small ds-muted" style={{ marginBottom: 10 }}>Opening frames edited from your reference images with the image model. The kept keyframe becomes the first frame of every take for that shot.</p>
          {shots.filter((shot) => shot.mode === "i2v").map((shot) => {
            const frames = keyframes.filter((k) => k.grp === shot.id);
            return (
              <div key={shot.id} className="ds-shot">
                <div className="ds-shot-info">
                  <b>{shot.id.slice(1)} · {shot.title}</b>
                  <p>{shot.keyframe_prompt}</p>
                </div>
                <div className="ds-stack" style={{ gap: 8 }}>
                  <div className="ds-takes">
                    {frames.map((frame) => (
                      <div key={frame.id} className={`ds-take${frame.verdict === "keep" ? " keep" : ""}`}>
                        <button type="button" className="ds-media-btn" onClick={() => frame.status === "ready" || frame.status === "blocked" || frame.status === "failed" ? openReview(frame.id) : undefined} aria-label={`Open ${frame.label}`}>
                          <MediaPreview artifact={frame} portrait={vertical} />
                        </button>
                        <div className="ds-meta"><div className="ds-row between"><b className="ds-mono">{frame.label}</b><span className="ds-muted">{frame.gen_seconds ? `${Math.round(frame.gen_seconds)} s` : ""}</span></div>
                          {frame.error && <span className="ds-tiny" style={{ color: "var(--red)" }}>{frame.error}</span>}
                        </div>
                        <div className="ds-acts">
                          {frame.status === "ready" && <button type="button" className={`ds-btn sm${frame.verdict === "keep" ? " good" : ""}`} disabled={busy !== null || !kfOpen} onClick={() => void act("decide", { artifact_id: frame.id, verdict: "keep" })}>{frame.verdict === "keep" ? "Kept" : "Keep"}</button>}
                          {(frame.status === "failed" || frame.status === "blocked") && kfOpen && <button type="button" className="ds-btn sm" onClick={() => openReview(frame.id)}>Reword & retry</button>}
                        </div>
                      </div>
                    ))}
                  </div>
                  {kfOpen && (
                    <form className="ds-row" onSubmit={(event) => { event.preventDefault(); void act("regenerate_keyframe", { shot_id: shot.id, note: kfNote[shot.id] ?? "" }).then(() => setKfNote({ ...kfNote, [shot.id]: "" })); }}>
                      <input aria-label={`Change for keyframe ${shot.id}`} value={kfNote[shot.id] ?? ""} onChange={(e) => setKfNote({ ...kfNote, [shot.id]: e.target.value })} placeholder="What should change? (optional)" style={{ flex: 1 }} />
                      <button type="submit" className="ds-btn sm" disabled={busy !== null}><RefreshCw size={13} aria-hidden="true" /> New keyframe</button>
                    </form>
                  )}
                </div>
              </div>
            );
          })}
        </section>
      )}

      {steps.takes && steps.takes.status !== "pending" && (
        <section id="step-takes" className="ds-card">
          <div className="ds-row between" style={{ marginBottom: 8 }}>
            <h3 style={{ margin: 0 }}>Takes {steps.takes.status === "waiting" && <ReviewTag waiting />}</h3>
            <div className="ds-row">
              <span className="ds-chip ok">Kept {counts.kept}</span>
              <span className="ds-chip warn">Regenerate {counts.regen}</span>
              <span className="ds-chip">Undecided {counts.undecided}</span>
              {counts.active > 0 && <span className="ds-chip info"><Spinner size={11} /> {counts.active} generating</span>}
            </div>
          </div>
          <p className="ds-small ds-muted" style={{ marginBottom: 6 }}>Click a take to review it full size. Keep one per shot; checks flag, you decide.</p>
          {shots.map((shot) => {
            const shotTakes = takes.filter((t) => t.grp === shot.id);
            return (
              <div key={shot.id} className="ds-shot">
                <div className="ds-shot-info">
                  <b>{shot.id.slice(1)} · {shot.title}</b>
                  <p>{shot.mode === "i2v" ? "keyframe → video" : "text → video"}{shot.subject === "people" ? " (people)" : ""}</p>
                  <p>{shot.prompt.slice(0, 140)}{shot.prompt.length > 140 ? "…" : ""}</p>
                  {takesOpen && (
                    <button type="button" className="ds-btn sm" style={{ marginTop: 8 }} disabled={busy !== null} onClick={() => void act("regenerate_take", { shot_id: shot.id })}>
                      <Plus size={13} aria-hidden="true" /> Another take
                    </button>
                  )}
                </div>
                <div className="ds-takes" style={vertical ? { gridTemplateColumns: "repeat(auto-fill, minmax(130px, 1fr))" } : undefined}>
                  {shotTakes.map((take) => <TakeCard key={take.id} take={take} act={act} busy={busy} openReview={openReview} onRemix={(t) => { setRemix(t); setRemixNote(""); }} portrait={vertical} open={Boolean(takesOpen)} />)}
                </div>
              </div>
            );
          })}
        </section>
      )}

      {voiceover && (
        <section id="step-voiceover" className="ds-card">
          <h3>Voiceover</h3>
          {voiceover.media_sha ? <audio controls src={mediaUrl(voiceover.media_sha)} preload="none" /> : <MediaPreview artifact={voiceover} />}
          <p className="ds-small ds-muted" style={{ marginTop: 6 }}>{voiceover.prompt}</p>
        </section>
      )}

      {final && (
        <section id="step-assemble" className="ds-card hl">
          <div className="ds-row between" style={{ marginBottom: 8 }}>
            <h3 style={{ margin: 0 }}>Final cut</h3>
            {final.media_sha && <a className="ds-btn sm" href={mediaUrl(final.media_sha, `${detail.run.title.replace(/[^\w .-]+/g, "")}.mp4`)}><Download size={13} aria-hidden="true" /> Download MP4</a>}
          </div>
          {final.status === "ready" && final.media_sha ? (
            <div className="ds-review" style={{ gridTemplateColumns: "minmax(0, 1.6fr) minmax(260px, 1fr)" }}>
              <div className="ds-player"><video src={mediaUrl(final.media_sha)} poster={final.thumb_sha ? mediaUrl(final.thumb_sha) : undefined} controls preload="metadata" playsInline /></div>
              <div className="ds-stack">
                <dl className="ds-kv">
                  <dt>Length</dt><dd>{final.metrics.duration?.toFixed(1)} s</dd>
                  <dt>Edit list</dt><dd className="ds-mono ds-small">{(final.params.edit_labels ?? []).join(" · ")}</dd>
                </dl>
                <Checks checks={[...final.checks, ...(report?.checks ?? [])]} />
                {steps.takes?.status === "done" && (
                  <button type="button" className="ds-btn sm" style={{ justifySelf: "start" }} disabled={busy !== null} onClick={() => void act("reopen", { step: "takes" })}>Back to takes (re-cut)</button>
                )}
              </div>
            </div>
          ) : <MediaPreview artifact={final} />}
          {report?.status === "ready" && (
            <p className="ds-tiny ds-muted" style={{ marginTop: 8 }}>{String((report.data as { note?: string }).note ?? "")}</p>
          )}
        </section>
      )}

      {detail.run.status === "completed" && !final && <Banner kind="info">This run finished without an assembled cut.</Banner>}

      {remix && (
        <Dialog title={`Remix ${remix.label}`} onClose={() => setRemix(null)} actions={<>
          <button type="button" className="ds-btn ghost" onClick={() => setRemix(null)}>Cancel</button>
          <button type="button" className="ds-btn primary" disabled={!remixNote.trim()} onClick={() => { const target = remix; setRemix(null); void act("remix_take", { artifact_id: target.id, note: remixNote }); }}>Make the remix</button>
        </>}>
          <p style={{ marginBottom: 8 }}>A remix keeps the take and changes one thing. Describe only the change; the result appears as a new take next to this one.</p>
          <textarea aria-label="Remix change" value={remixNote} onChange={(e) => setRemixNote(e.target.value)} placeholder="e.g. slower camera, warmer light, the car stays in its lane" autoFocus />
        </Dialog>
      )}
    </div>
  );
}
