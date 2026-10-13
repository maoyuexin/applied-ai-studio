import { Bot, Lock, X } from "lucide-react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import type { Selection } from "./WorkflowCanvas";
import { stepColor } from "./replay";
import type { Run, ScenarioSpec } from "./types";

const PATTERN_INFO: Record<string, { what: string; when: string; cost: string }> = {
  single: {
    what: "One agent runs a loop: read, decide, call a tool, read the result, decide again.",
    when: "Start here. Add agents only when one agent has too many tools or mixed roles.",
    cost: "Fewest model calls; easiest to test and explain.",
  },
  sequential: {
    what: "Agents work in a fixed order, like an assembly line. Each step passes its output to the next.",
    when: "The steps are known in advance and always happen in the same order.",
    cost: "One pass through the line; plain-code steps cost nothing.",
  },
  handoff: {
    what: "Agents pass ownership of the task to each other. Whoever holds it decides who goes next.",
    when: "Who should act next depends on what the current agent finds, for example a failed test.",
    cost: "Every hop adds model calls; loops need turn limits.",
  },
  group_chat: {
    what: "A chair picks who speaks next. Everyone sees the whole conversation.",
    when: "Work that improves through review and debate, such as copy or plans.",
    cost: "Most model calls: the chair thinks before every turn and context grows each round.",
  },
  concurrent: {
    what: "Several agents work on the same input at the same time; a final step combines their answers.",
    when: "Independent perspectives you want quickly.",
    cost: "Many calls at once; fast but not cheap.",
  },
};

export function Inspector({
  scenario,
  selection,
  model,
  onClose,
}: {
  scenario: ScenarioSpec;
  selection: Selection;
  model?: string | null;
  onClose: () => void;
}) {
  if (!selection) return null;
  const agent = selection.kind === "agent" ? scenario.agents.find((item) => item.id === selection.id) : undefined;
  const tool = selection.kind === "tool" ? scenario.tools.find((item) => item.id === selection.id) : undefined;
  const node = selection.kind === "node" ? scenario.nodes.find((item) => item.id === selection.id) : undefined;
  const owners = tool ? scenario.agents.filter((item) => item.tools.includes(tool.id)).map((item) => item.label) : [];
  return (
    <aside className="aw-inspector" aria-label="Details">
      <button type="button" className="aw-icon-button aw-inspector-close" onClick={onClose} aria-label="Close details">
        <X size={16} />
      </button>
      {agent ? (
        <>
          <p className="aw-eyebrow">{agent.kind === "chair" ? "Chair agent" : "Agent"} = model + instructions + tools</p>
          <h3 style={{ color: agent.color }}>
            <Bot size={16} /> {agent.label}
          </h3>
          <p>{agent.role}</p>
          <dl className="aw-facts">
            <dt>Model</dt>
            <dd>{model ?? "Configured language model"}</dd>
            <dt>Tools</dt>
            <dd>
              {agent.tools.length ? (
                <ul>
                  {agent.tools.map((id) => {
                    const spec = scenario.tools.find((item) => item.id === id);
                    return (
                      <li key={id}>
                        <strong style={{ color: stepColor(spec?.step) }}>{spec?.label ?? id}</strong>
                        {spec?.approval ? (
                          <span className="aw-pill">
                            <Lock size={10} /> needs approval
                          </span>
                        ) : null}
                        <br />
                        <small>{spec?.description}</small>
                      </li>
                    );
                  })}
                </ul>
              ) : agent.kind === "chair" ? (
                "None. It only decides who speaks next."
              ) : (
                "None. It only reads the conversation and writes."
              )}
            </dd>
          </dl>
          <p className="aw-eyebrow">Instructions</p>
          <pre className="aw-instructions">{agent.instructions}</pre>
        </>
      ) : null}
      {tool ? (
        <>
          <p className="aw-eyebrow">Tool · {tool.kind}</p>
          <h3 style={{ color: stepColor(tool.step) }}>{tool.label}</h3>
          <p>{tool.description}</p>
          <dl className="aw-facts">
            <dt>Five-step role</dt>
            <dd style={{ textTransform: "capitalize" }}>{tool.step}</dd>
            <dt>What is behind it</dt>
            <dd>{tool.source}</dd>
            <dt>Used by</dt>
            <dd>{owners.join(", ")}</dd>
            <dt>Approval</dt>
            <dd>{tool.approval ? "A person must approve every call." : "Runs without approval (read-only or checks)."}</dd>
          </dl>
          <p className="aw-eyebrow">Name the model sees</p>
          <code>{tool.id}</code>
        </>
      ) : null}
      {node ? (
        <>
          <p className="aw-eyebrow">{node.kind === "human" ? "Person" : node.kind === "code" ? "Plain code step" : node.kind}</p>
          <h3>{node.label}</h3>
          <p>{node.detail}</p>
          {node.kind === "code" ? <p className="aw-note">No model is involved here. If a function can do the job, it should.</p> : null}
        </>
      ) : null}
    </aside>
  );
}

