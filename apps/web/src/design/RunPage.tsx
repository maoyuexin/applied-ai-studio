import { useCallback, useEffect, useRef, useState } from "react";
import { Ban, Download, GitFork, Lock, RotateCcw, Trash2, Unlock } from "lucide-react";
import { designApi, mediaUrl, useRun, type RunDetail } from "./api";
import { Banner, Crumbs, Dialog, EventLog, Link, ReviewTag, Spinner, StatusPill, Stepper } from "./ui";
import ArticleRun from "./ArticleRun";
import ImageRun from "./ImageRun";
import ReviewView from "./ReviewView";
import VideoRun from "./VideoRun";
import VoiceRun from "./VoiceRun";
import { go, useAction, when } from "./lib";

export interface RunViewProps {
  detail: RunDetail;
  act: <T = unknown>(action: string, payload?: Record<string, unknown>) => Promise<T | undefined>;
  busy: string | null;
  setApproveExtra: (fn: (() => Record<string, unknown>) | null) => void;
  openReview: (artifactId: string) => void;
}

function stepDetail(detail: RunDetail) {
  return (step: RunDetail["steps"][number]) => {
    const items = detail.artifacts.filter((a) => a.step_key === step.key && a.kind !== "reference" && a.status !== "superseded");
    if (step.status === "failed") return step.error ? `failed: ${step.error.slice(0, 60)}` : "failed";
    if (!items.length) return null;
    const active = items.filter((a) => a.status === "queued" || a.status === "running").length;
    const ready = items.filter((a) => a.status === "ready").length;
    const kept = items.filter((a) => a.verdict === "keep").length;
    const parts = [];
    if (ready) parts.push(`${ready} ready`);
    if (kept && step.gate) parts.push(`${kept} kept`);
    if (active) parts.push(`${active} generating`);
    const blocked = items.filter((a) => a.status === "blocked" || a.status === "failed").length;
    if (blocked) parts.push(`${blocked} need attention`);
    return parts.join(" · ") || null;
  };
}

