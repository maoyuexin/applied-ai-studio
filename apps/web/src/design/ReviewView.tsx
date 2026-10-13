import { useEffect, useMemo, useState } from "react";
import { ArrowLeft, ChevronLeft, ChevronRight, Download } from "lucide-react";
import { mediaUrl, type Artifact } from "./api";
import type { RunViewProps } from "./RunPage";
import { Banner, Checks, MediaPreview, Spinner } from "./ui";

function checklistFor(props: RunViewProps, artifact: Artifact): string[] {
  const { detail } = props;
  const hasRefs = detail.artifacts.some((a) => a.kind === "reference");
  if (detail.run.pipeline === "image") {
    const useCase = detail.run.brief.use_case ?? "hero";
    return detail.pipeline?.use_cases?.[useCase]?.checklist ?? ["Matches the brief?", "No real brand, logo or face?"];
  }
  if (artifact.kind === "keyframe") {
    return ["Same product as the design sheet?", "No real brand, logo, face or plate?", "Room for motion in the shot?"];
  }
  return [
    ...(hasRefs ? ["Same product as the design sheet?"] : []),
    "Does the action match the shot?",
    "No real brand, logo, face or plate?",
    "Sound fits? (listen, don't just look)",
  ];
}

export default function ReviewView(props: RunViewProps & { artifact: Artifact; onBack: () => void }) {
  const { detail, act, busy, artifact, onBack, openReview } = props;
  const [note, setNote] = useState(artifact.note ?? "");
  const [prompt, setPrompt] = useState(artifact.prompt ?? "");
  const [remixNote, setRemixNote] = useState("");
  const checklist = useMemo(() => checklistFor(props, artifact), [props, artifact]);
  const [ticks, setTicks] = useState<Record<string, boolean | null>>(artifact.checklist ?? {});
  useEffect(() => {
    setNote(artifact.note ?? "");
    setPrompt(artifact.prompt ?? "");
    setTicks(artifact.checklist ?? {});
  }, [artifact.id]); // eslint-disable-line react-hooks/exhaustive-deps

  const siblings = detail.artifacts.filter((a) => a.kind === artifact.kind && a.status !== "superseded");
  const index = siblings.findIndex((a) => a.id === artifact.id);
  const previous = index > 0 ? siblings[index - 1] : null;
  const next = index < siblings.length - 1 ? siblings[index + 1] : null;
  const step = detail.steps.find((s) => s.key === artifact.step_key);
  const open = step?.status === "running" || step?.status === "waiting";
  const shot = (detail.steps.find((s) => s.key === "shotlist")?.data.shots ?? []).find((s) => s.id === artifact.grp);
  const isVideo = artifact.media_type === "video/mp4";
  const parent = artifact.parent_id ? detail.artifacts.find((a) => a.id === artifact.parent_id) : null;
  const inputs = artifact.inputs.map((sha) => detail.artifacts.find((a) => a.media_sha === sha)).filter((a): a is Artifact => Boolean(a));

  useEffect(() => {
    const onKey = (event: KeyboardEvent) => {
      if ((event.target as HTMLElement).closest("input, textarea, select")) return;
      if (event.key === "ArrowLeft" && previous) openReview(previous.id);
      if (event.key === "ArrowRight" && next) openReview(next.id);
      if (event.key === "Escape") onBack();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [previous, next, openReview, onBack]);

  const decide = (verdict: string | null) => act("decide", { artifact_id: artifact.id, verdict, note, checklist: ticks });
  const cycle = (item: string) => setTicks((current) => ({ ...current, [item]: current[item] === true ? false : current[item] === false ? null : true }));

  return (
    <div className="ds-stack">
      <div className="ds-row between">
        <div className="ds-row">
          <button type="button" className="ds-btn" onClick={onBack}><ArrowLeft size={14} aria-hidden="true" /> Back to the run</button>
          <h2 style={{ margin: 0 }}>Review {artifact.label}</h2>
          {shot && <span className="ds-muted ds-small">shot {shot.id.slice(1)} · {shot.title}</span>}
        </div>
        <div className="ds-row">
          <button type="button" className="ds-btn sm" disabled={!previous} onClick={() => previous && openReview(previous.id)} aria-label="Previous"><ChevronLeft size={14} aria-hidden="true" /> {previous?.label}</button>
          <button type="button" className="ds-btn sm" disabled={!next} onClick={() => next && openReview(next.id)} aria-label="Next">{next?.label} <ChevronRight size={14} aria-hidden="true" /></button>
        </div>
      </div>
      <div className="ds-review">
        <div className="ds-stack">
          <div className="ds-player">
            {artifact.status === "ready" && artifact.media_sha ? (
              isVideo ? <video key={artifact.id} src={mediaUrl(artifact.media_sha)} poster={artifact.thumb_sha ? mediaUrl(artifact.thumb_sha) : undefined} controls autoPlay playsInline preload="auto" />
                : <img src={mediaUrl(artifact.media_sha)} alt={artifact.label ?? ""} />
            ) : <MediaPreview artifact={artifact} />}
          </div>
          <div className="ds-card tight">
            <h3>Prompt sent</h3>
            {open && (artifact.status === "failed" || artifact.status === "blocked" || artifact.status === "canceled") ? (
              <div className="ds-stack" style={{ gap: 8 }}>
                <Banner kind={artifact.status === "blocked" ? "warn" : "error"}>{artifact.error}</Banner>
                <textarea aria-label="Prompt" value={prompt} onChange={(e) => setPrompt(e.target.value)} style={{ minHeight: 120 }} />
                <div className="ds-row">
                  <button type="button" className="ds-btn primary" disabled={busy !== null || !prompt.trim()} onClick={() => void act("retry_artifact", { artifact_id: artifact.id, prompt })}>
                    {busy === "retry_artifact" ? <Spinner /> : null} Retry with this prompt
                  </button>
                  <span className="ds-tiny ds-muted">Filters sometimes block harmless wording; rewording is part of the job. The original prompt stays in the event log.</span>
                </div>
              </div>
            ) : (
              <div className="ds-promptbox">{artifact.prompt}</div>
            )}
            <div className="ds-row" style={{ marginTop: 8 }}>
              {inputs.map((input) => <span key={input.id} className="ds-chip">input: {input.label}{input.data.role ? ` (${input.data.role})` : ""}</span>)}
              {parent && <span className="ds-chip">from {parent.label}</span>}
              {artifact.deployment && <span className="ds-chip model">{artifact.deployment}{artifact.model_version ? ` · ${artifact.model_version}` : ""}</span>}
              {artifact.vendor_job_id && <span className="ds-chip model" title={artifact.vendor_job_id}>{artifact.vendor_job_id.slice(0, 18)}…</span>}
              {artifact.gen_seconds != null && <span className="ds-chip">{Math.round(artifact.gen_seconds)} s to generate</span>}
            </div>
          </div>
        </div>
        <div className="ds-card">
          <h3>Automatic checks</h3>
          <Checks checks={artifact.checks} />
          {artifact.status === "ready" && (
            <>
              <h3 style={{ marginTop: 16 }}>Your review</h3>
              <div className="ds-checks">
                {checklist.map((item) => (
                  <div className="ds-check" key={item}>
                    <button type="button" className={`box ${ticks[item] === true ? "ok" : ticks[item] === false ? "bad" : ""}`} onClick={() => cycle(item)} aria-label={`${item}: ${ticks[item] === true ? "yes" : ticks[item] === false ? "no" : "not checked"}`}>
                      {ticks[item] === true ? "✓" : ticks[item] === false ? "✗" : ""}
                    </button>
                    <div>{item}</div>
                  </div>
                ))}
              </div>
              <label htmlFor="review-note">Note (saved with the run)</label>
              <textarea id="review-note" value={note} onChange={(e) => setNote(e.target.value)} style={{ minHeight: 64 }} placeholder="What you saw, why you decided" />
              <div className="ds-row" style={{ marginTop: 10 }}>
                <button type="button" className={`ds-btn${artifact.verdict === "keep" ? " good" : ""}`} disabled={busy !== null || !open && artifact.kind !== "image"} onClick={() => void decide("keep")}>Keep</button>
                <button type="button" className={`ds-btn${artifact.verdict === "usable" ? " on" : ""}`} disabled={busy !== null} onClick={() => void decide("usable")}>Usable</button>
                {artifact.kind === "take" && (
                  <button type="button" className={`ds-btn${artifact.verdict === "regenerate" ? " warn" : ""}`} disabled={busy !== null || !open} onClick={() => void decide("regenerate").then(() => act("regenerate_take", { shot_id: artifact.grp }))}>Regenerate</button>
                )}
                {artifact.kind !== "take" && <button type="button" className={`ds-btn${artifact.verdict === "reject" ? " warn" : ""}`} disabled={busy !== null} onClick={() => void decide("reject")}>Reject</button>}
                <button type="button" className="ds-btn ghost" disabled={busy !== null} onClick={() => void decide(artifact.verdict)}>Save note</button>
              </div>
              {artifact.kind === "take" && open && artifact.vendor_job_id && (
                <form className="ds-stack" style={{ gap: 6, marginTop: 14 }} onSubmit={(event) => { event.preventDefault(); void act("remix_take", { artifact_id: artifact.id, note: remixNote }).then(() => setRemixNote("")); }}>
                  <label htmlFor="remix-note" style={{ margin: 0 }}>Remix with a note</label>
                  <div className="ds-row">
                    <input id="remix-note" value={remixNote} onChange={(e) => setRemixNote(e.target.value)} placeholder="Only the change, e.g. “the car stays in its lane”" style={{ flex: 1 }} />
                    <button type="submit" className="ds-btn" disabled={busy !== null || !remixNote.trim()}>Remix</button>
                  </div>
                </form>
              )}
              {artifact.media_sha && (
                <a className="ds-btn sm ghost" style={{ marginTop: 12 }} href={mediaUrl(artifact.media_sha, `${artifact.label ?? "item"}.${isVideo ? "mp4" : "png"}`)}><Download size={13} aria-hidden="true" /> Download original</a>
              )}
            </>
          )}
          {artifact.verdict && <p className="ds-tiny ds-muted" style={{ marginTop: 10 }}>Current verdict: <b>{artifact.verdict}</b>. Every decision is stored in the run's record.</p>}
        </div>
      </div>
    </div>
  );
}
