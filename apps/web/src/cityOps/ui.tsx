import type { ReactNode } from "react";
import { CircleAlert, DatabaseZap, LoaderCircle } from "lucide-react";
import type { RecordedRun } from "./runs";

export function Panel({ eyebrow, title, aside, className = "", children }: {
  eyebrow?: string; title: ReactNode; aside?: ReactNode; className?: string; children: ReactNode;
}) {
  return (
    <section className={`co-panel ${className}`}>
      <header className="co-panel-head">
        <div>
          {eyebrow && <span className="co-eyebrow">{eyebrow}</span>}
          <strong>{title}</strong>
        </div>
        {aside}
      </header>
      {children}
    </section>
  );
}

/** Every AI-written message carries this. Nothing in this app is ever sent. */
export function NotSent() {
  return <span className="co-notsent">Draft · AI-assisted · not sent</span>;
}

/** Loading, missing (not imported here) and error states of a recorded run. */
export function RunGate({ run, what, children }: { run: RecordedRun; what: string; children: ReactNode }) {
  if (run.load.state === "loading") {
    return <div className="co-state"><LoaderCircle size={18} className="co-spin" aria-hidden="true" /> Loading the recorded {what}…</div>;
  }
  if (run.load.state === "missing") {
    return (
      <div className="co-state is-missing">
        <DatabaseZap size={20} aria-hidden="true" />
        <div>
          <strong>This run is not imported on this install (History → Import).</strong>
          <p>The recorded {what} comes from Design Studio run <code>{run.load.id}</code>. Import its bundle in Design Studio → History → Import, then reload this page.</p>
        </div>
      </div>
    );
  }
  if (run.load.state === "error") {
    return (
      <div className="co-state is-error">
        <CircleAlert size={20} aria-hidden="true" />
        <div>
          <strong>The recorded {what} could not be loaded.</strong>
          <p>{run.load.message}</p>
          <button type="button" className="co-btn" onClick={() => void run.refresh()}>Try again</button>
        </div>
      </div>
    );
  }
  return <>{children}</>;
}

export function ActionError({ run }: { run: RecordedRun }) {
  if (!run.actionError) return null;
  return (
    <p className="co-error" role="alert">
      <CircleAlert size={14} aria-hidden="true" /> {run.actionError}
      <button type="button" className="co-link" onClick={run.clearError}>Dismiss</button>
    </p>
  );
}
