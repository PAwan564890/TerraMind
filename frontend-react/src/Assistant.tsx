import { useEffect, useRef, useState } from "react";
import { api } from "./api";
import { PageHeading } from "./UI";
import { AIExplanation, Notice, Results } from "./Results";
import type {
  Health,
  System,
  Run,
  Mode,
  SourceMode,
  Language,
  Explanation,
} from "./contracts";
import { ArrowUpRight } from "lucide-react";
export const EXAMPLE =
  "Show temperature and rainfall in Gangtok from 2025-01-01 to 2025-01-07.";
export default function Assistant({
  system,
  health,
  session,
  run,
  setRun,
  reset,
}: {
  system: System | null;
  health: Health | null;
  session: string;
  run: Run | null;
  setRun: (r: Run | null) => void;
  reset: () => void;
}) {
  const [question, setQuestion] = useState(EXAMPLE),
    [mode, setMode] = useState<Mode>("trained"),
    [source, setSource] = useState<SourceMode>("live"),
    [language, setLanguage] = useState<Language | "auto">("auto"),
    [busy, setBusy] = useState(false),
    [error, setError] = useState(""),
    [followup, setFollowup] = useState("What is the mean temperature?"),
    [answer, setAnswer] = useState<Explanation | null>(null);
  const active = useRef<AbortController | null>(null);
  useEffect(() => () => active.current?.abort(), []);
  async function submit(event: React.FormEvent) {
    event.preventDefault();
    active.current?.abort();
    const c = new AbortController();
    active.current = c;
    setBusy(true);
    setError("");
    setRun(null);
    setAnswer(null);
    try {
      const analysis = await api.analyze(question, session, mode, c.signal);
      const initial: Run = { question, mode, source, analysis, bundle: null };
      if (!c.signal.aborted) setRun(initial);
      if (analysis.status === "ok" && analysis.structured_query) {
        const bundle = await api.session(
          analysis.structured_query,
          session,
          source,
          language === "auto" ? analysis.language.code : language,
          c.signal,
        );
        if (!c.signal.aborted) setRun({ ...initial, bundle });
      }
    } catch (e) {
      if (!c.signal.aborted) setError((e as Error).message);
    } finally {
      if (active.current === c) setBusy(false);
    }
  }
  async function ask(event: React.FormEvent) {
    event.preventDefault();
    if (!run?.bundle?.context_id) return;
    const c = new AbortController();
    active.current = c;
    setBusy(true);
    setError("");
    setAnswer(null);
    try {
      const value = await api.explain(
        session,
        run.bundle.context_id,
        followup,
        language === "auto" ? run.analysis.language.code : language,
        c.signal,
      );
      if (!c.signal.aborted) setAnswer(value);
    } catch (e) {
      if (!c.signal.aborted) setError((e as Error).message);
    } finally {
      if (active.current === c) setBusy(false);
    }
  }
  return (
    <>
      <PageHeading
        eyebrow="MULTILINGUAL AI ASSISTANT"
        title="Start with a question."
        description="English, हिन्दी, नेपाली — one validated environmental workflow."
      />
      <section className="panel">
        <form onSubmit={submit}>
          <div className="controls">
            <label>
              Inference mode
              <select
                value={mode}
                onChange={(e) => setMode(e.target.value as Mode)}
                disabled={busy}
              >
                <option value="trained">Trained NLP inference</option>
                <option value="demo" disabled={!system?.demo_enabled}>
                  Rule demonstration · not trained
                </option>
              </select>
            </label>
            <label>
              Environmental source
              <select
                value={source}
                onChange={(e) => setSource(e.target.value as SourceMode)}
                disabled={busy}
              >
                <option value="live">Live Open-Meteo retrieval</option>
                <option value="snapshot">
                  Recorded snapshot · 1–7 Jan 2025
                </option>
              </select>
            </label>
            <label>
              Explanation language
              <select
                value={language}
                onChange={(e) =>
                  setLanguage(e.target.value as Language | "auto")
                }
                disabled={busy}
              >
                <option value="auto">Match detected language</option>
                <option value="en">English</option>
                <option value="hi">हिन्दी</option>
                <option value="ne">नेपाली</option>
              </select>
            </label>
          </div>
          {mode === "demo" && (
            <Notice>
              RULE DEMONSTRATION: rule-based language, intent and entities. Not
              trained-model inference; confidence is unmeasured.
            </Notice>
          )}
          {mode === "trained" && health && !health.models_loaded && (
            <Notice>
              Trained checkpoints unavailable. No automatic rule fallback will
              occur.
            </Notice>
          )}
          {source === "snapshot" && (
            <Notice>
              Recorded environmental data, not a live request. Limited to
              2025-01-01 through 2025-01-07.
            </Notice>
          )}
          <label htmlFor="question">Environmental question</label>
          <textarea
            id="question"
            value={question}
            onChange={(e) => setQuestion(e.target.value)}
            maxLength={4000}
            required
            rows={3}
            disabled={busy}
          />
          <div className="actions">
            <button className="primary" disabled={busy || !question.trim()}>
              {busy ? "Processing…" : "Analyze environment"}{" "}
              <ArrowUpRight size={16} />
            </button>
            {busy && (
              <button
                type="button"
                onClick={() => {
                  active.current?.abort();
                  setBusy(false);
                  setError(
                    "Request cancelled. Start a new query to refresh the context.",
                  );
                }}
              >
                Cancel request
              </button>
            )}
            <button
              type="button"
              disabled={busy}
              onClick={() => {
                reset();
                setAnswer(null);
                setError("");
              }}
            >
              New conversation
            </button>
          </div>
        </form>
        <div className="examples">
          Try:{" "}
          {[
            "गान्तोकमा 2025-01-01 देखि 2025-01-07 सम्म तापक्रम र वर्षा कति छ?",
            "गंगटोक में 2025-01-01 से 2025-01-07 तक तापमान और बारिश दिखाएं।",
          ].map((q) => (
            <button key={q} disabled={busy} onClick={() => setQuestion(q)}>
              {q}
            </button>
          ))}
        </div>
      </section>
      {error && (
        <div className="error" role="alert">
          {error}
        </div>
      )}
      {run && (
        <>
          <section className="panel">
            <div className="eyebrow">
              NLP ANALYSIS ·{" "}
              {run.mode === "demo" ? "RULE DEMONSTRATION" : "TRAINED INFERENCE"}
            </div>
            <h2>Your question</h2>
            <p>{run.question}</p>
            <div className="tags">
              <span className="badge">
                Language: {run.analysis.language.code}
              </span>
              <span className="badge">Intent: {run.analysis.intent.label}</span>
              <span className="badge">{run.analysis.status}</span>
            </div>
            {run.analysis.clarification && (
              <Notice>
                {run.analysis.clarification.message_key} Missing:{" "}
                {run.analysis.clarification.missing_fields.join(", ")}
              </Notice>
            )}
            {run.analysis.status === "out_of_domain" && (
              <Notice>
                This question is outside the environmental NLP domain.
              </Notice>
            )}
            <p>
              Location:{" "}
              {run.analysis.structured_query?.locations
                .map((l) => l.name)
                .join(", ") || "Unresolved"}{" "}
              · Period:{" "}
              {run.analysis.structured_query?.time_period?.start ||
                run.analysis.structured_query?.time_period?.type ||
                "Unresolved"}{" "}
              → {run.analysis.structured_query?.time_period?.end || ""}
            </p>
            <div className="tags">
              {run.analysis.entities.map((e, i) => (
                <span className="entity" key={i}>
                  {e.text}{" "}
                  <small>
                    {e.type} · {e.normalized || "unresolved"}
                  </small>
                </span>
              ))}
            </div>
            {run.analysis.warnings.map((w, i) => (
              <p className="muted" key={i}>
                {w}
              </p>
            ))}
            <details>
              <summary>Structured query · original backend contract</summary>
              <pre>
                {JSON.stringify(run.analysis.structured_query, null, 2)}
              </pre>
            </details>
          </section>
          {run.bundle && (
            <>
              <Notice>
                {run.source === "snapshot"
                  ? "RECORDED SNAPSHOT — not live data"
                  : "Live source selected. See retrieval timestamps below."}
              </Notice>
              <Results environment={run.bundle.environment} />
              <AIExplanation value={run.bundle.explanation} />
              {run.bundle.context_id && (
                <section className="panel">
                  <h2>Ask about these results</h2>
                  <p>
                    Stored period and locations only. New measurements require a
                    new environmental query.
                  </p>
                  <form onSubmit={ask}>
                    <label htmlFor="followup">Contextual follow-up</label>
                    <input
                      id="followup"
                      value={followup}
                      onChange={(e) => setFollowup(e.target.value)}
                      maxLength={500}
                      required
                      disabled={busy || answer?.status === "no_context"}
                    />
                    <button
                      className="primary"
                      disabled={
                        busy ||
                        answer?.status === "no_context" ||
                        !followup.trim()
                      }
                    >
                      Ask follow-up
                    </button>
                  </form>
                  {answer && <AIExplanation value={answer} />}
                  {answer?.status === "no_context" && (
                    <Notice>
                      Session expired or replaced. Run the environmental query
                      again to create fresh context.
                    </Notice>
                  )}
                </section>
              )}
            </>
          )}
        </>
      )}
    </>
  );
}
