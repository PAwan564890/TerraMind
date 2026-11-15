import {
  LineChart,
  Line,
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
} from "recharts";
import type { Environment, Explanation, Weather } from "./contracts";
export function Notice({ children }: { children: React.ReactNode }) {
  return (
    <div className="notice" role="status">
      {children}
    </div>
  );
}
export function AIExplanation({ value }: { value: Explanation }) {
  return (
    <section className="panel ai">
      <div className="eyebrow">GROUNDED GENERATIVE AI</div>
      <h2>
        Explanation <span className="badge">{value.status}</span>
      </h2>
      <p>{value.message}</p>
      {value.status === "ok" && value.text && (
        <>
          <p className="explanation" lang={value.language}>
            {value.text}
          </p>
          <small>
            {value.provider} · {value.model} · Validated backend claims;
            template-rendered language
          </small>
          <ul>
            {value.sources.map((s) => (
              <li key={s.id}>
                <a href={safeURL(s.url)} target="_blank" rel="noreferrer">
                  {s.name}
                </a>{" "}
                · {s.source_mode} · {s.attribution}
              </li>
            ))}
          </ul>
        </>
      )}
    </section>
  );
}
export function safeURL(value: string) {
  try {
    const url = new URL(value);
    return ["https:", "http:"].includes(url.protocol) ? url.href : undefined;
  } catch {
    return undefined;
  }
}
const show = (n: number | null | undefined) =>
  n == null
    ? "Unavailable"
    : n.toLocaleString(undefined, { maximumFractionDigits: 2 });
export function Metrics({ result: r }: { result: Weather }) {
  return (
    <div className="metrics">
      {[
        ["Mean temperature", r.summary.temperature_mean_c, "°C"],
        [
          "Minimum / maximum",
          `${show(r.summary.temperature_min_c)} / ${show(r.summary.temperature_max_c)}`,
          "°C",
        ],
        ["Rainfall total", r.summary.rainfall_total_mm, "mm"],
        ["Total precipitation", r.summary.precipitation_total_mm, "mm"],
      ].map(([label, value, unit]) => (
        <div className="metric" key={String(label)}>
          <span>{label}</span>
          <strong>
            {typeof value === "number" ? show(value) : (value ?? "Unavailable")}{" "}
            <small>{unit}</small>
          </strong>
        </div>
      ))}
    </div>
  );
}
export function Provenance({ result: r }: { result: Weather }) {
  return (
    <details className="provenance">
      <summary>Source, coverage & limitations — {r.location_name}</summary>
      <p>
        {r.start} → {r.end} · {r.timezone} · {r.data_kind}
      </p>
      <p>
        {r.attribution} ·{" "}
        <a href={safeURL(r.source_url)} target="_blank" rel="noreferrer">
          Original data source
        </a>{" "}
        · <a href={safeURL(r.license_url)}>License</a>
      </p>
      <p>
        Retrieved {r.retrieved_at}. Requested point {r.requested_latitude},{" "}
        {r.requested_longitude}; model grid {r.grid_latitude},{" "}
        {r.grid_longitude}.
      </p>
      <p>{r.summary.interpretation}</p>
      <p>
        Available days:{" "}
        {Object.entries(r.summary.valid_days)
          .map(([key, n]) => `${key}: ${n}/${r.summary.days}`)
          .join(" · ")}
      </p>
      {!r.summary.totals_complete && (
        <Notice>
          Incomplete coverage: totals are partial. Missing values are never
          treated as zero.
        </Notice>
      )}
      {r.warnings.map((w, i) => (
        <p key={i}>{w}</p>
      ))}
    </details>
  );
}
export function Results({ environment: e }: { environment: Environment }) {
  return (
    <>
      <Notice>
        Retrieval: {e.status}. {e.message} {e.errors.join(" ")}
      </Notice>
      {e.results.map((r) => (
        <section className="panel" key={r.location_id}>
          <div className="eyebrow">OBSERVED PERIOD · GRID ESTIMATES</div>
          <h2>
            {r.location_name}{" "}
            <span className="badge">
              {r.start} → {r.end}
            </span>
          </h2>
          <p>
            {r.timezone} · {r.daily.length} daily records · {r.data_kind}
          </p>
          <Metrics result={r} />
          <div className="chart-grid">
            <div>
              <h3>Daily temperature · °C</h3>
              <div
                className="chart"
                role="img"
                aria-label={`${r.location_name} daily mean, minimum and maximum temperature in degrees Celsius`}
              >
                <ResponsiveContainer width="100%" height="100%">
                  <LineChart data={r.daily}>
                    <CartesianGrid strokeDasharray="3 3" />
                    <XAxis
                      dataKey="date"
                      tickFormatter={(v) => String(v).slice(5)}
                    />
                    <YAxis />
                    <Tooltip />
                    <Legend />
                    <Line
                      isAnimationActive={false}
                      dataKey="temperature_mean_c"
                      name="Mean °C"
                      stroke="#087f78"
                      dot={false}
                    />
                    <Line
                      isAnimationActive={false}
                      dataKey="temperature_min_c"
                      name="Min °C"
                      stroke="#537fb3"
                      dot={false}
                    />
                    <Line
                      isAnimationActive={false}
                      dataKey="temperature_max_c"
                      name="Max °C"
                      stroke="#bc742a"
                      dot={false}
                    />
                  </LineChart>
                </ResponsiveContainer>
              </div>
            </div>
            <div>
              <h3>Daily water totals · mm</h3>
              <div
                className="chart"
                role="img"
                aria-label={`${r.location_name} rainfall and precipitation in millimetres`}
              >
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart data={r.daily}>
                    <CartesianGrid strokeDasharray="3 3" />
                    <XAxis
                      dataKey="date"
                      tickFormatter={(v) => String(v).slice(5)}
                    />
                    <YAxis />
                    <Tooltip />
                    <Legend />
                    <Bar
                      isAnimationActive={false}
                      dataKey="rainfall_mm"
                      name="Rainfall mm"
                      fill="#087f78"
                    />
                    <Bar
                      isAnimationActive={false}
                      dataKey="precipitation_mm"
                      name="Precipitation mm"
                      fill="#88a9ca"
                    />
                  </BarChart>
                </ResponsiveContainer>
              </div>
            </div>
          </div>
          <details>
            <summary>Daily observations · accessible data table</summary>
            <div className="table-scroll">
              <table>
                <caption>
                  {r.location_name} · {r.start} to {r.end} · {r.timezone}
                </caption>
                <thead>
                  <tr>
                    {[
                      "Date",
                      "Mean °C",
                      "Min °C",
                      "Max °C",
                      "Rainfall mm",
                      "Precipitation mm",
                    ].map((h) => (
                      <th key={h}>{h}</th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {r.daily.map((d) => (
                    <tr key={d.date}>
                      <th>{d.date}</th>
                      {[
                        d.temperature_mean_c,
                        d.temperature_min_c,
                        d.temperature_max_c,
                        d.rainfall_mm,
                        d.precipitation_mm,
                      ].map((v, i) => (
                        <td key={i}>{show(v)}</td>
                      ))}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </details>
          <Provenance result={r} />
        </section>
      ))}
    </>
  );
}
