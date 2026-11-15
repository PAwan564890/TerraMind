import { useEffect, useRef, useState } from "react";
import { api } from "./api";
import { PageHeading } from "./UI";
import { Notice, Results } from "./Results";
import type {
  Health,
  System,
  Run,
  Mode,
  SourceMode,
  Language,
  Explanation,
} from "./contracts";
export default function Comparison({ system }: { system: System | null }) {
  const [towns, setTowns] = useState(["Gangtok", "Namchi"]),
    [variable, setVariable] = useState("temperature and rainfall"),
    [start, setStart] = useState("2025-01-01"),
    [end, setEnd] = useState("2025-01-07"),
    [source, setSource] = useState<SourceMode>("live"),
    [result, setResult] = useState<Run | null>(null),
    [busy, setBusy] = useState(false),
    [error, setError] = useState("");
  const active = useRef<AbortController | null>(null);
  useEffect(() => () => active.current?.abort(), []);
  async function compare(e: React.FormEvent) {
    e.preventDefault();
    if (start > end) {
      setError("Start date must be on or before end date.");
      return;
    }
    if (towns.length !== 2) {
      setError("Select exactly two supported town points.");
      return;
    }
    setError("");
    setResult(null);
    setBusy(true);
    const c = new AbortController();
    active.current = c;
    try {
      const question = `Compare ${variable} in ${towns.join(" and ")} from ${start} to ${end}.`;
      const session = crypto.randomUUID();
      const analysis = await api.analyze(
        question,
        session,
        "trained",
        c.signal,
      );
      let bundle = null;
      if (analysis.status === "ok" && analysis.structured_query)
        bundle = await api.session(
          analysis.structured_query,
          session,
          source,
          "en",
          c.signal,
        );
      if (!c.signal.aborted)
        setResult({ question, analysis, bundle, mode: "trained", source });
    } catch (e) {
      if (!c.signal.aborted) setError((e as Error).message);
    } finally {
      if (!c.signal.aborted) setBusy(false);
    }
  }
  return (
    <>
      <PageHeading
        eyebrow="LOCATION COMPARISON"
        title="Two places. The same period."
        description="Compare supported town points using the trained NLP workflow. No district-wide or statewide coverage."
      />
      <section className="panel">
        <form onSubmit={compare}>
          <fieldset>
            <legend>Select two town points</legend>
            {Object.entries(system?.towns || {}).map(([id, name]) => (
              <label className="check" key={id}>
                <input
                  type="checkbox"
                  checked={towns.includes(name)}
                  disabled={busy}
                  onChange={(e) =>
                    setTowns(
                      e.target.checked
                        ? [...towns, name]
                        : towns.filter((t) => t !== name),
                    )
                  }
                />
                {name}
              </label>
            ))}
          </fieldset>
          <div className="controls">
            <label>
              Variables
              <select
                value={variable}
                onChange={(e) => setVariable(e.target.value)}
              >
                <option>temperature and rainfall</option>
                <option>temperature</option>
                <option>rainfall</option>
                <option>precipitation</option>
              </select>
            </label>
            <label>
              Start date
              <input
                type="date"
                value={start}
                min="1940-01-01"
                onChange={(e) => setStart(e.target.value)}
                required
              />
            </label>
            <label>
              End date
              <input
                type="date"
                value={end}
                min={start}
                onChange={(e) => setEnd(e.target.value)}
                required
              />
            </label>
            <label>
              Source
              <select
                value={source}
                onChange={(e) => setSource(e.target.value as SourceMode)}
              >
                <option value="live">Live retrieval</option>
                <option value="snapshot">Recorded snapshot</option>
              </select>
            </label>
          </div>
          <button className="primary" disabled={busy}>
            {busy ? "Retrieving comparison…" : "Compare town points"}
          </button>
        </form>
        <p>
          Trained NLP required. Maximum 366 days; backend validates historical
          availability. Snapshot coverage: 1–7 January 2025.
        </p>
      </section>
      {error && (
        <div className="error" role="alert">
          {error}
        </div>
      )}
      {result && (
        <>
          {result.source === "snapshot" && (
            <Notice>Recorded snapshots — not live data.</Notice>
          )}
          {result.bundle ? (
            <>
              <div className="comparison-summary">
                {result.bundle.environment.results.map((r) => (
                  <div className="panel" key={r.location_id}>
                    <h2>{r.location_name}</h2>
                    <p>
                      {r.start} → {r.end}
                    </p>
                    <p>
                      Mean {r.summary.temperature_mean_c ?? "Unavailable"} °C
                    </p>
                    <p>
                      Rainfall {r.summary.rainfall_total_mm ?? "Unavailable"} mm
                    </p>
                  </div>
                ))}
              </div>
              <Results environment={result.bundle.environment} />
            </>
          ) : (
            <Notice>
              NLP: {result.analysis.status}.{" "}
              {result.analysis.clarification?.message_key ||
                "No supported comparison returned."}
            </Notice>
          )}
        </>
      )}
    </>
  );
}
