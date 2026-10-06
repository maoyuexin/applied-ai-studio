import { useEffect, useMemo, useState } from "react";
import { Clapperboard, Download, Plus, Sparkles, Trash2 } from "lucide-react";
import { mediaUrl, type Artifact, type Reference } from "./api";
import { DropZone } from "./NewRunPage";
import type { RunViewProps } from "./RunPage";
import { Banner, Checks, MediaPreview, ReviewTag, Spinner } from "./ui";
import { PREFILL_KEY, type Prefill, go, useUploader } from "./lib";

type RefItem = Reference & { thumb_sha?: string };

function shapeOf(size?: string) {
  return { portrait: size === "864x1536", square: size === "1024x1024" };
}

function PromptStep({ detail, act, busy, setApproveExtra }: RunViewProps) {
  const step = detail.steps.find((s) => s.key === "prompt")!;
  const original = step.data.prompt ?? "";
  const [prompt, setPrompt] = useState(original);
  const dirty = prompt.trim() !== original.trim();
  useEffect(() => setPrompt(step.data.prompt ?? ""), [step.data.prompt]);
  useEffect(() => {
    if (step.status !== "waiting") return;
    setApproveExtra(dirty ? () => ({ prompt }) : null);
    return () => setApproveExtra(null);
  }, [dirty, prompt, step.status, setApproveExtra]);
  if (step.status === "running" && !original) return <p className="ds-muted"><Spinner /> The text model is writing the prompt…</p>;
  if (step.status !== "waiting") {
    return <details><summary className="ds-small ds-dim" style={{ cursor: "pointer" }}>Prompt approved{step.data.edited ? " with your edits" : ""}{step.data.model ? ` · written by ${step.data.model}` : ""}</summary><div className="ds-promptbox" style={{ marginTop: 8 }}>{original}</div></details>;
  }
  return (
    <div className="ds-stack" style={{ gap: 8 }}>
      <textarea aria-label="Prompt" value={prompt} onChange={(e) => setPrompt(e.target.value)} style={{ minHeight: 130 }} />
      <div className="ds-row between">
        <div className="ds-row">
          <button type="button" className="ds-btn sm" disabled={!dirty || busy !== null} onClick={() => void act("update_prompt", { prompt })}>Save edits</button>
          {dirty && <button type="button" className="ds-btn sm ghost" onClick={() => setPrompt(original)}>Discard</button>}
        </div>
        <span className="ds-tiny ds-muted">The app adds the reference-image roles and your “must not include” rules when it sends this.</span>
      </div>
    </div>
  );
}

function ImageCard({ item, selected, onSelect, act, busy, shape }: { item: Artifact; selected?: boolean; onSelect?: () => void; act: RunViewProps["act"]; busy: string | null; shape: { portrait: boolean; square: boolean } }) {
  return (
    <div className={`ds-take${item.verdict === "keep" ? " keep" : ""}${selected ? " selected" : ""}`}>
      <button type="button" className="ds-media-btn" onClick={onSelect} aria-label={`Select ${item.label}`}>
        <MediaPreview artifact={item} portrait={shape.portrait} square={shape.square} />
      </button>
      <div className="ds-meta">
        <div className="ds-row between"><b className="ds-mono">{item.label}</b><span className="ds-muted">{item.gen_seconds ? `${Math.round(item.gen_seconds)} s` : ""}</span></div>
        {item.error && <span className="ds-tiny" style={{ color: "var(--red)" }}>{item.error}</span>}
      </div>
      {item.status === "ready" && (
        <div className="ds-acts">
          <button type="button" className={`ds-btn sm${item.verdict === "keep" ? " good" : ""}`} disabled={busy !== null} onClick={() => void act("decide", { artifact_id: item.id, verdict: item.verdict === "keep" ? null : "keep" })}>{item.verdict === "keep" ? "Kept" : "Keep"}</button>
        </div>
      )}
    </div>
  );
}

interface TreeNode { item: Artifact; depth: number }

