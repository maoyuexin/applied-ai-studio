import { Clapperboard, FileText, History, ImageIcon, Mic, ScanEye, Settings } from "lucide-react";
import { designApi, mediaUrl, useLoad, type PipelineInfo, type PipelineKey, type RunSummary, type StudioStatus } from "./api";
import { Banner, FlowTrack, Link, Progress, ReviewTag, StatusPill } from "./ui";
import { go, stepWorker, when } from "./lib";

const ICONS: Record<PipelineKey, typeof Clapperboard> = { video: Clapperboard, image: ImageIcon, voice: Mic, article: FileText, inspect: ScanEye };
const TAGLINES: Record<PipelineKey, string> = {
  video: "Ads · promos · previz",
  image: "Key art · posters · keyframes",
  voice: "Podcast intros · narration · ad reads",
  article: "Summaries · reports · explainers",
  inspect: "Vision checks · audits · what may be asked",
};
const ORDER: PipelineKey[] = ["article", "voice", "image", "video", "inspect"];

/** Which models a card's pipeline uses, so each card shows its own connections. */
const CARD_ROLES: Record<PipelineKey, Array<[string, string]>> = {
  article: [["text-draft", "Writes"], ["text-judge", "Checks"]],
  voice: [["text-draft", "Script"], ["voice", "Voice"], ["listen-back", "Listen-back"]],
  image: [["text-draft", "Prompt"], ["image", "Image"]],
  video: [["text-draft", "Shots"], ["image", "Keyframes"], ["video", "Video"], ["voice", "Voiceover"]],
  inspect: [["text-draft", "Vision"]],
};

function shortDate(iso: string) {
  return new Date(`${iso}T12:00:00`).toLocaleDateString([], { month: "short", day: "numeric" });
}

function ModelChips({ pipeline, status }: { pipeline: PipelineKey; status: StudioStatus }) {
  return (
    <div className="ds-model-chips" aria-label="Models this pipeline uses">
      {CARD_ROLES[pipeline].map(([role, label]) => {
        const info = status.roles.find((item) => item.role === role);
        const configured = info?.configured ?? false;
        const name = pipeline === "inspect" ? `pick up to 4 of ${status.text_models.length}`
          : role === "text-draft" || role === "text-judge" ? status.text_defaults?.[role] ?? info?.model
          : role === "listen-back" ? "Speech to text" : info?.model;
        const retire = role === "video" ? status.video_retirement : null;
        const retiring = Boolean(retire && retire.days_left >= 0 && retire.days_left <= 14);
        const kind = !configured ? "bad" : retiring ? "warn" : "ok";
        const title = !configured ? "Not connected on this install: see Settings"
          : retiring && retire ? `Sora 2 (2025-12-08) retires ${retire.on}: ${retire.days_left} day(s) left. Finished videos stay in history.`
            : `${info?.resource} / ${info?.deployment}`;
        return (
          <span key={role} className={`ds-chip ${kind}`} title={title}>
            ● {label} · {configured ? name : "not connected"}{retiring && retire ? ` · retires ${shortDate(retire.on)}` : ""}
          </span>
        );
      })}
    </div>
  );
}

