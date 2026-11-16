import { useEffect, useState } from "react";
import { api } from "./api";
import type { InsightResponse, EventDay } from "./contracts";
import { formatMetric } from "./format";
import { Notice } from "./Results";
export function InsightsLoader({
  session,
  context,
}: {
  session: string;
  context: string | null | undefined;
}) {
  const [value, setValue] = useState<InsightResponse | null>(null),
    [error, setError] = useState("");
  useEffect(() => {
    setValue(null);
    setError("");
    if (!context) return;
    const c = new AbortController();
    api
      .insights(session, context, c.signal)
      .then((v) => {
        if (!c.signal.aborted) setValue(v);
      })
      .catch(() => {
        if (!c.signal.aborted)
          setError(
            "Additional insights unavailable; original environmental results remain below.",
          );
      });
    return () => c.abort();
  }, [session, context]);
  return (
    <>
      {error && <Notice>{error}</Notice>}
      {value && <Insights value={value} />}
    </>
  );
}
function Event({
  name,
  event,
  unit,
}: {
  name: string;
  event: EventDay | null;
  unit: "°C" | "mm";
}) {
  return (
    <div className="metric">
      <span>{name}</span>
      <strong>
        {event ? formatMetric(event.value, unit) : "Unavailable"}{" "}
        <small>{unit}</small>
      </strong>
      {event && (
        <>
          <p>{event.date}</p>
          {event.tied_dates.length > 1 && (
            <details>
              <summary>
                {event.tied_dates.length} tied dates; earliest shown
              </summary>
              <p>{event.tied_dates.join(", ")}</p>
            </details>
          )}
        </>
      )}
    </div>
  );
}
export default function Insights({ value }: { value: InsightResponse }) {
  return (
    <section className="panel">
      <div className="eyebrow">DETERMINISTIC ENVIRONMENTAL INSIGHTS</div>
      <h2>What the retrieved period shows</h2>
      {(value.status !== "ok" || value.message) && (
        <Notice>
          {value.status}. {value.message}
        </Notice>
      )}
      {value.comparisons.map((c) => (
        <div className="notice" key={c.left + c.right}>
          <strong>
            {c.left_name ?? c.left} − {c.right_name ?? c.right}
          </strong>
          <p>
            {c.start} → {c.end}. Mean temperature difference:{" "}
            {formatMetric(c.temperature_difference_c, "°C")} °C. Rainfall
            difference: {formatMetric(c.rainfall_difference_mm, "mm")} mm.
          </p>
          <p>
            Warmer: {c.warmer_name ?? c.warmer ?? "Unavailable"}. More rainfall:{" "}
            {c.wetter_name ?? c.wetter ?? "Unavailable"}.
          </p>
          {c.warnings.map((w) => (
            <p key={w}>{w}</p>
          ))}
        </div>
      ))}
      {value.results.map((r) => (
        <div key={r.location_id}>
          <h3>
            {r.location_name ?? r.location_id} · {r.start} → {r.end}
          </h3>
          <div className="metrics">
            <Event
              name="Warmest available day · daily mean"
              event={r.temperature_days.highest}
              unit="°C"
            />
            <Event
              name="Coolest available day · daily mean"
              event={r.temperature_days.lowest}
              unit="°C"
            />
            <Event
              name="Wettest available day"
              event={r.rainfall_days.highest}
              unit="mm"
            />
            <Event
              name="Driest available day"
              event={r.rainfall_days.lowest}
              unit="mm"
            />
          </div>
          <p>
            Available period range (highest daily maximum − lowest daily
            minimum): {formatMetric(r.period_temperature_range_c, "°C")} °C.
          </p>
          <p className="muted">
            {r.tie_rule} {r.limitation}
          </p>
          <details>
            <summary>Day-to-day changes, monthly portions & coverage</summary>
            <div className="table-scroll">
              <table>
                <caption>
                  Consecutive-day changes and daily temperature ranges · °C
                </caption>
                <thead>
                  <tr>
                    <th>Date</th>
                    <th>Mean change °C</th>
                    <th>Daily max − min °C</th>
                  </tr>
                </thead>
                <tbody>
                  {r.daily_variation.map((d) => (
                    <tr key={d.date}>
                      <th>{d.date}</th>
                      <td>
                        {formatMetric(
                          r.day_to_day.find((c) => c.date === d.date)
                            ?.temperature_mean_change_c,
                          "°C",
                        )}
                      </td>
                      <td>{formatMetric(d.temperature_range_c, "°C")}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <div className="table-scroll">
              <table>
                <caption>
                  Retrieved portions of calendar months — no extrapolation
                </caption>
                <thead>
                  <tr>
                    <th>Month</th>
                    <th>Mean °C</th>
                    <th>Rainfall mm</th>
                    <th>Valid temperature/rainfall days</th>
                    <th>Period</th>
                  </tr>
                </thead>
                <tbody>
                  {r.monthly.map((m) => (
                    <tr key={m.month}>
                      <th>{m.month}</th>
                      <td>{formatMetric(m.temperature_mean_c, "°C")}</td>
                      <td>{formatMetric(m.rainfall_total_mm, "mm")}</td>
                      <td>
                        {m.temperature_valid_days}/{m.retrieved_days} ·{" "}
                        {m.rainfall_valid_days}/{m.retrieved_days}
                      </td>
                      <td>
                        {m.period_start} through {m.period_end}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <ul>
              {Object.entries(r.coverage).map(([field, c]) => (
                <li key={field}>
                  {field}: {c.valid}/{c.expected} valid; {c.missing} missing
                </li>
              ))}
            </ul>
          </details>
        </div>
      ))}
    </section>
  );
}