function buildTree(images: Artifact[]): TreeNode[] {
  const children = new Map<string, Artifact[]>();
  images.forEach((image) => {
    if (image.parent_id) children.set(image.parent_id, [...(children.get(image.parent_id) ?? []), image]);
  });
  const roots = images.filter((image) => image.grp === "candidates" && (image.verdict === "keep" || children.has(image.id)));
  const out: TreeNode[] = [];
  const walk = (item: Artifact, depth: number) => {
    out.push({ item, depth });
    (children.get(item.id) ?? []).forEach((child) => walk(child, depth + 1));
  };
  roots.forEach((root) => walk(root, 0));
  return out;
}

function IterateStep(props: RunViewProps & { images: Artifact[] }) {
  const { detail, act, busy, images, openReview, setApproveExtra } = props;
  const brief = detail.run.brief;
  const shape = shapeOf(brief.size);
  const step = detail.steps.find((s) => s.key === "iterate")!;
  const open = step.status === "waiting" || step.status === "running";
  const tree = useMemo(() => buildTree(images), [images]);
  const kept = images.filter((image) => image.status === "ready" && image.verdict === "keep");
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const selected = images.find((image) => image.id === selectedId) ?? tree[tree.length - 1]?.item ?? kept[0] ?? null;
  const runRefs: RefItem[] = detail.artifacts.filter((a) => a.kind === "reference" && a.media_sha).map((a) => ({ sha: a.media_sha!, thumb_sha: a.thumb_sha ?? undefined, role: (a.data.role as Reference["role"]) ?? "subject", name: a.label ?? "" }));
  const [refs, setRefs] = useState<RefItem[]>(runRefs.filter((ref) => ref.role === "subject"));
  const [note, setNote] = useState("");
  const [mode, setMode] = useState<"edit" | "regenerate">("edit");
  const [rewrite, setRewrite] = useState(Boolean(brief.prompt_helper));
  const [draft, setDraft] = useState<{ prompt: string; preview: string } | null>(null);
  const [finalId, setFinalId] = useState<string | null>(null);
  const [title, setTitle] = useState(brief.title ?? "");
  const [label, setLabel] = useState(brief.visible_label ?? "");
  const { upload, uploading, error: uploadError } = useUploader((added) => setRefs((current) => [...current, ...added].slice(0, 4)));
  const finalChoice = kept.find((image) => image.id === finalId) ?? kept[kept.length - 1];

  useEffect(() => {
    if (step.status !== "waiting") return;
    setApproveExtra(() => ({ final_id: finalChoice?.id, title, label }));
    return () => setApproveExtra(null);
  }, [finalChoice?.id, title, label, step.status, setApproveExtra]);

  useEffect(() => setDraft(null), [selected?.id]);

  const payload = () => ({ artifact_id: selected?.id, note, mode, references: refs.map(({ sha, role, name }) => ({ sha, role, name })) });
  const make = async (count: number) => {
    if (!selected) return;
    if (rewrite && !draft) {
      const result = await act<{ prompt: string; preview: string }>("draft_revision", payload());
      if (result) setDraft(result);
      return;
    }
    const result = await act<{ created: string[] }>("revise", { ...payload(), prompt: draft?.prompt ?? "", count });
    if (result?.created?.length) {
      setNote("");
      setDraft(null);
      setSelectedId(result.created[0]);
    }
  };
  const nextLabel = `v${images.filter((image) => image.grp === "versions").length + 1}`;

  return (
    <div className="ds-iter">
      <div className="ds-card tight">
        <h3>Versions</h3>
        <div className="ds-tree">
          {tree.map(({ item, depth }) => (
            <button key={item.id} type="button" onClick={() => setSelectedId(item.id)}
              className={`ds-node${selected?.id === item.id ? " sel" : ""}${item.verdict === "keep" ? " kept" : ""} ${item.status}`}
              style={{ marginLeft: Math.min(depth, 4) * 16, width: `calc(100% - ${Math.min(depth, 4) * 16}px)` }}>
              {item.thumb_sha ? <img src={mediaUrl(item.thumb_sha)} alt="" /> : <span className="ph">{item.status === "running" || item.status === "queued" ? <Spinner size={12} /> : item.status}</span>}
              <span style={{ minWidth: 0 }}>
                <b>{item.label}{item.verdict === "keep" ? " · kept" : ""}</b>
                <small>{item.params.note || (item.grp === "candidates" ? "candidate" : "")}{item.status === "blocked" ? " · blocked" : item.status === "failed" ? " · failed" : ""}</small>
              </span>
            </button>
          ))}
          {!tree.length && <p className="ds-small ds-muted">Keep a candidate to start iterating.</p>}
        </div>
      </div>
      <div className={`ds-iter-main${open ? "" : " solo"}`}>
      <div className="ds-card tight" style={{ minWidth: 0 }}>
        {selected ? (
          <div className="ds-stack" style={{ gap: 8 }}>
            <button type="button" className="ds-media-btn" onClick={() => openReview(selected.id)} aria-label={`Review ${selected.label} full size`}>
              <MediaPreview artifact={selected} portrait={shape.portrait} square={shape.square} />
            </button>
            <div className="ds-row between">
              <div className="ds-row ds-small">
                <b>{selected.label}</b>
                <span className="ds-muted">{selected.parent_id ? `from ${images.find((i) => i.id === selected.parent_id)?.label}` : "candidate"} · {selected.deployment} ({selected.params.operation}) · {selected.params.width}×{selected.params.height}</span>
              </div>
              {selected.status === "ready" && (
                <button type="button" className={`ds-btn sm${selected.verdict === "keep" ? " good" : ""}`} disabled={busy !== null} onClick={() => void act("decide", { artifact_id: selected.id, verdict: selected.verdict === "keep" ? null : "keep" })}>{selected.verdict === "keep" ? "Kept" : "Keep"}</button>
              )}
            </div>
            {selected.params.note && <p className="ds-small"><b>Change asked:</b> {selected.params.note}</p>}
            <div className="ds-promptbox scroll"><b>Prompt sent:</b> {selected.prompt}</div>
            {(selected.status === "failed" || selected.status === "blocked") && open && (
              <button type="button" className="ds-btn sm" style={{ justifySelf: "start" }} onClick={() => openReview(selected.id)}>Reword & retry</button>
            )}
            <Checks checks={selected.checks} />
          </div>
        ) : <p className="ds-muted">Nothing selected.</p>}
      </div>
      {open && <div className="ds-stack">
        {selected?.status === "ready" && (
          <div className="ds-card tight">
            <h3>Revise {selected.label}</h3>
            <label htmlFor="revise-note" style={{ marginTop: 0 }}>What should change?</label>
            <textarea id="revise-note" value={note} onChange={(e) => { setNote(e.target.value); setDraft(null); }} style={{ minHeight: 80 }} placeholder="e.g. lower the camera to road level; keep the car identical" />
            <label>References for this pass</label>
            <div className="ds-mini-refs">
              {mode === "edit" && <span className="ds-mini-ref"><img src={mediaUrl(selected.thumb_sha ?? selected.media_sha!)} alt="" />{selected.label} · base</span>}
              {refs.map((ref, index) => (
                <span key={ref.sha + index} className="ds-mini-ref">
                  <img src={mediaUrl(ref.thumb_sha ?? ref.sha)} alt="" />
                  <select aria-label="Reference role" value={ref.role} onChange={(e) => { setRefs(refs.map((item, i) => (i === index ? { ...item, role: e.target.value as Reference["role"] } : item))); setDraft(null); }}>
                    <option value="subject">subject</option><option value="style">style</option><option value="scene">scene</option>
                  </select>
                  <button type="button" className="ds-btn sm ghost" style={{ minHeight: 22, padding: "0 4px" }} aria-label="Remove reference" onClick={() => { setRefs(refs.filter((_, i) => i !== index)); setDraft(null); }}><Trash2 size={11} aria-hidden="true" /></button>
                </span>
              ))}
            </div>
            <div className="ds-row" style={{ marginTop: 6 }}>
              {runRefs.filter((ref) => !refs.some((item) => item.sha === ref.sha)).map((ref) => (
                <button key={ref.sha} type="button" className="ds-btn sm" onClick={() => setRefs([...refs, ref].slice(0, 4))}><Plus size={12} aria-hidden="true" /> {ref.name || "run reference"}</button>
              ))}
            </div>
            <div style={{ marginTop: 6 }}><DropZone onFiles={(files) => void upload(files)} uploading={uploading} label="Add an image" /></div>
            {uploadError && <Banner kind="error">{uploadError}</Banner>}
            <label>How</label>
            <div className="ds-seg" role="radiogroup" aria-label="Revision mode">
              <button type="button" role="radio" aria-checked={mode === "edit"} className={mode === "edit" ? "on" : ""} onClick={() => { setMode("edit"); setDraft(null); }}>Edit this version</button>
              <button type="button" role="radio" aria-checked={mode === "regenerate"} className={mode === "regenerate" ? "on" : ""} onClick={() => { setMode("regenerate"); setDraft(null); }}>Regenerate from prompt</button>
            </div>
            <label className="ds-row" style={{ fontWeight: 500 }}>
              <input type="checkbox" checked={rewrite} onChange={(e) => { setRewrite(e.target.checked); setDraft(null); }} /> Let the text model turn my note into a full prompt (shown before sending)
            </label>
            {draft && (
              <div className="ds-stack" style={{ gap: 6 }}>
                <label htmlFor="draft-prompt" style={{ margin: 0 }}>Proposed prompt (edit freely)</label>
                <textarea id="draft-prompt" value={draft.prompt} onChange={(e) => setDraft({ ...draft, prompt: e.target.value })} style={{ minHeight: 110 }} />
              </div>
            )}
            <div className="ds-row" style={{ marginTop: 10 }}>
              <button type="button" className="ds-btn primary" disabled={busy !== null || !note.trim()} onClick={() => void make(1)}>
                {busy === "draft_revision" || busy === "revise" ? <Spinner /> : <Sparkles size={14} aria-hidden="true" />}
                {rewrite && !draft ? "Write the prompt" : `Make ${nextLabel} from ${selected.label}`}
              </button>
              {(!rewrite || draft) && <button type="button" className="ds-btn" disabled={busy !== null || !note.trim()} onClick={() => void make(2)}>Variations ×2</button>}
            </div>
            <p className="ds-tiny ds-muted" style={{ marginTop: 6 }}>Each pass is one image call. Nothing is overwritten: the new version appears under {selected.label}.</p>
          </div>
        )}
        {step.status === "waiting" && (
          <div className="ds-card tight">
            <h3>Finish</h3>
            {kept.length ? (
              <>
                <label htmlFor="final-pick" style={{ marginTop: 0 }}>Final image</label>
                <select id="final-pick" value={finalChoice?.id} onChange={(e) => setFinalId(e.target.value)}>
                  {kept.map((image) => <option key={image.id} value={image.id}>{image.label}{image.params.note ? ` · ${image.params.note.slice(0, 40)}` : ""}</option>)}
                </select>
                <label htmlFor="final-title">Title (drawn by the app)</label>
                <input id="final-title" value={title} onChange={(e) => setTitle(e.target.value)} placeholder="optional" />
                <label htmlFor="final-label">Visible label</label>
                <input id="final-label" value={label} onChange={(e) => setLabel(e.target.value)} />
                <p className="ds-tiny ds-muted" style={{ marginTop: 6 }}>Use “Approve & continue” above to finish.</p>
              </>
            ) : <p className="ds-small ds-muted">Keep at least one version to finish.</p>}
          </div>
        )}
      </div>}
      </div>
    </div>
  );
}