export function RunsTable({ runs, compact = false }: { runs: RunSummary[]; compact?: boolean }) {
  return (
    <div className="ds-scroll-x">
      <table className="ds-table">
        <thead>
          <tr>
            <th aria-label="Preview" />
            <th>Run</th>
            <th>Pipeline</th>
            <th>Status</th>
            <th className="ds-hide-sm">{compact ? "Progress" : "Outputs"}</th>
            <th>Updated</th>
          </tr>
        </thead>
        <tbody>
          {runs.map((run) => (
            <tr key={run.id} className="clickable" onClick={() => go(`/design-studio/runs/${run.id}`)}>
              <td>
                <div className="ds-thumb">
                  {run.counters.thumb_sha ? <img src={mediaUrl(run.counters.thumb_sha)} alt="" loading="lazy" /> : <PipelineGlyph pipeline={run.pipeline} />}
                </div>
              </td>
              <td className="title">
                <Link to={`/design-studio/runs/${run.id}`}><b>{run.title}</b></Link>
                <small>{run.source === "imported" ? "imported · " : ""}{run.brief_excerpt.slice(0, 90)}</small>
              </td>
              <td>{run.pipeline_title}</td>
              <td><StatusPill status={run.status} restricted={run.restricted} /></td>
              <td className="ds-hide-sm">
                {compact && run.status !== "completed" && run.step ? (
                  <div className="ds-stack" style={{ gap: 4 }}>
                    <Progress value={(run.steps_done / Math.max(run.steps_total, 1)) * 100} />
                    <span className="ds-tiny ds-muted">step {run.step.index} of {run.step.total} · {run.step.title}</span>
                  </div>
                ) : (
                  <span className="ds-small ds-dim">{run.counters.outputs ?? "—"}</span>
                )}
              </td>
              <td className="ds-small nowrap">{when(run.updated_at)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export function PipelineGlyph({ pipeline }: { pipeline: PipelineKey }) {
  const Icon = ICONS[pipeline];
  return <Icon size={16} aria-hidden="true" />;
}

function PipelineCard({ pipeline, ready, missing, model, status }: { pipeline: PipelineInfo; ready: boolean; missing: string[]; model: (role: string) => string | undefined; status: StudioStatus | null }) {
  const Icon = ICONS[pipeline.key];
  return (
    <article className={`ds-card ds-pipe${pipeline.key === "video" ? " hl" : ""}`}>
      <div className="ds-pipe-main">
        <div className="ds-pipe-top">
          <span className={`ds-pipe-badge ${pipeline.key}`}><Icon size={19} aria-hidden="true" /></span>
          <div>
            <b>{pipeline.title}</b>
            <small>{TAGLINES[pipeline.key]}</small>
          </div>
        </div>
        <p>{pipeline.summary}</p>
        {status && <ModelChips pipeline={pipeline.key} status={status} />}
        <div className="ds-row">
          <button type="button" className="ds-btn primary" disabled={!ready} onClick={() => go(`/design-studio/new/${pipeline.key}`)}>
            New {pipeline.title.toLowerCase()} run
          </button>
          {!ready && <span className="ds-tiny ds-muted">Needs: {missing.join(", ")}</span>}
        </div>
      </div>
      <div className="ds-pipe-flow">
        <span className="ds-flow-label">How it runs</span>
        <FlowTrack steps={pipeline.steps} compact modelFor={(step) => stepWorker(step, model, pipeline.key)} />
      </div>
    </article>
  );
}

export default function HomePage() {
  const status = useLoad(designApi.status, "status");
  const pipelines = useLoad(designApi.pipelines, "pipelines");
  const runs = useLoad(() => designApi.runs({ limit: 6 }), "recent");
  const error = status.error ?? pipelines.error ?? runs.error;
  const model = (role: string) => (role === "text-draft" || role === "text-judge" ? status.data?.text_defaults?.[role] : undefined)
    ?? status.data?.roles.find((item) => item.role === role)?.model;
  const ordered = ORDER.map((key) => pipelines.data?.find((p) => p.key === key)).filter((p): p is PipelineInfo => Boolean(p));

  return (
    <div className="page ds">
      <header className="ds-head">
        <div>
          <h1>Design Studio</h1>
          <p className="ds-sub">
            Pipelines for text, voice, images and video on your Microsoft Foundry models. Each run pauses at the review
            steps for your decision, and saves its prompts, model versions, outputs and decisions, so you can reopen, fork
            or compare it later.
          </p>
        </div>
        <div className="ds-head-actions">
          {status.data?.provider_mode === "fake" && <span className="ds-chip warn">Offline demo mode: placeholder media</span>}
          <Link to="/design-studio/history" className="ds-btn icon" title="Run history" aria-label="Run history"><History size={18} aria-hidden="true" /></Link>
          <Link to="/design-studio/settings" className="ds-btn icon" title="Settings: models, caps, where this runs" aria-label="Settings"><Settings size={18} aria-hidden="true" /></Link>
        </div>
      </header>
      {error && <Banner kind="error">{error}</Banner>}
      <p className="ds-legend">
        <span>Each card lists its steps in the order they run.</span>
        <span className="ds-row" style={{ gap: 6 }}><ReviewTag /> the run pauses until you approve</span>
        <span>Other steps run on their own; the line under each step says which model or tool does it.</span>
      </p>
      <section className="ds-pipes" aria-label="Pipelines">
        {ordered.map((pipeline) => {
          const state = status.data?.pipelines.find((item) => item.key === pipeline.key);
          return <PipelineCard key={pipeline.key} pipeline={pipeline} ready={state?.ready ?? false} missing={state?.missing ?? []} model={model} status={status.data} />;
        })}
      </section>
      <section className="ds-card" style={{ marginTop: 16 }}>
        <div className="ds-row between" style={{ marginBottom: 6 }}>
          <h2 style={{ margin: 0 }}>Recent runs</h2>
          <Link to="/design-studio/history" className="ds-btn sm">View all runs →</Link>
        </div>
        {runs.data && runs.data.runs.length > 0 ? (
          <RunsTable runs={runs.data.runs} compact />
        ) : (
          !runs.loading && (
            <div className="ds-empty">
              <b>No runs yet</b>
              <span>Start a pipeline above, or import a run bundle from another machine in Run history.</span>
            </div>
          )
        )}
      </section>
    </div>
  );
}
