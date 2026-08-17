import { useRef, useState } from "react";
import { Bot, CircleStop, RotateCcw, Send, Sparkles, UserRound } from "lucide-react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { deleteAgentSession, streamAgentChat, type AgentEvent } from "../api";

interface Message {
  id: string;
  role: "user" | "assistant";
  content: string;
}

const samplePrompts = [
  "Compare the maintenance triage and assortment planning patterns.",
  "Which showcase cases require the strongest human review boundary?",
  "Give me three design principles for grounded AI applications.",
  "Which use case is a good example of document intelligence plus an LLM?",
];

export default function AskStudioPage() {
  const searchParams = new URLSearchParams(window.location.search);
  const assessmentId = searchParams.get("assessment");
  const courseCaseId = searchParams.get("courseCase");
  const [messages, setMessages] = useState<Message[]>([]);
  const [composer, setComposer] = useState(
    assessmentId
      ? `Explain fit assessment ${assessmentId}. Focus on the recommended pattern, risks, and the first validation step.`
      : courseCaseId
        ? `Use workflow scenario ${courseCaseId}. Explain the selected AI-relevant decisions through Data, Method, Metric, and Human, and distinguish them from decisions that should use a rule, solver, or human judgment.`
        : "",
  );
  const [sessionId, setSessionId] = useState<string | undefined>();
  const [model, setModel] = useState<string | null>(null);
  const [streaming, setStreaming] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const abortRef = useRef<AbortController | null>(null);

  const sendPrompt = async (prompt: string) => {
    const message = prompt.trim();
    if (!message || streaming) return;
    const assistantId = crypto.randomUUID();
    setMessages((current) => [
      ...current,
      { id: crypto.randomUUID(), role: "user", content: message },
      { id: assistantId, role: "assistant", content: "" },
    ]);
    setComposer("");
    setError(null);
    setStreaming(true);
    const controller = new AbortController();
    abortRef.current = controller;

    try {
      await streamAgentChat(
        { sessionId, message },
        (event: AgentEvent) => {
          if (event.type === "meta") {
            setSessionId(event.sessionId);
            setModel(event.model);
          }
          if (event.type === "delta") {
            setMessages((current) =>
              current.map((item) => (item.id === assistantId ? { ...item, content: item.content + event.content } : item)),
            );
          }
          if (event.type === "error") setError(event.message);
        },
        controller.signal,
      );
    } catch {
      if (!controller.signal.aborted) {
        // Signed out, approval still pending, quota, timeout - a beginner cannot act on the
        // difference, and every one of them is fixed the same way.
        setError(
          "Ask Studio needs GitHub Copilot, and it is not connected to your account yet. Everything else in the app works without it — the workflows, the AI Fit Analyzer, and the Online Order demo. Copilot is free for students once your Student Developer Pack is approved, which usually takes a few days. Setup steps are in docs/student-quickstart.md, section 3.",
        );
      }
    } finally {
      setStreaming(false);
      abortRef.current = null;
    }
  };

  const clear = async () => {
    abortRef.current?.abort();
    if (sessionId) await deleteAgentSession(sessionId).catch(() => undefined);
    setSessionId(undefined);
    setModel(null);
    setMessages([]);
    setError(null);
  };

  return (
    <div className="page ask-page">
      <header className="page-header">
        <div>
          <span className="eyebrow">Grounded design assistant</span>
          <h1>Ask Studio</h1>
          <p>Reason over the public catalog and your current fit assessment.</p>
        </div>
        <div className="agent-state">
          <span className={streaming ? "status-dot active" : "status-dot"} />
          {streaming ? "Copilot responding" : model ? `Model: ${model}` : "Connects on first message"}
        </div>
      </header>

      <section className="chat-workbench">
        <div className="chat-transcript" aria-live="polite">
          {!messages.length ? (
            <div className="chat-empty">
              <div className="assistant-emblem"><Sparkles size={28} aria-hidden="true" /></div>
              <h2>Studio questions</h2>
              <div className="prompt-grid">
                {samplePrompts.map((prompt) => (
                  <button type="button" key={prompt} onClick={() => void sendPrompt(prompt)}>
                    {prompt}<Send size={15} aria-hidden="true" />
                  </button>
                ))}
              </div>
            </div>
          ) : (
            messages.map((message) => (
              <article className={`chat-message ${message.role}`} key={message.id}>
                <div className="message-avatar">{message.role === "assistant" ? <Bot size={18} aria-hidden="true" /> : <UserRound size={18} aria-hidden="true" />}</div>
                <div className="message-body">
                  <span>{message.role === "assistant" ? "Applied AI Studio" : "You"}</span>
                  {message.content ? (
                    <ReactMarkdown remarkPlugins={[remarkGfm]}>{message.content}</ReactMarkdown>
                  ) : (
                    <div className="typing-indicator" aria-label="Assistant is responding"><i /><i /><i /></div>
                  )}
                </div>
              </article>
            ))
          )}
          {error ? <div className="error-banner">{error}</div> : null}
        </div>

        <form
          className="chat-composer"
          onSubmit={(event) => {
            event.preventDefault();
            void sendPrompt(composer);
          }}
        >
          <label>
            <span className="sr-only">Message Ask Studio</span>
            <textarea rows={2} maxLength={4000} value={composer} onChange={(event) => setComposer(event.target.value)} placeholder="Ask about a use case, architecture pattern, or fit assessment" />
          </label>
          <div className="composer-actions">
            <button type="button" className="icon-button" onClick={() => void clear()} title="Clear conversation" aria-label="Clear conversation"><RotateCcw size={18} /></button>
            {streaming ? (
              <button type="button" className="stop-button" onClick={() => abortRef.current?.abort()}><CircleStop size={17} aria-hidden="true" /> Stop</button>
            ) : (
              <button type="submit" className="primary-button compact" disabled={!composer.trim()}><Send size={17} aria-hidden="true" /> Send</button>
            )}
          </div>
        </form>
      </section>
    </div>
  );
}