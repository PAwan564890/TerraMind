import type { Run, QuestionRoute, Explanation, System } from "./contracts";
import { safeURL } from "./Results";
export default function PipelineInspector({
  run,
  route,
  explanation,
  configured,
}: {
  run: Run | null;
  route: QuestionRoute | null;
  explanation: Explanation | null;
  configured: System["genai"] | undefined;
}) {
  const bypass =
    route &&
    ["general_knowledge", "unsupported", "clarification"].includes(
      route.category,
    );
  const analysis = bypass ? null : run?.analysis;
  const environment = bypass ? null : run?.bundle?.environment;
  const measurements = bypass ? null : run?.measurements;
  const ai = bypass ? null : explanation;
  return (
    <details className="panel pipeline-inspector">
      <summary>AI Pipeline Inspector</summary>
      <p className="muted">
        Returned backend outputs only. Raw model logits, hidden reasoning and
        provider credentials are not exposed.
      </p>
      <section aria-label="NLP pipeline stage">
        <h2>A. Trained NLP / explicit rule demonstration</h2>
        {analysis && run ? (
          <>
            <p>
              Inference mode:{" "}
              <strong>
                {run.mode === "trained"
                  ? "Trained NLP inference"
                  : "Rule demonstration — not trained inference"}
              </strong>
            </p>
            <p>
              Detected language: {analysis.language.code}. Predicted intent label:{" "}
              {analysis.intent.label}. Status: {analysis.status}.
            </p>
            <p>
              {run.mode === "trained"
                ? `Backend language confidence: ${analysis.language.confidence}; intent confidence: ${analysis.intent.confidence}.`
                : "Rule confidence is unmeasured; zero values must not be interpreted as trained probabilities."}
            </p>
            <div className="table-scroll">
              <table>
                <caption>
                  Actual backend entities and canonical normalization
                </caption>
                <thead>
                  <tr>
                    <th>Text</th>
                    <th>Entity type</th>
                    <th>Offsets</th>
                    <th>Canonical normalization</th>
                    <th>Backend confidence</th>
                  </tr>
                </thead>
                <tbody>
                  {analysis.entities.map((e, i) => (
                    <tr key={i}>
                      <th>{e.text}</th>
                      <td>{e.type}</td>
                      <td>
                        {e.start}–{e.end}
                      </td>
                      <td>{e.normalized ?? "Not resolved"}</td>
                      <td>
                        {run.mode === "trained"
                          ? e.confidence
                          : "Unmeasured (rules)"}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <p>
              Normalization warnings:{" "}
              {analysis.warnings.join(" · ") || "None returned"}. Entity
              confidence can include the backend normalization score; raw NER
              scores are not separately exposed.
            </p>
            <h3>Original structured environmental query</h3>
            <pre>{JSON.stringify(analysis.structured_query, null, 2)}</pre>
          </>
        ) : (
          <p>
            {bypass
              ? "Not invoked for this routing category."
              : "No NLP result returned yet. Language, intent, entities and normalization are unavailable."}
          </p>
        )}
      </section>
      <section aria-label="Environmental pipeline stage">
        <h2>B. Environmental data & deterministic analytics</h2>
        {environment ? (
          <>
            <p>
              Retrieval status: {environment.status}. {environment.message}{" "}
              {environment.errors.join(" ")}
            </p>
            <p>
              Temperature uses °C; rainfall and total precipitation use mm.
              Missing values remain null.
            </p>
            {environment.results.map((r) => (
              <div key={r.location_id}>
                <h3>
                  {r.location_name} · {r.start} → {r.end} · {r.timezone}
                </h3>
                <p>
                  {r.source} · {r.data_kind} · retrieved {r.retrieved_at}
                </p>
                <p>
                  <a
                    href={safeURL(r.source_url)}
                    target="_blank"
                    rel="noreferrer"
                  >
                    Environmental source
                  </a>{" "}
                  · {r.attribution}
                </p>
                <h3>Returned observations, computed statistics and coverage</h3>
                <pre>
                  {JSON.stringify(
                    {
                      daily: r.daily,
                      summary: r.summary,
                      warnings: r.warnings,
                      requested_point: [
                        r.requested_latitude,
                        r.requested_longitude,
                      ],
                      model_grid: [r.grid_latitude, r.grid_longitude],
                    },
                    null,
                    2,
                  )}
                </pre>
              </div>
            ))}
          </>
        ) : (
          <p>
            {bypass
              ? "No environmental retrieval was performed for this routing answer."
              : "No weather observations or statistics returned."}
          </p>
        )}
        {measurements && (
          <>
            <p>
              Supplemental retrieval status: {measurements.status}.{" "}
              {measurements.message}
            </p>
            <pre>{JSON.stringify(measurements.results, null, 2)}</pre>
            <p>
              Supplemental units and coverage are returned by the backend; these
              measurements are not in the weather GenAI context.
            </p>
          </>
        )}
      </section>
      <section aria-label="Generative AI pipeline stage">
        <h2>C. Grounded Generative AI</h2>
        <p>
          Configured provider:{" "}
          {configured?.provider ?? "Not exposed by backend"}. Credentials
          configured:{" "}
          {configured
            ? String(configured.configured)
            : "Not exposed by backend"}
          .
        </p>
        {ai ? (
          <>
            <p>
              Actual explanation status:{" "}
              <strong>Explanation status: {ai.status}</strong>. {ai.message}
            </p>
            <p>
              Response provider: {ai.provider ?? "Not exposed by backend"}.
              Model: {ai.model ?? "Not exposed by backend"}.
            </p>
            <h3>Validated server facts</h3>
            <pre>{JSON.stringify(ai.claims, null, 2)}</pre>
            <h3>Actual evidence references</h3>
            <ul>
              {ai.sources.map((s) => (
                <li key={s.id}>
                  <a href={safeURL(s.url)} target="_blank" rel="noreferrer">
                    [{s.id}] {s.name}
                  </a>{" "}
                  · {s.data_kind} · {s.source_mode} · {s.retrieved_at} ·{" "}
                  {s.attribution}
                </li>
              ))}
            </ul>
          </>
        ) : (
          <p>
            {bypass
              ? "No LLM call was made for this routing answer."
              : "No grounded explanation response returned; provider/model and validated facts are unavailable."}
          </p>
        )}
        <p>
          Follow-up context:{" "}
          {!bypass && run?.bundle?.context_id
            ? "Available for this browser conversation; backend enforces ownership and expiry."
            : "No usable weather context returned for this view."}{" "}
          Follow-ups can use only validated stored facts, not new places, dates,
          measurements or authoritative model calculations.
        </p>
      </section>
    </details>
  );
}
