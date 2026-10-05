import { useEffect, useMemo, useRef, useState, type ReactNode } from "react";
import { FileUp, ImagePlus, Trash2, Wand2 } from "lucide-react";
import {
  designApi, errorMessage, mediaUrl, useLoad,
  type ArticleSource, type Brief, type PipelineInfo, type PipelineKey, type Reference, type Speaker, type StudioStatus, type Voice,
} from "./api";
import { Banner, Crumbs, Spinner } from "./ui";
import { PREFILL_KEY, go, useUploader, type Prefill } from "./lib";
import { STARLINER_SOURCE } from "./examples";

type RefItem = Reference & { thumb_sha?: string };

const EXAMPLES: Record<PipelineKey, { title: string; brief: Partial<Brief> }> = {
  video: {
    title: "SOLENNE GT · family drive",
    brief: {
      brief: "A 30-second ad for SOLENNE GT, a fictional luxury electric grand tourer in liquid silver. A family drive: the car on a coastal highway at sunrise, dad at the wheel, two kids laughing in the back, arriving home at dusk. Warm, cinematic, quiet confidence.",
      must_not_include: "real car brands or logos, readable license plates, copyrighted music",
      visible_label: "Fictional vehicle. Made with AI.",
      end_title: "SOLENNE GT",
      end_tagline: "Drive the quiet.",
    },
  },
  image: {
    title: "SOLENNE GT · campaign poster",
    brief: {
      use_case: "poster",
      brief: "Vertical campaign poster for SOLENNE GT, a fictional luxury electric grand tourer. The exact car from the design sheet on a wet coastal road at blue hour, city lights far away, sea mist. Premium and cinematic.",
      must_not_include: "real car brands or logos, readable license plates, people",
      title: "SOLENNE GT",
      visible_label: "Fictional vehicle. Made with AI.",
    },
  },
  article: {
    title: "Starliner update · newsroom summary",
    brief: {
      format: "news-summary",
      brief: "Summarize this NASA release for community college students: what changed, what flies next and when. Plain words, no hype.",
      audience: "community college students",
      target_words: 150,
      sources: [STARLINER_SOURCE],
      visible_label: "AI-assisted summary, reviewed by an editor.",
    },
  },
  voice: {
    title: "Module 8 welcome · two hosts",
    brief: {
      format: "two-hosts",
      brief: "Open Module 8 of an applied AI course: AI in media, content and creative industries. Tonight students watch a car ad get made with Sora and a newsroom summary get fact-checked, and decide where a human has to sign off. Upbeat and warm.",
      target_seconds: 35,
    },
  },
};

const VIDEO_DEFAULTS: Brief = {
  brief: "", shots: 4, seconds: 8, takes_per_shot: 3, size: "1280x720", must_not_include: "", visible_label: "Made with AI",
  end_title: "", end_tagline: "", voiceover: "", voice: "", references: [],
};
const IMAGE_DEFAULTS: Brief = {
  brief: "", use_case: "hero", size: "1536x864", candidates: 4, prompt_helper: true, must_not_include: "", title: "",
  visible_label: "Made with AI", references: [],
};
const VOICE_DEFAULTS: Brief = {
  brief: "", format: "two-hosts", target_seconds: 45, locale: "en-US", pause_ms: 350, disclosure: true, speakers: [],
};
const ARTICLE_DEFAULTS: Brief = {
  brief: "", format: "news-summary", audience: "general readers", tone: "clear, neutral, specific", target_words: 250,
  sources: [], must_not_include: "", fact_check: true, visible_label: "AI-assisted draft, reviewed by an editor.",
};
const DEFAULTS: Record<PipelineKey, Brief> = { video: VIDEO_DEFAULTS, image: IMAGE_DEFAULTS, voice: VOICE_DEFAULTS, article: ARTICLE_DEFAULTS };

function Field({ label, children, hint }: { label: ReactNode; children: ReactNode; hint?: string }) {
  return (
    <div>
      <label>{label}</label>
      {children}
      {hint && <div className="ds-tiny ds-muted" style={{ marginTop: 4 }}>{hint}</div>}
    </div>
  );
}

