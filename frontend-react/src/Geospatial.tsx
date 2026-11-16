import { useEffect, useRef, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "./api";
import type {
  LocationRegistry,
  SelectedBundle,
  MeasurementResponse,
  Query,
  SourceMode,
} from "./contracts";
import { PageHeading } from "./UI";
import { Notice, Results, AIExplanation } from "./Results";
import Insights from "./Insights";
import Measurements from "./Measurements";
import TownMap from "./TownMap";
export default function Geospatial() {
  const [registry, setRegistry] = useState<LocationRegistry | null>(null),
    [selected, setSelected] = useState<string[]>(["loc:gangtok"]),
    [bundle, setBundle] = useState<SelectedBundle | null>(null),
    [measures, setMeasures] = useState<MeasurementResponse | null>(null),
    [variables, setVariables] = useState<string[]>([]),
    [start, setStart] = useState("2025-01-01"),
    [end, setEnd] = useState("2025-01-07"),
    [source, setSource] = useState<SourceMode>("live"),
    [error, setError] = useState(""),
    [busy, setBusy] = useState(false);
  const active = useRef<AbortController | null>(null);
  useEffect(() => {
    const c = new AbortController();
    api
      .locations(c.signal)
      .then((r) => {
        if (!c.signal.aborted) setRegistry(r);
      })
      .catch((e) => {
        if (!c.signal.aborted) setError((e as Error).message);
      });
    return () => {
      c.abort();
      active.current?.abort();
    };
  }, []);
  function choose(id: string) {
    if (busy) return;
    setError("");
    if (!selected.includes(id) && selected.length === 2) {
      setError("Select at most two town points.");
      return;
    }
    setSelected(
      selected.includes(id)
        ? selected.filter((v) => v !== id)
        : [...selected, id],
    );
    setBundle(null);
    setMeasures(null);
  }
  async function retrieve(e: React.FormEvent) {
    e.preventDefault();
    if (!selected.length || start > end) {
      setError("Select one or two towns and ordered dates.");
      return;
    }
    const c = new AbortController();
    active.current = c;
    setError("");
    setBusy(true);
    setBundle(null);
    setMeasures(null);
    try {
      const result = await api.selected(
        selected,
        start,
        end,
        crypto.randomUUID(),
        source,
        c.signal,
      );
      if (c.signal.aborted) return;
      setBundle(result);
      if (variables.length) {
        const query: Query = { ...result.environment.query, variables };
        const extra = await api.measurements(query, source, c.signal);
        if (!c.signal.aborted) setMeasures(extra);
      }
    } catch (e) {
      if (!c.signal.aborted) setError((e as Error).message);
    } finally {
      if (active.current === c) setBusy(false);
    }
  }
  return (
    <>
      <PageHeading
        eyebrow="GEOSPATIAL ENVIRONMENTAL EXPLORER"
        title="Environmental map of Sikkim."
        description="Verified coordinates, explicit selections and real environmental retrieval. No trained NLP inference is claimed for this form."
      />
      {error && (
        <div className="error" role="alert">
          {error}
        </div>
      )}
      {registry && (
        <>
          <section className="panel">
            <Notice>
              {registry.locations.length} active verified points.{" "}
              {registry.extended_enabled
                ? "Expanded registry enabled."
                : "Baseline registry; enable TERRAMIND_EXTENDED_LOCATIONS=1 on the backend for the reviewed expansion."}
            </Notice>
            <TownMap
              towns={registry.locations}
              selected={selected}
              onSelect={choose}
              results={bundle?.environment.results}
            />
            <form onSubmit={retrieve}>
              <fieldset>
                <legend>Accessible location selection · up to two towns</legend>
                {registry.locations.map((t) => (
                  <label className="check" key={t.id}>
                    <input
                      type="checkbox"
                      checked={selected.includes(t.id)}
                      onChange={() => choose(t.id)}
                      disabled={busy}
                    />
                    {t.name}
                  </label>
                ))}
              </fieldset>
              <div className="controls">
                <label>
                  Period start
                  <input
                    type="date"
                    value={start}
                    onChange={(e) => setStart(e.target.value)}
                    min="1940-01-01"
                    required
                    disabled={busy}
                  />
                </label>
                <label>
                  Period end
                  <input
                    type="date"
                    value={end}
                    onChange={(e) => setEnd(e.target.value)}
                    min={start}
                    required
                    disabled={busy}
                  />
                </label>
                <label>
                  Data source
                  <select
                    value={source}
                    onChange={(e) => setSource(e.target.value as SourceMode)}
                    disabled={busy}
                  >
                    <option value="live">Explicit live retrieval</option>
                    <option value="snapshot">
                      Recorded baseline snapshots · three original towns only
                    </option>
                  </select>
                </label>
              </div>
              <fieldset>
                <legend>
                  Additional measurements · explicit live data only
                </legend>
                {["HUMIDITY", "WIND_SPEED"].map((v) => (
                  <label className="check" key={v}>
                    <input
                      type="checkbox"
                      checked={variables.includes(v)}
                      disabled={
                        busy || !registry.supplemental_variables.includes(v)
                      }
                      onChange={(e) =>
                        setVariables(
                          e.target.checked
                            ? [...variables, v]
                            : variables.filter((x) => x !== v),
                        )
                      }
                    />
                    {v === "HUMIDITY"
                      ? "Relative humidity · %"
                      : "Scalar wind speed · m/s"}
                  </label>
                ))}
              </fieldset>
              <div className="actions">
                <button className="primary" disabled={busy || !selected.length}>
                  {busy
                    ? "Retrieving environmental data…"
                    : "Retrieve selected points"}
                </button>
                {busy && (
                  <button
                    type="button"
                    onClick={() => {
                      active.current?.abort();
                      setBusy(false);
                    }}
                  >
                    Cancel retrieval
                  </button>
                )}
                {selected.length === 2 && (
                  <Link
                    to={
                      "/comparison?" +
                      selected
                        .map((id) => "town=" + encodeURIComponent(id))
                        .join("&")
                    }
                  >
                    Open these towns in trained comparison
                  </Link>
                )}
              </div>
            </form>
            <details>
              <summary>
                Registry coordinates, aliases and geographical sources
              </summary>
              <div className="table-scroll">
                <table>
                  <caption>
                    GeoNames populated-place points via Open-Meteo; not district
                    boundaries
                  </caption>
                  <thead>
                    <tr>
                      <th>Town / aliases</th>
                      <th>Coordinates</th>
                      <th>Region</th>
                      <th>Verification source</th>
                    </tr>
                  </thead>
                  <tbody>
                    {registry.locations.map((t) => (
                      <tr key={t.id}>
                        <th>
                          {t.name}
                          <small>
                            {" "}
                            {Object.values(t.aliases).flat().join(", ")}
                          </small>
                        </th>
                        <td>
                          {t.latitude}, {t.longitude}
                        </td>
                        <td>
                          {t.admin1}, {t.country_code};{" "}
                          {t.admin2 ?? "District not supplied"}
                        </td>
                        <td>
                          <a
                            href={t.source_url}
                            target="_blank"
                            rel="noreferrer"
                          >
                            GeoNames {t.geonames_id}
                          </a>{" "}
                          · {t.verified_at}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </details>
          </section>
          {bundle && (
            <div id="map-results">
              <Notice>
                {bundle.inference} Weather GenAI uses validated
                temperature/rainfall facts only.
              </Notice>
              <Insights value={bundle.insights} />
              <Results environment={bundle.environment} />
              {measures && <Measurements value={measures} />}
              <AIExplanation value={bundle.explanation} />
            </div>
          )}
        </>
      )}
    </>
  );
}
