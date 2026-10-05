import { Clapperboard, FileText, History, ImageIcon, Mic, Settings } from "lucide-react";
import { designApi, mediaUrl, useLoad, type PipelineInfo, type PipelineKey, type RunSummary, type StudioStatus } from "./api";
import { Banner, Link, Progress, StatusPill } from "./ui";
import { go, when } from "./lib";

const ICONS: Record<PipelineKey, typeof Clapperboard> = { video: Clapperboard, image: ImageIcon, voice: Mic, article: FileText };
const TAGLINES: Record<PipelineKey, string> = {
  video: "Ads · promos · previz",
  image: "Key art · posters · keyframes",
  voice: "Podcast intros · narration · ad reads",
  article: "Summaries · reports · explainers",
};
const ORDER: PipelineKey[] = ["article", "voice", "image", "video"];

export function RoleChips({ status }: { status: StudioStatus }) {
  const show = ["text-draft", "image", "voice", "video"];
  return (
    <div className="ds-chips-bar">
      {status.roles.filter((role) => show.includes(role.role)).map((role) => {
        const retiring = role.role === "video" && status.video_retirement;
        const kind = !role.configured ? "bad" : retiring && status.video_retirement!.days_left <= 14 ? "warn" : "ok";
        const label = role.label.replace("Text: drafting", "Text");
        return (
          <span key={role.role} className={`ds-chip ${kind}`} title={`${role.resource} / ${role.deployment}`}>
            ● {label} · {role.configured ? role.model : "not connected"}
            {retiring && role.configured ? ` · retires ${new Date(`${status.video_retirement!.on}T12:00:00`).toLocaleDateString([], { month: "short", day: "numeric" })}` : ""}
          </span>
        );
      })}
      <Link to="/design-studio/settings" className="ds-btn sm ghost"><Settings size={13} aria-hidden="true" /> Settings</Link>
      {status.provider_mode === "fake" && <span className="ds-chip warn">Offline demo mode: placeholder media</span>}
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

function PipelineCard({ pipeline, ready, missing }: { pipeline: PipelineInfo; ready: boolean; missing: string[] }) {
  const Icon = ICONS[pipeline.key];
  return (
    <article className={`ds-card ds-pipe${pipeline.key === "video" ? " hl" : ""}`}>
      <div className="ds-pipe-top">
        <span className={`ds-pipe-badge ${pipeline.key}`}><Icon size={19} aria-hidden="true" /></span>
        <div>
          <b>{pipeline.title}</b>
          <small>{TAGLINES[pipeline.key]}</small>
        </div>
      </div>
      <p>{pipeline.summary}</p>
      <div className="ds-steps-line" aria-label="Steps">
        {pipeline.steps.map((step, index) => (
          <span key={step.key} className="ds-row" style={{ gap: 5 }}>
            <span className={step.gate ? "gate" : ""}>{step.title}{step.gate ? " ✋" : ""}</span>
            {index < pipeline.steps.length - 1 && <em>›</em>}
          </span>
        ))}
      </div>
      <div className="ds-row">
        <button type="button" className="ds-btn primary" disabled={!ready} onClick={() => go(`/design-studio/new/${pipeline.key}`)}>
          New {pipeline.title.toLowerCase()} run
        </button>
        {!ready && <span className="ds-tiny ds-muted">Needs: {missing.join(", ")}</span>}
      </div>
    </article>
  );
}

export default function HomePage() {
  const status = useLoad(designApi.status, "status");
  const pipelines = useLoad(designApi.pipelines, "pipelines");
  const runs = useLoad(() => designApi.runs({ limit: 6 }), "recent");
  const error = status.error ?? pipelines.error ?? runs.error;
  const ordered = ORDER.map((key) => pipelines.data?.find((p) => p.key === key)).filter((p): p is PipelineInfo => Boolean(p));

  return (
    <div className="page ds">
      <header className="ds-head">
        <div>
          <span className="eyebrow">Design Studio</span>
          <h1>Make it with models. Review every step.</h1>
          <p className="ds-sub">
            Pipelines for text, voice, images and video on your Microsoft Foundry models. Each run pauses where a person has to
            decide (✋), and saves its prompts, model versions, outputs and your decisions, so you can reopen, fork or
            compare it later.
          </p>
        </div>
        <div className="ds-head-actions">
          <Link to="/design-studio/history" className="ds-btn"><History size={15} aria-hidden="true" /> Run history</Link>
        </div>
      </header>
      {error && <Banner kind="error">{error}</Banner>}
      {status.data && <RoleChips status={status.data} />}
      {status.data?.video_retirement && status.data.video_retirement.days_left >= 0 && status.data.video_retirement.days_left <= 14 && (
        <div style={{ marginBottom: 14 }}>
          <Banner kind="warn">
            The video model (Sora 2, version 2025-12-08) retires on {status.data.video_retirement.on}: {status.data.video_retirement.days_left} day(s) left.
            Runs already in history keep their videos; new video runs need a replacement model after that date.
          </Banner>
        </div>
      )}
      <section className="ds-pipes" aria-label="Pipelines">
        {ordered.map((pipeline) => {
          const state = status.data?.pipelines.find((item) => item.key === pipeline.key);
          return <PipelineCard key={pipeline.key} pipeline={pipeline} ready={state?.ready ?? false} missing={state?.missing ?? []} />;
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
