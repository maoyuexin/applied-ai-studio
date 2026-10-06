import { useEffect, type ReactNode } from "react";
import { AlertTriangle, CheckCircle2, Info, LoaderCircle, UserCheck, XCircle } from "lucide-react";
import { mediaUrl, type Artifact, type Check, type RunEvent, type RunStatus, type Step, type StepSpec } from "./api";
import { checkFlag, clockOf, go } from "./lib";

export function Link({ to, children, className, title, ...aria }: {
  to: string; children: ReactNode; className?: string; title?: string; "aria-label"?: string;
}) {
  return (
    <a
      href={to}
      className={className}
      title={title}
      aria-label={aria["aria-label"]}
      onClick={(event) => {
        if (event.metaKey || event.ctrlKey || event.shiftKey || event.button !== 0) return;
        event.preventDefault();
        go(to);
      }}
    >
      {children}
    </a>
  );
}

export function Crumbs({ items }: { items: Array<{ label: string; to?: string }> }) {
  return (
    <nav className="ds-crumbs" aria-label="Breadcrumb">
      {items.map((item, index) => (
        <span key={`${item.label}-${index}`} className="ds-row" style={{ gap: 6 }}>
          {index > 0 && <span aria-hidden="true">›</span>}
          {item.to ? <Link to={item.to}>{item.label}</Link> : <span>{item.label}</span>}
        </span>
      ))}
    </nav>
  );
}

const STATUS_LABEL: Record<RunStatus, string> = {
  running: "Running",
  waiting: "Waiting for your review",
  completed: "Completed",
  failed: "Needs attention",
  canceled: "Canceled",
};

export function StatusPill({ status, detail, restricted }: { status: RunStatus; detail?: string; restricted?: boolean }) {
  return (
    <span className="ds-row" style={{ gap: 6 }}>
      <span className={`ds-status ${status}`}>
        <span className="dot" aria-hidden="true" />
        {STATUS_LABEL[status]}
        {detail ? ` · ${detail}` : ""}
      </span>
      {restricted && <span className="ds-status restricted">Restricted</span>}
    </span>
  );
}

export function Banner({ kind = "info", children }: { kind?: "info" | "warn" | "error" | "ok"; children: ReactNode }) {
  const Icon = kind === "error" ? XCircle : kind === "warn" ? AlertTriangle : kind === "ok" ? CheckCircle2 : Info;
  return (
    <div className={`ds-banner ${kind}`} role={kind === "error" ? "alert" : "status"}>
      <Icon size={16} aria-hidden="true" />
      <div>{children}</div>
    </div>
  );
}

export function Spinner({ size = 14 }: { size?: number }) {
  return <LoaderCircle size={size} className="ds-spin" aria-hidden="true" />;
}

export function Progress({ value }: { value: number | null | undefined }) {
  const width = Math.max(4, Math.min(100, value ?? 4));
  return (
    <div className="ds-progress" role="progressbar" aria-valuenow={value ?? 0} aria-valuemin={0} aria-valuemax={100}>
      <i style={{ width: `${width}%` }} />
    </div>
  );
}

const CHECK_MARK: Record<string, string> = { ok: "✓", warn: "!", bad: "✗", info: "i" };

export function Checks({ checks }: { checks: Check[] }) {
  if (!checks.length) return <p className="ds-muted ds-small">No automatic checks for this item.</p>;
  return (
    <div className="ds-checks">
      {checks.map((check) => (
        <div className="ds-check" key={check.key}>
          <span className={`box ${check.state}`} aria-label={check.state}>{CHECK_MARK[check.state]}</span>
          <div>
            {check.label}
            {check.basis && <small>{check.basis}</small>}
          </div>
        </div>
      ))}
    </div>
  );
}

export function EventLog({ events, limit = 40 }: { events: RunEvent[]; limit?: number }) {
  const items = [...events].reverse().slice(0, limit);
  return (
    <div className="ds-log" aria-live="polite">
      {items.map((event) => (
        <div key={event.id}>
          <span className="t">{clockOf(event.at)}</span>
          <span className={event.level}>{event.message}</span>
        </div>
      ))}
      {!items.length && <span className="ds-muted">No events yet.</span>}
    </div>
  );
}

const STEP_SUB: Record<string, string> = {
  pending: "not started",
  running: "working…",
  waiting: "waiting for you",
  done: "done",
  skipped: "skipped",
  failed: "failed",
};

export function Stepper({ steps, detail, onSelect, selected }: {
  steps: Step[];
  detail?: (step: Step) => string | null;
  onSelect?: (key: string) => void;
  selected?: string | null;
}) {
  return (
    <div className="ds-stepper">
      {steps.map((step, index) => {
        const extra = detail?.(step);
        const content = (
          <>
            <span className="n">{step.status === "done" ? "✓" : step.status === "failed" ? "!" : index + 1}</span>
            <div>
              <b>{step.title}</b>
              <small>{extra ?? STEP_SUB[step.status]}</small>
              {step.gate && <ReviewTag waiting={step.status === "waiting"} done={step.status === "done"} />}
            </div>
          </>
        );
        const className = `ds-st ${step.status}${selected === step.key ? " sel" : ""}`;
        return onSelect && step.status !== "pending" && step.status !== "skipped" ? (
          <button key={step.key} type="button" className={className} onClick={() => onSelect(step.key)}>{content}</button>
        ) : (
          <div key={step.key} className={className}>{content}</div>
        );
      })}
    </div>
  );
}