export default function RunPage({ runId, review }: { runId: string; review: string | null }) {
  const { detail, setDetail, error, live } = useRun(runId);
  const { busy, run, toast } = useAction();
  const approveExtra = useRef<(() => Record<string, unknown>) | null>(null);
  const [confirm, setConfirm] = useState<null | "delete" | "cancel">(null);
  const [renaming, setRenaming] = useState(false);
  const [title, setTitle] = useState("");

  const act = useCallback(async <T,>(action: string, payload: Record<string, unknown> = {}): Promise<T | undefined> => {
    const response = await run(action, () => designApi.act<T>(runId, action, payload));
    if (response) {
      setDetail(response.detail);
      return response.result;
    }
    return undefined;
  }, [run, runId, setDetail]);

  const setApproveExtra = useCallback((fn: (() => Record<string, unknown>) | null) => {
    approveExtra.current = fn;
  }, []);

  const openReview = useCallback((artifactId: string) => go(`/design-studio/runs/${runId}?review=${artifactId}`), [runId]);

  useEffect(() => {
    if (detail) setTitle(detail.run.title);
  }, [detail?.run.title]); // eslint-disable-line react-hooks/exhaustive-deps

  if (!detail) {
    return (
      <div className="page ds">
        {error ? <Banner kind="error">{error}</Banner> : <div className="route-loading"><Spinner /> Loading run…</div>}
      </div>
    );
  }

  const { run: info, steps, gate } = detail;
  const waiting = gate ? steps.find((step) => step.key === gate.step) : null;
  const failed = steps.find((step) => step.status === "failed");
  const stepIndex = steps.findIndex((step) => step.key === info.current_step);
  const reviewItem = review ? detail.artifacts.find((a) => a.id === review) : null;
  const props: RunViewProps = { detail, act, busy, setApproveExtra, openReview };

  const approve = async () => {
    if (!gate) return;
    await act("approve", { step: gate.step, ...(approveExtra.current?.() ?? {}) });
  };

  const fork = () => go(`/design-studio/new/${info.pipeline}?fork=${info.id}`);
  const rename = async () => {
    const value = title.trim();
    if (!value || value === info.title) { setRenaming(false); return; }
    const updated = await run("rename", () => designApi.update(info.id, { title: value }));
    if (updated) setDetail(updated);
    setRenaming(false);
  };
  const toggleRestricted = async () => {
    const updated = await run("restrict", () => designApi.update(info.id, { restricted: !info.restricted }));
    if (updated) setDetail(updated);
  };
  const remove = async () => {
    setConfirm(null);
    const done = await run("delete", async () => { await designApi.remove(info.id); return true; });
    if (done) go("/design-studio/history");
  };

  return (
    <div className="page ds">
      <Crumbs items={[
        { label: "Design Studio", to: "/design-studio" },
        { label: "History", to: "/design-studio/history" },
        { label: detail.pipeline?.title ?? info.pipeline },
        { label: info.id },
      ]} />
      <header className="ds-head">
        <div style={{ minWidth: 0 }}>
          {renaming ? (
            <form className="ds-row" onSubmit={(event) => { event.preventDefault(); void rename(); }}>
              <input aria-label="Run title" value={title} onChange={(e) => setTitle(e.target.value)} autoFocus style={{ fontSize: 20, fontWeight: 700, width: "min(640px, 80vw)" }} />
              <button type="submit" className="ds-btn sm primary">Save</button>
              <button type="button" className="ds-btn sm ghost" onClick={() => { setTitle(info.title); setRenaming(false); }}>Cancel</button>
            </form>
          ) : (
            <h1>
              <button type="button" onClick={() => setRenaming(true)} title="Rename" style={{ all: "unset", cursor: "text" }}>{info.title}</button>
            </h1>
          )}
          <div className="ds-row ds-small">
            <StatusPill status={info.status} restricted={info.restricted} detail={stepIndex >= 0 && info.status !== "completed" ? `step ${stepIndex + 1} of ${steps.length}` : undefined} />
            <span className="ds-muted">Started {when(info.created_at)}{info.counters.outputs ? ` · ${info.counters.outputs}` : ""}</span>
            {info.parent_run_id && <span className="ds-muted">· fork of <Link to={`/design-studio/runs/${info.parent_run_id}`}>{info.parent_run_id}</Link></span>}
            {!live && info.status !== "completed" && info.status !== "canceled" && <span className="ds-chip warn" title="Live updates reconnecting; polling every few seconds">reconnecting…</span>}
          </div>
        </div>
        <div className="ds-head-actions">
          <button type="button" className="ds-btn" onClick={fork}><GitFork size={14} aria-hidden="true" /> Fork</button>
          {!info.restricted && <a className="ds-btn" href={designApi.exportUrl(info.id)} download><Download size={14} aria-hidden="true" /> Export bundle</a>}
          <button type="button" className="ds-btn" onClick={() => void toggleRestricted()} title={info.restricted ? "Allow exporting this run" : "Keep this run on this machine only"}>
            {info.restricted ? <Unlock size={14} aria-hidden="true" /> : <Lock size={14} aria-hidden="true" />} {info.restricted ? "Unrestrict" : "Restrict"}
          </button>
          {(info.status === "running" || info.status === "waiting") && (
            <button type="button" className="ds-btn" onClick={() => setConfirm("cancel")}><Ban size={14} aria-hidden="true" /> Cancel</button>
          )}
          <button type="button" className="ds-btn danger" onClick={() => setConfirm("delete")} aria-label="Delete run"><Trash2 size={14} aria-hidden="true" /></button>
        </div>
      </header>

      {failed && (
        <div style={{ marginBottom: 12 }}>
          <Banner kind="error">
            <b>{failed.title} failed.</b> {failed.error}{" "}
            <button type="button" className="ds-btn sm" onClick={() => void act("retry_step", { step: failed.key })} disabled={busy !== null}>
              <RotateCcw size={13} aria-hidden="true" /> Retry step
            </button>
          </Banner>
        </div>
      )}
      {info.source === "imported" && (
        <div style={{ marginBottom: 12 }}>
          <Banner kind="info">Imported run: these outputs were made before Design Studio existed (or on another machine). Fork it to run the same brief again here.</Banner>
        </div>
      )}

      {reviewItem ? (
        <ReviewView {...props} artifact={reviewItem} onBack={() => go(`/design-studio/runs/${runId}`)} />
      ) : (
        <div className="ds-ws two">
          <aside className="ds-ws-side">
            <div className="ds-card tight">
              <Stepper steps={steps} detail={stepDetail(detail)} selected={info.current_step}
                onSelect={(key) => document.getElementById(`step-${key}`)?.scrollIntoView({ behavior: "smooth", block: "start" })} />
            </div>
            {detail.artifacts.some((a) => a.kind === "reference") && (
              <div className="ds-card tight">
                <h3>References</h3>
                <div className="ds-mini-refs">
                  {detail.artifacts.filter((a) => a.kind === "reference").map((a) => (
                    <a key={a.id} className="ds-mini-ref" href={mediaUrl(a.media_sha!)} target="_blank" rel="noreferrer" title={a.label ?? ""}>
                      <img src={mediaUrl(a.thumb_sha ?? a.media_sha!)} alt="" />{a.data.role}
                    </a>
                  ))}
                </div>
              </div>
            )}
            <div className="ds-card tight">
              <h3>This run</h3>
              <dl className="ds-kv">
                <dt>Pipeline</dt><dd>{detail.pipeline?.title}</dd>
                <dt>Models</dt><dd className="ds-mono ds-tiny">{(info.counters.models ?? []).join(" · ") || "—"}</dd>
                {info.counters.video_seconds ? <><dt>Generated</dt><dd>{info.counters.video_seconds} s of video</dd></> : null}
                {info.counters.images ? <><dt>Images</dt><dd>{info.counters.images}</dd></> : null}
                {info.counters.audio_seconds ? <><dt>Audio</dt><dd>{info.counters.audio_seconds} s recorded</dd></> : null}
                <dt>Decisions</dt><dd>{detail.decisions.length}</dd>
                <dt>Tags</dt><dd>{info.tags.length ? info.tags.map((tag) => <span key={tag} className="ds-chip" style={{ marginRight: 4 }}>{tag}</span>) : "—"}</dd>
              </dl>
            </div>
            <div className="ds-card tight">
              <h3>Event log</h3>
              <EventLog events={detail.events} />
            </div>
          </aside>
          <main style={{ minWidth: 0 }}>
            {gate && waiting && (
              <div className="ds-gatebar" role="region" aria-label="Review gate">
                <div>
                  <ReviewTag waiting /> <b>{waiting.title}</b>{" "}
                  <span className="ds-small ds-dim">{gate.ready ? "Approve to continue to the next step." : gate.reason}</span>
                </div>
                <button type="button" className="ds-btn primary" disabled={!gate.ready || busy !== null} onClick={() => void approve()}>
                  {busy === "approve" ? <Spinner /> : null} Approve & continue
                </button>
              </div>
            )}
            {info.pipeline === "video" && <VideoRun {...props} />}
            {info.pipeline === "image" && <ImageRun {...props} />}
            {info.pipeline === "voice" && <VoiceRun {...props} />}
            {info.pipeline === "article" && <ArticleRun {...props} />}
          </main>
        </div>
      )}

      {confirm === "delete" && (
        <Dialog title="Delete this run?" onClose={() => setConfirm(null)} actions={<>
          <button type="button" className="ds-btn ghost" onClick={() => setConfirm(null)}>Keep it</button>
          <button type="button" className="ds-btn danger" onClick={() => void remove()}>Delete run and its media</button>
        </>}>
          This removes “{info.title}”, its outputs and its decision record from this machine. Export a bundle first if you may want it back.
        </Dialog>
      )}
      {confirm === "cancel" && (
        <Dialog title="Cancel this run?" onClose={() => setConfirm(null)} actions={<>
          <button type="button" className="ds-btn ghost" onClick={() => setConfirm(null)}>Keep running</button>
          <button type="button" className="ds-btn danger" onClick={() => { setConfirm(null); void act("cancel"); }}>Cancel run</button>
        </>}>
          Queued work stops. Jobs already started at the vendor may still finish (and be billed) on their side. Finished outputs stay in history.
        </Dialog>
      )}
      {toast}
    </div>
  );
}
