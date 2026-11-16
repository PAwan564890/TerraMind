import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  CartesianGrid,
} from "recharts";
import type { MeasurementResponse } from "./contracts";
import { Notice, safeURL } from "./Results";
const show = (v: number | null) =>
  v == null
    ? "Unavailable"
    : v.toLocaleString(undefined, {
        minimumFractionDigits: 1,
        maximumFractionDigits: 2,
      });
export default function Measurements({
  value,
}: {
  value: MeasurementResponse;
}) {
  return (
    <section className="panel">
      <div className="eyebrow">
        SUPPLEMENTAL MEASUREMENTS · NOT WEATHER GENAI CONTEXT
      </div>
      <h2>Humidity & wind-speed observations</h2>
      <Notice>
        {value.status}. {value.message} {value.errors.join(" ")}
      </Notice>
      {value.results.map((r) => (
        <div key={r.location_id}>
          <h3>
            {r.location_name} · {r.start} → {r.end} · {r.timezone}
          </h3>
          <p>{r.data_kind} grid estimates, not station measurements.</p>
          {Object.entries(r.summary).map(([variable, s]) => (
            <div key={variable}>
              <h3>
                {variable === "HUMIDITY"
                  ? "Daily mean relative humidity · 2 m"
                  : "Daily mean scalar wind speed · 10 m"}
              </h3>
              <div className="metrics">
                <div className="metric">
                  <span>Period mean of valid daily means</span>
                  <strong>
                    {show(s.mean)} <small>{s.unit}</small>
                  </strong>
                </div>
                <div className="metric">
                  <span>Minimum / maximum daily mean</span>
                  <strong>
                    {show(s.minimum)} / {show(s.maximum)}{" "}
                    <small>{s.unit}</small>
                  </strong>
                </div>
                <div className="metric">
                  <span>Coverage</span>
                  <strong>
                    {s.valid_days}/{s.expected_days}
                  </strong>
                  <p>{s.missing_days} missing days</p>
                </div>
              </div>
              <div
                className="chart"
                role="img"
                aria-label={`${r.location_name} ${variable} daily mean in ${s.unit}`}
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
                    <Line
                      dataKey={variable}
                      name={`${variable} ${s.unit}`}
                      stroke="#087f78"
                      dot={false}
                      isAnimationActive={false}
                    />
                  </LineChart>
                </ResponsiveContainer>
              </div>
            </div>
          ))}
          <details>
            <summary>
              Daily supplemental data table and scientific provenance
            </summary>
            <div className="table-scroll">
              <table>
                <caption>{r.location_name} · actual daily means</caption>
                <thead>
                  <tr>
                    <th>Date</th>
                    {Object.entries(r.summary).map(([v, s]) => (
                      <th key={v}>
                        {v} {s.unit}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {r.daily.map((d) => (
                    <tr key={d.date}>
                      <th>{d.date}</th>
                      {Object.keys(r.summary).map((v) => (
                        <td key={v}>{show(d[v] as number | null)}</td>
                      ))}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <p>
              <a href={safeURL(r.source_url)} target="_blank" rel="noreferrer">
                {r.source}
              </a>{" "}
              · {r.data_kind} · {r.attribution}
            </p>
            <p>
              Retrieved {r.retrieved_at}. Requested {r.requested_latitude},{" "}
              {r.requested_longitude}; grid {r.grid_latitude},{" "}
              {r.grid_longitude}.
            </p>
            {r.limitations.map((text) => (
              <p key={text}>{text}</p>
            ))}
          </details>
        </div>
      ))}
    </section>
  );
}