export function MediaPreview({ artifact, portrait, controls = false, square }: {
  artifact: Artifact;
  portrait?: boolean;
  controls?: boolean;
  square?: boolean;
}) {
  const shape = portrait ? " portrait" : square ? " square" : "";
  if (artifact.status === "queued" || artifact.status === "running") {
    return (
      <div className={`ds-media hatched${shape}`}>
        <div className="gen">
          <span>{artifact.status === "queued" ? "queued" : artifact.progress ? `generating… ${artifact.progress}%` : "generating…"}</span>
          {artifact.status === "running" && <Progress value={artifact.progress} />}
        </div>
      </div>
    );
  }
  if (artifact.status === "failed" || artifact.status === "blocked" || artifact.status === "canceled") {
    return (
      <div className={`ds-media hatched${shape}`}>
        <div className="gen err">
          <span>{artifact.status === "blocked" ? "Blocked by the content filter" : artifact.status === "canceled" ? "Canceled" : "Failed"}</span>
        </div>
      </div>
    );
  }
  const flag = checkFlag(artifact);
  const isVideo = artifact.media_type === "video/mp4";
  const isAudio = artifact.media_type?.startsWith("audio/");
  return (
    <div className={`ds-media${shape}`}>
      {isVideo && controls && artifact.media_sha ? (
        <video src={mediaUrl(artifact.media_sha)} poster={artifact.thumb_sha ? mediaUrl(artifact.thumb_sha) : undefined} controls preload="none" playsInline />
      ) : artifact.thumb_sha ? (
        <img src={mediaUrl(artifact.thumb_sha)} alt={artifact.label ?? artifact.kind} loading="lazy" />
      ) : artifact.media_sha && !isAudio ? (
        <img src={mediaUrl(artifact.media_sha)} alt={artifact.label ?? artifact.kind} loading="lazy" />
      ) : (
        <span className="ds-muted ds-small">{artifact.kind}</span>
      )}
      {isVideo && !controls && artifact.metrics.duration != null && <span className="badge">▶ 0:{String(Math.round(artifact.metrics.duration)).padStart(2, "0")}</span>}
      {flag && <span className={`flag${flag.bad ? " bad" : ""}`}>{flag.text}</span>}
    </div>
  );
}

export function Dialog({ title, children, onClose, actions }: {
  title: string;
  children: ReactNode;
  onClose: () => void;
  actions: ReactNode;
}) {
  useEffect(() => {
    const onKey = (event: KeyboardEvent) => {
      if (event.key === "Escape") onClose();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);
  return (
    <div className="ds-dialog-backdrop" role="presentation" onMouseDown={(event) => { if (event.target === event.currentTarget) onClose(); }}>
      <div className="ds-dialog" role="dialog" aria-modal="true" aria-label={title}>
        <h2>{title}</h2>
        <div className="ds-dim ds-small">{children}</div>
        <div className="ds-row">{actions}</div>
      </div>
    </div>
  );
}

export function PipelineIcon({ pipeline, size = 18 }: { pipeline: string; size?: number }) {
  if (pipeline === "video") return <span aria-hidden="true" style={{ fontSize: size }}>▶</span>;
  if (pipeline === "image") return <span aria-hidden="true" style={{ fontSize: size }}>▣</span>;
  return <span aria-hidden="true" style={{ fontSize: size }}>♪</span>;
}

/** Marks a human review gate: the run pauses at this step until a person approves. */
export function ReviewTag({ waiting = false, done = false }: { waiting?: boolean; done?: boolean }) {
  const label = waiting ? "Waiting for you" : done ? "Reviewed" : "You review";
  return (
    <span className={`ds-review-tag${waiting ? " waiting" : ""}${done ? " done" : ""}`}
      title="Human review: the run pauses here until you approve">
      <UserCheck size={12} aria-hidden="true" /> {label}
    </span>
  );
}

/** The steps of a pipeline, in order, with who does each one: a model, a tool, or you. */
export function FlowTrack({ steps, modelFor, compact = false }: {
  steps: StepSpec[];
  modelFor: (step: StepSpec) => string;
  compact?: boolean;
}) {
  return (
    <ol className={`ds-flow${compact ? " compact" : ""}`}>
      {steps.map((step, index) => (
        <li key={step.key} className={step.gate ? "gate" : ""}>
          <span className="n" aria-hidden="true">{index + 1}</span>
          <div className="t">
            <b>{step.title}{step.optional ? <span className="ds-muted"> · optional</span> : null}</b>
            <small className="who">{modelFor(step)}</small>
            {!compact && step.description && <small>{step.description}</small>}
          </div>
          {step.gate ? <ReviewTag /> : <span />}
        </li>
      ))}
    </ol>
  );
}