export function ResultPanel({ scenario, run, finished }: { scenario: ScenarioSpec; run: Run | null; finished: boolean }) {
  if (!run) return <p className="aw-empty">Choose a run to see its result.</p>;
  if (!finished) return <p className="aw-empty">The result appears when the run finishes.</p>;
  const result = run.result ?? {};
  const stats = run.stats;
  return (
    <div className="aw-result">
      <h3>{result.headline ?? run.status}</h3>
      {result.fields?.length ? (
        <dl className="aw-facts">
          {result.fields.map((field) => (
            <div key={field.label}>
              <dt>{field.label}</dt>
              <dd>{field.value}</dd>
            </div>
          ))}
        </dl>
      ) : null}
      {result.code ? (
        <>
          <p className="aw-eyebrow">Final code</p>
          <pre className="aw-code">{result.code}</pre>
        </>
      ) : null}
      {result.document ? (
        <>
          <p className="aw-eyebrow">Document</p>
          <pre>{JSON.stringify(result.document, null, 2)}</pre>
        </>
      ) : null}
      {result.copy ? (
        <>
          <p className="aw-eyebrow">Final copy</p>
          <div className="aw-markdown aw-copy">
            <ReactMarkdown remarkPlugins={[remarkGfm]}>{result.copy}</ReactMarkdown>
          </div>
        </>
      ) : null}
      {result.final ? (
        <>
          <p className="aw-eyebrow">Last word</p>
          <div className="aw-markdown">
            <ReactMarkdown remarkPlugins={[remarkGfm]}>{result.final}</ReactMarkdown>
          </div>
        </>
      ) : null}
      <p className="aw-eyebrow">Actions that went through</p>
      {result.outbox?.length ? (
        <pre>{JSON.stringify(result.outbox, null, 2)}</pre>
      ) : (
        <p className="aw-note">None. Every action needs approval, and nothing reaches a real system.</p>
      )}
      {run.task.truth ? (
        <div className="aw-truth">
          <p className="aw-eyebrow">What actually happened (hidden from the agents)</p>
          <p>{run.task.truth}</p>
        </div>
      ) : null}
      {stats ? (
        <p className="aw-note">
          {stats.model_calls} model calls · {stats.tool_calls} tool calls · {(stats.input_tokens + stats.output_tokens).toLocaleString()} tokens ·{" "}
          {Math.round(run.seconds ?? 0)} s · {run.model ?? "model"} · {run.framework ?? ""}
        </p>
      ) : null}
      {scenario.data_note ? <p className="aw-note">{scenario.data_note}</p> : null}
    </div>
  );
}

export function AboutPanel({ scenario }: { scenario: ScenarioSpec }) {
  const info = PATTERN_INFO[scenario.pattern];
  return (
    <div className="aw-about">
      <p className="aw-eyebrow">
        {scenario.industry} · {scenario.pattern_label}
      </p>
      <h3>{scenario.title}</h3>
      <p>{scenario.summary}</p>
      <p className="aw-eyebrow">Watch for</p>
      <ul>
        {scenario.watch_for.map((item) => (
          <li key={item}>{item}</li>
        ))}
      </ul>
      {info ? (
        <>
          <p className="aw-eyebrow">The pattern</p>
          <dl className="aw-facts">
            <dt>What</dt>
            <dd>{info.what}</dd>
            <dt>Use it when</dt>
            <dd>{info.when}</dd>
            <dt>Cost</dt>
            <dd>{info.cost}</dd>
          </dl>
        </>
      ) : null}
      <p className="aw-note">{scenario.data_note}</p>
    </div>
  );
}