export function DropZone({ onFiles, uploading, label }: { onFiles: (files: FileList) => void; uploading: boolean; label: string }) {
  const input = useRef<HTMLInputElement>(null);
  const [over, setOver] = useState(false);
  return (
    <>
      <button
        type="button"
        className={`ds-drop${over ? " over" : ""}`}
        onClick={() => input.current?.click()}
        onDragOver={(event) => { event.preventDefault(); setOver(true); }}
        onDragLeave={() => setOver(false)}
        onDrop={(event) => { event.preventDefault(); setOver(false); if (event.dataTransfer.files.length) onFiles(event.dataTransfer.files); }}
      >
        {uploading ? <><Spinner /> Uploading…</> : <><ImagePlus size={15} aria-hidden="true" style={{ verticalAlign: "-3px" }} /> {label}</>}
      </button>
      <input ref={input} type="file" accept="image/png,image/jpeg,image/webp" multiple hidden onChange={(event) => { if (event.target.files) onFiles(event.target.files); event.target.value = ""; }} />
    </>
  );
}

function ReferenceList({ refs, onChange, max = 5, roles = true }: { refs: RefItem[]; onChange: (refs: RefItem[]) => void; max?: number; roles?: boolean }) {
  const { upload, uploading, error } = useUploader((added) => onChange([...refs, ...added].slice(0, max)));
  useEffect(() => {
    const onPaste = (event: ClipboardEvent) => {
      const files = Array.from(event.clipboardData?.files ?? []);
      if (files.length) void upload(files);
    };
    window.addEventListener("paste", onPaste);
    return () => window.removeEventListener("paste", onPaste);
  });
  return (
    <div className="ds-refs">
      {refs.map((ref, index) => (
        <div className="ds-ref" key={ref.sha + index}>
          <img src={mediaUrl(ref.thumb_sha ?? ref.sha)} alt="" />
          <div style={{ minWidth: 0 }}>
            <b className="ds-small" style={{ display: "block", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{ref.name || `reference ${index + 1}`}</b>
            <div className="ds-tiny ds-muted">image {index + 1}</div>
          </div>
          {roles ? (
            <div className="ds-seg" role="radiogroup" aria-label={`Role of ${ref.name}`}>
              {(["subject", "style", "scene"] as const).map((role) => (
                <button key={role} type="button" role="radio" aria-checked={ref.role === role} className={ref.role === role ? "on" : ""}
                  onClick={() => onChange(refs.map((item, i) => (i === index ? { ...item, role } : item)))}>
                  {role[0].toUpperCase() + role.slice(1)}
                </button>
              ))}
            </div>
          ) : <span />}
          <button type="button" className="ds-btn sm ghost" aria-label={`Remove ${ref.name}`} onClick={() => onChange(refs.filter((_, i) => i !== index))}>
            <Trash2 size={13} aria-hidden="true" />
          </button>
        </div>
      ))}
      {refs.length < max && <DropZone uploading={uploading} onFiles={(files) => void upload(files)} label={`Drop, paste or choose images (up to ${max})`} />}
      {error && <Banner kind="error">{error}</Banner>}
    </div>
  );
}

function VideoForm({ brief, set, voices }: { brief: Brief; set: (patch: Partial<Brief>) => void; voices: Voice[] }) {
  return (
    <>
      <Field label="Brief" hint="What is it for, who is in it, what happens, the mood. The text model turns this into shots you approve before any video is generated.">
        <textarea value={brief.brief} onChange={(e) => set({ brief: e.target.value })} style={{ minHeight: 120 }} placeholder="A 30-second ad for…" />
      </Field>
      <div className="ds-grid4">
        <Field label="Shots"><select value={brief.shots} onChange={(e) => set({ shots: Number(e.target.value) })}>{[1, 2, 3, 4, 5, 6, 7, 8].map((n) => <option key={n}>{n}</option>)}</select></Field>
        <Field label="Seconds per shot"><select value={brief.seconds} onChange={(e) => set({ seconds: Number(e.target.value) })}>{[4, 8, 12].map((n) => <option key={n} value={n}>{n} s</option>)}</select></Field>
        <Field label="Takes per shot"><select value={brief.takes_per_shot} onChange={(e) => set({ takes_per_shot: Number(e.target.value) })}>{[1, 2, 3, 4].map((n) => <option key={n}>{n}</option>)}</select></Field>
        <Field label="Frame"><select value={brief.size} onChange={(e) => set({ size: e.target.value })}><option value="1280x720">16:9 · 1280×720</option><option value="720x1280">9:16 · 720×1280</option></select></Field>
      </div>
      <Field label="Must not include" hint="Goes into every prompt and onto the review checklist.">
        <input value={brief.must_not_include} onChange={(e) => set({ must_not_include: e.target.value })} placeholder="real car brands or logos, readable license plates" />
      </Field>
      <div className="ds-grid3">
        <Field label="Visible label"><input value={brief.visible_label} onChange={(e) => set({ visible_label: e.target.value })} /></Field>
        <Field label="End card title"><input value={brief.end_title} onChange={(e) => set({ end_title: e.target.value })} placeholder="optional" /></Field>
        <Field label="End card tagline"><input value={brief.end_tagline} onChange={(e) => set({ end_tagline: e.target.value })} placeholder="optional" /></Field>
      </div>
      <Field label="Voiceover (optional)" hint="Read by MAI-Voice and mixed over the cut.">
        <textarea value={brief.voiceover} onChange={(e) => set({ voiceover: e.target.value })} style={{ minHeight: 60 }} placeholder="Leave empty for music and sound from the takes only." />
      </Field>
      {brief.voiceover?.trim() && (
        <Field label="Voiceover voice">
          <select value={brief.voice} onChange={(e) => set({ voice: e.target.value })}>
            <option value="">Default ({voices[0]?.display ?? "first available"})</option>
            {voices.map((voice) => <option key={voice.name} value={voice.name}>{voice.display} · {voice.locale} · {voice.gender}</option>)}
          </select>
        </Field>
      )}
    </>
  );
}

function ImageForm({ brief, set, info }: { brief: Brief; set: (patch: Partial<Brief>) => void; info: PipelineInfo }) {
  const useCases = info.use_cases ?? {};
  return (
    <>
      <Field label="Use case" hint="Sets the default size and the review checklist.">
        <select value={brief.use_case} onChange={(e) => set({ use_case: e.target.value, size: useCases[e.target.value]?.size ?? brief.size })}>
          {Object.entries(useCases).map(([key, value]) => <option key={key} value={key}>{value.title}</option>)}
        </select>
      </Field>
      <Field label="Brief" hint="What the image is for and what should be in it.">
        <textarea value={brief.brief} onChange={(e) => set({ brief: e.target.value })} style={{ minHeight: 110 }} placeholder="Hero studio shot of…" />
      </Field>
      <Field label="Must not include"><input value={brief.must_not_include} onChange={(e) => set({ must_not_include: e.target.value })} placeholder="real brands or logos, real people's faces" /></Field>
      <div className="ds-grid3">
        <Field label="Size">
          <select value={brief.size} onChange={(e) => set({ size: e.target.value })}>
            <option value="1536x864">16:9 · 1536×864</option><option value="1024x1024">1:1 · 1024×1024</option><option value="864x1536">9:16 · 864×1536</option>
          </select>
        </Field>
        <Field label="Candidates"><select value={brief.candidates} onChange={(e) => set({ candidates: Number(e.target.value) })}>{[1, 2, 3, 4, 5, 6].map((n) => <option key={n}>{n}</option>)}</select></Field>
        <Field label="Prompt helper">
          <select value={brief.prompt_helper ? "on" : "off"} onChange={(e) => set({ prompt_helper: e.target.value === "on" })}>
            <option value="on">Text model expands the brief</option><option value="off">Off: send my words as-is</option>
          </select>
        </Field>
      </div>
      <div className="ds-grid2">
        <Field label="Title on the final image" hint="Drawn by the app, so spelling is exact."><input value={brief.title} onChange={(e) => set({ title: e.target.value })} placeholder="optional" /></Field>
        <Field label="Visible label"><input value={brief.visible_label} onChange={(e) => set({ visible_label: e.target.value })} /></Field>
      </div>
    </>
  );
}

const LOCALE_NAMES: Record<string, string> = { "en-US": "English (US)", "es-MX": "Spanish (Mexico)", "es-ES": "Spanish (Spain)", "zh-CN": "Chinese (Mandarin)", "fr-FR": "French", "de-DE": "German", "pt-BR": "Portuguese (Brazil)", "ja-JP": "Japanese", "en-GB": "English (UK)", "en-AU": "English (Australia)" };

function VoiceForm({ brief, set, voices }: { brief: Brief; set: (patch: Partial<Brief>) => void; voices: Voice[] }) {
  const locales = useMemo(() => Array.from(new Set(voices.map((voice) => voice.locale))).sort(), [voices]);
  const localVoices = voices.filter((voice) => voice.locale === brief.locale);
  const speakers = brief.speakers ?? [];
  const setSpeaker = (index: number, patch: Partial<Speaker>) => set({ speakers: speakers.map((s, i) => (i === index ? { ...s, ...patch } : s)) });
  return (
    <>
      <div className="ds-grid3">
        <Field label="Format">
          <select value={brief.format} onChange={(e) => set({ format: e.target.value })}>
            <option value="two-hosts">Two hosts</option><option value="narration">Narration</option><option value="ad-read">Ad read</option><option value="interview">Interview</option>
          </select>
        </Field>
        <Field label="Target length">
          <select value={brief.target_seconds} onChange={(e) => set({ target_seconds: Number(e.target.value) })}>{[15, 30, 35, 45, 60, 90, 120].map((n) => <option key={n} value={n}>{n} s</option>)}</select>
        </Field>
        <Field label="Language">
          <select value={brief.locale} onChange={(e) => {
            const locale = e.target.value;
            const options = voices.filter((voice) => voice.locale === locale);
            set({ locale, speakers: speakers.map((s, i) => ({ ...s, voice: options[i % Math.max(options.length, 1)]?.name ?? s.voice, style: "" })) });
          }}>
            {locales.map((locale) => <option key={locale} value={locale}>{LOCALE_NAMES[locale] ?? locale}</option>)}
          </select>
        </Field>
      </div>
      <Field label="Brief" hint="Topic, audience, key points and tone. The script comes back for you to edit before anything is recorded.">
        <textarea value={brief.brief} onChange={(e) => set({ brief: e.target.value })} style={{ minHeight: 100 }} />
      </Field>
      <label>Speakers</label>
      <div className="ds-stack" style={{ gap: 8 }}>
        {speakers.map((speaker, index) => {
          const voice = voices.find((item) => item.name === speaker.voice);
          return (
            <div key={index} className="ds-grid4" style={{ gridTemplateColumns: "1fr 1.4fr 1fr auto", alignItems: "center" }}>
              <input aria-label={`Speaker ${index + 1} name`} value={speaker.name} onChange={(e) => setSpeaker(index, { name: e.target.value })} />
              <select aria-label={`Speaker ${index + 1} voice`} value={speaker.voice} onChange={(e) => setSpeaker(index, { voice: e.target.value, style: "" })}>
                {localVoices.map((item) => <option key={item.name} value={item.name}>{item.display} · {item.gender}</option>)}
              </select>
              <select aria-label={`Speaker ${index + 1} default style`} value={speaker.style} onChange={(e) => setSpeaker(index, { style: e.target.value })} disabled={!voice?.styles.length}>
                <option value="">{voice?.styles.length ? "Default style" : "No styles"}</option>
                {voice?.styles.map((style) => <option key={style}>{style}</option>)}
              </select>
              <button type="button" className="ds-btn sm ghost" aria-label="Remove speaker" disabled={speakers.length <= 1} onClick={() => set({ speakers: speakers.filter((_, i) => i !== index) })}><Trash2 size={13} aria-hidden="true" /></button>
            </div>
          );
        })}
        {speakers.length < 4 && localVoices.length > 0 && (
          <button type="button" className="ds-btn sm" style={{ justifySelf: "start" }} onClick={() => set({ speakers: [...speakers, { name: `Speaker ${speakers.length + 1}`, voice: localVoices[speakers.length % localVoices.length].name, style: "" }] })}>+ Add speaker</button>
        )}
      </div>
      <div className="ds-grid2">
        <Field label="Pause between lines"><select value={brief.pause_ms} onChange={(e) => set({ pause_ms: Number(e.target.value) })}>{[200, 300, 350, 500, 800].map((n) => <option key={n} value={n}>{n} ms</option>)}</select></Field>
        <Field label="Disclosure">
          <label className="ds-row" style={{ margin: "8px 0 0", fontWeight: 500 }}>
            <input type="checkbox" checked={brief.disclosure} onChange={(e) => set({ disclosure: e.target.checked })} /> End with a spoken "these voices are AI-generated" line
          </label>
        </Field>
      </div>
    </>
  );
}

function ArticleForm({ brief, set }: { brief: Brief; set: (patch: Partial<Brief>) => void }) {
  const sources = brief.sources ?? [];
  const fileInput = useRef<HTMLInputElement>(null);
  const setSource = (index: number, patch: Partial<ArticleSource>) => set({ sources: sources.map((s, i) => (i === index ? { ...s, ...patch } : s)) });
  const addFiles = async (files: FileList) => {
    const added: ArticleSource[] = [];
    for (const file of Array.from(files)) {
      const text = (await file.text()).slice(0, 30000);
      added.push({ title: file.name.replace(/\.(txt|md)$/i, ""), text, url: "", published: "" });
    }
    set({ sources: [...sources, ...added].slice(0, 8) });
  };
  return (
    <>
      <div className="ds-grid3">
        <Field label="Format">
          <select value={brief.format} onChange={(e) => set({ format: e.target.value })}>
            <option value="news-summary">Newsroom summary</option><option value="report">Report</option><option value="explainer">Explainer</option><option value="blog">Blog post</option><option value="press-release">Press release</option>
          </select>
        </Field>
        <Field label="Length"><select value={brief.target_words} onChange={(e) => set({ target_words: Number(e.target.value) })}>{[80, 150, 250, 400, 600, 900, 1200].map((n) => <option key={n} value={n}>about {n} words</option>)}</select></Field>
        <Field label="Fact check">
          <select value={brief.fact_check ? "on" : "off"} onChange={(e) => set({ fact_check: e.target.value === "on" })}>
            <option value="on">Second model checks claims</option><option value="off">Off</option>
          </select>
        </Field>
      </div>
      <Field label="Brief" hint="What to write, for whom, what to focus on.">
        <textarea value={brief.brief} onChange={(e) => set({ brief: e.target.value })} style={{ minHeight: 90 }} placeholder="Summarize this release for…" />
      </Field>
      <div className="ds-grid2">
        <Field label="Audience"><input value={brief.audience} onChange={(e) => set({ audience: e.target.value })} /></Field>
        <Field label="Tone"><input value={brief.tone} onChange={(e) => set({ tone: e.target.value })} /></Field>
      </div>
      <label>Sources ({sources.length} of 8) · the draft may only use facts from these</label>
      <div className="ds-stack" style={{ gap: 10 }}>
        {sources.map((source, index) => (
          <div key={index} className="ds-shot-edit">
            <div className="head">
              <b className="ds-mono">[{index + 1}]</b>
              <input aria-label={`Source ${index + 1} title`} value={source.title} onChange={(e) => setSource(index, { title: e.target.value })} style={{ flex: 1 }} />
              <button type="button" className="ds-btn sm ghost" aria-label={`Remove source ${index + 1}`} onClick={() => set({ sources: sources.filter((_, i) => i !== index) })}><Trash2 size={13} aria-hidden="true" /></button>
            </div>
            <div className="ds-grid2">
              <input aria-label={`Source ${index + 1} URL`} value={source.url} onChange={(e) => setSource(index, { url: e.target.value })} placeholder="URL (for the citation)" />
              <input aria-label={`Source ${index + 1} published`} value={source.published} onChange={(e) => setSource(index, { published: e.target.value })} placeholder="Published (e.g. 2026-09-28): resolves “this year”" />
            </div>
            <textarea aria-label={`Source ${index + 1} text`} value={source.text} onChange={(e) => setSource(index, { text: e.target.value })} style={{ minHeight: 90 }} placeholder="Paste the source text" />
            <span className="ds-tiny ds-muted">{source.text.split(/\s+/).filter(Boolean).length} words</span>
          </div>
        ))}
        {sources.length < 8 && (
          <div className="ds-row">
            <button type="button" className="ds-btn sm" onClick={() => set({ sources: [...sources, { title: `Source ${sources.length + 1}`, text: "", url: "", published: "" }] })}>+ Paste a source</button>
            <button type="button" className="ds-btn sm" onClick={() => fileInput.current?.click()}><FileUp size={13} aria-hidden="true" /> Add .txt or .md files</button>
            <input ref={fileInput} type="file" accept=".txt,.md,text/plain,text/markdown" multiple hidden onChange={(e) => { if (e.target.files) void addFiles(e.target.files); e.target.value = ""; }} />
          </div>
        )}
      </div>
      <div className="ds-grid2">
        <Field label="Must not include" hint="Checked by exact phrase search on every version."><input value={brief.must_not_include} onChange={(e) => set({ must_not_include: e.target.value })} /></Field>
        <Field label="Disclosure label"><input value={brief.visible_label} onChange={(e) => set({ visible_label: e.target.value })} /></Field>
      </div>
    </>
  );
}

function Preview({ info, status, brief, pipeline, onStart, busy, canStart }: {
  info: PipelineInfo; status: StudioStatus | null; brief: Brief; pipeline: PipelineKey; onStart: () => void; busy: boolean; canStart: boolean;
}) {
  const [estimate, setEstimate] = useState<Record<string, number | string> | null>(null);
  const [problem, setProblem] = useState<string | null>(null);
  const key = JSON.stringify(brief);
  const longEnough = brief.brief.trim().length >= (pipeline === "image" || pipeline === "article" ? 10 : 20);
  useEffect(() => {
    if (!longEnough) {
      setProblem(null);
      return;
    }
    const timer = window.setTimeout(async () => {
      try {
        const result = await designApi.estimate(pipeline, brief);
        setEstimate(result.estimate);
        setProblem(null);
      } catch (error) {
        setEstimate(null);
        setProblem(errorMessage(error));
      }
    }, 400);
    return () => window.clearTimeout(timer);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [key, pipeline, longEnough]);
  const roleModel = (role: string | null) => status?.roles.find((item) => item.role === role)?.model;
  const kpis: Array<[string, string]> = [];
  if (estimate) {
    if (pipeline === "video") kpis.push([String(estimate.video_generations), "video generations"], [`${estimate.video_seconds} s`, "video generated (billed)"], [`~${estimate.minutes} min`, "for the takes"]);
    if (pipeline === "image") kpis.push([String(estimate.image_calls), "image calls to start"], [`~${estimate.minutes} min`, "for candidates"]);
    if (pipeline === "voice") kpis.push([`~${estimate.voice_calls}`, "lines to record"], [`~${estimate.minutes} min`, "to record"]);
    if (pipeline === "article") kpis.push([String(estimate.text_calls), "text calls per version"], [`~${estimate.minutes} min`, "to the first draft"]);
  }
  const cap = pipeline === "video" ? status?.caps.video : pipeline === "image" ? status?.caps.image : pipeline === "voice" ? status?.caps.voice : status?.caps.text;
  const retire = pipeline === "video" ? status?.video_retirement : null;
  return (
    <div className="ds-card ds-ws-side" style={{ position: "sticky", top: 14 }}>
      <h3>Pipeline preview</h3>
      <div className="ds-stepper">
        {info.steps.map((step, index) => (
          <div key={step.key} className="ds-st pending">
            <span className="n">{index + 1}</span>
            <div>
              <b style={{ color: "var(--text)" }}>{step.title}{step.gate ? " ✋" : ""}</b>
              <small>
                {step.role && roleModel(step.role) ? <span className="ds-chip model" style={{ marginRight: 6 }}>{roleModel(step.role)}</span> : null}
                {step.description}
              </small>
            </div>
          </div>
        ))}
      </div>
      {kpis.length > 0 && (
        <div className="ds-grid3" style={{ marginTop: 8 }}>
          {kpis.map(([value, label]) => <div key={label} className="ds-kpi"><b>{value}</b><span>{label}</span></div>)}
        </div>
      )}
      {estimate?.basis && <p className="ds-tiny ds-muted">{String(estimate.basis)}</p>}
      <div className="ds-row">
        {retire && <span className="ds-chip warn">Sora 2 (2025-12-08) retires {retire.on}</span>}
        {cap && <span className="ds-chip info">Daily cap: {cap.used} of {cap.cap} {cap.label.toLowerCase()} used</span>}
      </div>
      {problem && <Banner kind="warn">{problem}</Banner>}
      <div className="ds-row">
        <button type="button" className="ds-btn primary" disabled={busy || !canStart || Boolean(problem)} onClick={onStart}>
          {busy ? <Spinner /> : null} Start run
        </button>
        <span className="ds-tiny ds-muted">Nothing expensive runs before the first ✋ review.</span>
      </div>
    </div>
  );
}

export default function NewRunPage({ pipeline: rawPipeline, forkOf }: { pipeline: string; forkOf: string | null }) {
  const pipeline: PipelineKey = rawPipeline === "image" || rawPipeline === "voice" || rawPipeline === "article" ? rawPipeline : "video";
  const pipelines = useLoad(designApi.pipelines, "pipelines");
  const status = useLoad(designApi.status, "status");
  const voices = useLoad(() => designApi.voices(), "voices");
  const [brief, setBrief] = useState<Brief>({ ...DEFAULTS[pipeline] });
  const [refs, setRefs] = useState<RefItem[]>([]);
  const [title, setTitle] = useState("");
  const [tags, setTags] = useState("");
  const [parent, setParent] = useState<string | null>(null);
  const [note, setNote] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const info = pipelines.data?.find((item) => item.key === pipeline);
  const set = (patch: Partial<Brief>) => setBrief((current) => ({ ...current, ...patch }));

  useEffect(() => {
    const raw = sessionStorage.getItem(PREFILL_KEY);
    if (raw) {
      sessionStorage.removeItem(PREFILL_KEY);
      try {
        const prefill = JSON.parse(raw) as Prefill;
        if (prefill.pipeline === pipeline) {
          setBrief((current) => ({ ...current, ...prefill.brief }));
          setRefs(prefill.references ?? []);
          if (prefill.title) setTitle(prefill.title);
          if (prefill.parent_run_id) setParent(prefill.parent_run_id);
          if (prefill.note) setNote(prefill.note);
        }
      } catch {
        // ignore a damaged handoff
      }
    }
    if (!forkOf) return;
    designApi.run(forkOf).then((detail) => {
      const source = detail.run;
      setBrief({ ...DEFAULTS[pipeline], ...source.brief });
      const references = detail.artifacts.filter((a) => a.kind === "reference" && a.media_sha).map((a) => ({
        sha: a.media_sha!, thumb_sha: a.thumb_sha ?? undefined, role: (a.data.role as Reference["role"]) ?? "subject", name: a.label ?? "",
      }));
      setRefs(references);
      setTitle(`${source.title} (fork)`);
      setTags(source.tags.join(", "));
      setParent(source.id);
      setNote(`Forked from “${source.title}”. Change anything, then start.`);
    }).catch((problem) => setError(errorMessage(problem)));
  }, [forkOf, pipeline]);

  useEffect(() => {
    if (pipeline !== "voice" || !voices.data || (brief.speakers ?? []).length) return;
    const local = voices.data.filter((voice) => voice.locale === (brief.locale ?? "en-US"));
    const pick = (name: string, fallback: number) => local.find((voice) => voice.display === name) ?? local[fallback];
    const first = pick("Harper", 0);
    const second = pick("Ethan", 1);
    if (first) set({ speakers: [{ name: first.display, voice: first.name, style: "" }, ...(second ? [{ name: second.display, voice: second.name, style: "" }] : [])] });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [voices.data, pipeline]);

  const fullBrief: Brief = pipeline === "voice" || pipeline === "article" ? brief : { ...brief, references: refs.map(({ sha, role, name }) => ({ sha, role, name })) };
  const ready = status.data?.pipelines.find((item) => item.key === pipeline)?.ready ?? false;
  const canStart = ready && brief.brief.trim().length >= (pipeline === "image" || pipeline === "article" ? 10 : 20)
    && (pipeline !== "article" || ((brief.sources ?? []).length > 0 && (brief.sources ?? []).every((s) => s.title.trim() && s.text.trim().length >= 40)));

  const start = async () => {
    setBusy(true);
    setError(null);
    try {
      const detail = await designApi.create({
        pipeline, brief: fullBrief, title: title.trim() || undefined, parent_run_id: parent ?? undefined,
        tags: tags.split(",").map((tag) => tag.trim()).filter(Boolean),
      });
      go(`/design-studio/runs/${detail.run.id}`);
    } catch (problem) {
      setError(errorMessage(problem));
      setBusy(false);
    }
  };

  const loadExample = () => {
    const example = EXAMPLES[pipeline];
    setTitle(example.title);
    set(example.brief);
    if (!tags) setTags("example");
  };

  return (
    <div className="page ds">
      <Crumbs items={[{ label: "Design Studio", to: "/design-studio" }, { label: info?.title ?? pipeline }, { label: "New run" }]} />
      <header className="ds-head">
        <div>
          <h1>New {pipeline} run</h1>
          <p className="ds-sub">
            {pipeline === "video" && "Write the brief once. The pipeline turns it into a shot list for you to approve before any video is generated."}
            {pipeline === "image" && "Say what the image is for, give it references, and set the rules. Candidates come back for you to pick; then you iterate from the pick."}
            {pipeline === "voice" && "Describe the piece and cast the voices. The script comes back for you to edit, then each line is recorded and checked."}
            {pipeline === "article" && "Give it a brief and the sources. You approve the outline, then every draft is fact-checked against the sources by a second model before you approve one."}
          </p>
        </div>
        <div className="ds-head-actions">
          <button type="button" className="ds-btn" onClick={loadExample}><Wand2 size={14} aria-hidden="true" /> Load example</button>
        </div>
      </header>
      {note && <div style={{ marginBottom: 12 }}><Banner kind="info">{note}</Banner></div>}
      {error && <div style={{ marginBottom: 12 }}><Banner kind="error">{error}</Banner></div>}
      {status.data && !ready && <div style={{ marginBottom: 12 }}><Banner kind="warn">This install has no model for this pipeline yet. Open Settings to see what's missing.</Banner></div>}
      {!info ? (
        pipelines.error ? <Banner kind="error">{pipelines.error}</Banner> : <div className="route-loading">Loading…</div>
      ) : (
        <div className="ds-grid2" style={{ gridTemplateColumns: "minmax(0, 1.2fr) minmax(320px, 0.8fr)", alignItems: "start" }}>
          <section className="ds-card">
            <div className="ds-grid2">
              <Field label="Run title"><input value={title} onChange={(e) => setTitle(e.target.value)} placeholder="Shown in run history" /></Field>
              <Field label="Tags" hint="Comma separated, e.g. Module 8, example"><input value={tags} onChange={(e) => setTags(e.target.value)} /></Field>
            </div>
            {pipeline === "video" && <VideoForm brief={brief} set={set} voices={voices.data ?? []} />}
            {pipeline === "image" && <ImageForm brief={brief} set={set} info={info} />}
            {pipeline === "voice" && <VoiceForm brief={brief} set={set} voices={voices.data ?? []} />}
            {pipeline === "article" && <ArticleForm brief={brief} set={set} />}
            {(pipeline === "video" || pipeline === "image") && (
              <>
                <label>Reference images {pipeline === "video" ? "(optional: the product or design sheet)" : "(optional)"}</label>
                <ReferenceList refs={refs} onChange={setRefs} />
                <p className="ds-tiny ds-muted" style={{ marginTop: 8 }}>
                  {pipeline === "video"
                    ? "Product and scene shots start from keyframes edited from these images. Sora rejects input images that contain human faces, so shots with people are made from text."
                    : "Subject = keep this thing the same · Style = borrow the look · Scene = put the subject here. Images of real people need their consent."}
                </p>
              </>
            )}
          </section>
          <Preview info={info} status={status.data} brief={fullBrief} pipeline={pipeline} onStart={() => void start()} busy={busy} canStart={canStart} />
        </div>
      )}
    </div>
  );
}