export default function ImageRun(props: RunViewProps) {
  const { detail, act, busy } = props;
  const steps = Object.fromEntries(detail.steps.map((step) => [step.key, step]));
  const images = detail.artifacts.filter((a) => a.kind === "image" && a.status !== "superseded");
  const candidates = images.filter((a) => a.grp === "candidates");
  const final = detail.artifacts.find((a) => a.kind === "final" && a.status !== "superseded");
  const shape = shapeOf(detail.run.brief.size);
  const candidatesOpen = steps.candidates?.status === "running" || steps.candidates?.status === "waiting";

  const toVideo = () => {
    if (!final?.media_sha && !images.some((i) => i.verdict === "keep")) return;
    const source = final?.parent_id ? images.find((i) => i.id === final.parent_id) : images.filter((i) => i.verdict === "keep").pop();
    if (!source?.media_sha) return;
    const prefill: Prefill = {
      pipeline: "video",
      title: `${detail.run.title} · video`,
      references: [{ sha: source.media_sha, thumb_sha: source.thumb_sha ?? undefined, role: "subject", name: `${detail.run.title} ${source.label}` }],
      brief: { must_not_include: detail.run.brief.must_not_include, visible_label: detail.run.brief.visible_label },
      parent_run_id: detail.run.id,
      note: `Starting from ${source.label} of “${detail.run.title}” as the subject reference.`,
    };
    sessionStorage.setItem(PREFILL_KEY, JSON.stringify(prefill));
    go("/design-studio/new/video");
  };

  return (
    <div className="ds-stack">
      <section id="step-prompt" className="ds-card">
        <h3>Brief → prompt {steps.prompt?.status === "waiting" && <ReviewTag waiting />}</h3>
        <p className="ds-small ds-muted" style={{ marginBottom: 8 }}><b>Brief:</b> {detail.run.brief.brief}</p>
        <PromptStep {...props} />
      </section>
      {steps.candidates && steps.candidates.status !== "pending" && (
        <section id="step-candidates" className="ds-card">
          <div className="ds-row between" style={{ marginBottom: 8 }}>
            <h3 style={{ margin: 0 }}>Candidates {steps.candidates.status === "waiting" && <ReviewTag waiting />}</h3>
            {candidatesOpen && <button type="button" className="ds-btn sm" disabled={busy !== null} onClick={() => void act("more_candidates", { count: 2 })}><Plus size={13} aria-hidden="true" /> 2 more</button>}
          </div>
          <div className="ds-takes" style={{ gridTemplateColumns: `repeat(auto-fill, minmax(${shape.portrait ? 150 : 220}px, 1fr))` }}>
            {candidates.map((item) => <ImageCard key={item.id} item={item} act={act} busy={busy} shape={shape} onSelect={() => props.openReview(item.id)} />)}
          </div>
        </section>
      )}
      {steps.iterate && steps.iterate.status !== "pending" && (
        <section id="step-iterate">
          <IterateStep {...props} images={images} />
        </section>
      )}
      {final && (
        <section id="step-finish" className="ds-card hl">
          <div className="ds-row between" style={{ marginBottom: 8 }}>
            <h3 style={{ margin: 0 }}>Final image</h3>
            <div className="ds-row">
              {final.media_sha && <a className="ds-btn sm" href={mediaUrl(final.media_sha, `${detail.run.title.replace(/[^\w .-]+/g, "")}.png`)}><Download size={13} aria-hidden="true" /> Download</a>}
              <button type="button" className="ds-btn sm" onClick={toVideo}><Clapperboard size={13} aria-hidden="true" /> Use in a video run</button>
            </div>
          </div>
          <div className="ds-review" style={{ gridTemplateColumns: shape.portrait ? "minmax(0, 0.7fr) minmax(260px, 1fr)" : "minmax(0, 1.5fr) minmax(260px, 1fr)" }}>
            <div className="ds-player">{final.media_sha ? <img src={mediaUrl(final.media_sha)} alt="Final" /> : <MediaPreview artifact={final} />}</div>
            <div className="ds-stack">
              <p className="ds-small">From <b>{String(final.data.source_label ?? "")}</b></p>
              <Checks checks={final.checks} />
              {steps.iterate?.status === "done" && <button type="button" className="ds-btn sm" style={{ justifySelf: "start" }} onClick={() => void act("reopen", { step: "iterate" })}>Back to iterating</button>}
            </div>
          </div>
        </section>
      )}
    </div>
  );
}
