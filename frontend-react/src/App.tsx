import Geospatial from "./Geospatial";
import Measurements from "./Measurements";
import { InsightsLoader } from "./Insights";
import Assistant from "./Assistant";
import Comparison from "./Comparison";
import { PageHeading } from "./UI";
import { useEffect, useState } from "react";
import { NavLink, Link, Route, Routes } from "react-router-dom";
import {
  Mountain,
  LayoutDashboard,
  MessagesSquare,
  ChartNoAxesCombined,
  MapPinned,
  ShieldCheck,
  ArrowUpRight,
  RefreshCw,
} from "lucide-react";
import { api } from "./api";
import type { Health, System, Run } from "./contracts";
import { Notice, Results } from "./Results";
const navigation = [
  ["/", "Overview", LayoutDashboard],
  ["/assistant", "AI assistant", MessagesSquare],
  ["/analytics", "Climate analytics", ChartNoAxesCombined],
  ["/comparison", "Location comparison", MapPinned],
  ["/map", "Environmental map", Mountain],
  ["/transparency", "Model & data", ShieldCheck],
] as const;
export default function App() {
  const [health, setHealth] = useState<Health | null>(null),
    [system, setSystem] = useState<System | null>(null),
    [connection, setConnection] = useState("Connecting"),
    [run, setRun] = useState<Run | null>(null);
  const [session, setSession] = useState(() => crypto.randomUUID());
  async function refresh(signal?: AbortSignal) {
    setConnection("Connecting");
    try {
      const [h, s] = await Promise.all([
        api.health(signal),
        api.system(signal),
      ]);
      if (!signal?.aborted) {
        setHealth(h);
        setSystem(s);
        setConnection("Connected");
      }
    } catch {
      if (!signal?.aborted) {
        setHealth(null);
        setSystem(null);
        setConnection("Unavailable");
      }
    }
  }
  useEffect(() => {
    const c = new AbortController();
    void refresh(c.signal);
    return () => c.abort();
  }, []);
  return (
    <div className="shell">
      <a className="skip" href="#main">
        Skip to content
      </a>
      <aside className="sidebar">
        <Link className="brand" to="/">
          <Mountain size={32} />
          <span>
            TerraMind<small>ENVIRONMENTAL INTELLIGENCE</small>
          </span>
        </Link>
        <div className="workspace-label">SIKKIM RESEARCH WORKSPACE</div>
        <nav aria-label="Main navigation">
          {navigation.map(([path, label, Icon]) => (
            <NavLink key={path} to={path} end={path === "/"}>
              <Icon size={19} />
              {label}
            </NavLink>
          ))}
        </nav>
        <div className="sidebar-bottom">
          <span className="live-dot" /> Academic prototype
          <p>
            Verified town points.
            <br />
            Evidence before explanation.
          </p>
          <small>Evaluation · November 2026</small>
        </div>
      </aside>
      <div className="content">
        <header className="topbar">
          <span>Earth systems / Research workspace</span>
          <div>
            <span
              className={"badge " + (connection === "Connected" ? "good" : "")}
            >
              {connection}
            </span>
            <button
              className="icon-button"
              aria-label="Refresh backend status"
              onClick={() => void refresh()}
            >
              <RefreshCw size={16} />
            </button>
          </div>
        </header>
        <main id="main">
          <Routes>
            <Route path="/map" element={<Geospatial />} />
            <Route
              path="/"
              element={
                <>
                  <PageHeading
                    eyebrow="ENVIRONMENTAL INTELLIGENCE"
                    title="Understand your environment."
                    description="Ask in your language. Explore measured periods. Trace every explanation to its data."
                  />
                  <section className="hero">
                    <div>
                      <span className="eyebrow">SIKKIM · EASTERN HIMALAYA</span>
                      <h2>
                        A clearer view of
                        <br />a changing landscape.
                      </h2>
                      <p>
                        Multilingual analysis of temperature and rainfall,
                        grounded in environmental grid data.
                      </p>
                      <Link className="primary link-button" to="/assistant">
                        Open AI assistant <ArrowUpRight size={18} />
                      </Link>
                    </div>
                    <Mountain
                      className="hero-mountain"
                      strokeWidth={0.65}
                      aria-hidden="true"
                    />
                  </section>
                  <div className="status-grid">
                    <Status title="FastAPI backend" value={connection} />
                    <Status
                      title="Trained NLP"
                      value={
                        health?.models_loaded
                          ? "Available"
                          : health
                            ? "Checkpoints unavailable"
                            : "Unknown"
                      }
                    />
                    <Status
                      title="GenAI credentials"
                      value={
                        system
                          ? system.genai.configured
                            ? "Configured · not live-verified"
                            : "Not configured"
                          : "Unknown"
                      }
                    />
                  </div>
                  <section className="panel">
                    <h2>Your research area</h2>
                    <div className="towns">
                      {Object.entries(system?.towns || {}).map(([id, name]) => (
                        <div key={id}>
                          <MapPinned />
                          <h3>{name}</h3>
                          <p>Town-point grid estimate</p>
                        </div>
                      ))}
                    </div>
                    <p>
                      Variables: temperature (°C), rainfall and total
                      precipitation (mm). Sources: Open-Meteo ERA5 reanalysis
                      and weather-model estimates; optional recorded snapshots.
                    </p>
                  </section>
                  {system?.capabilities && (
                    <p className="muted">
                      Supplemental measurements enabled:{" "}
                      {system.capabilities.additional_measurements.join(", ") ||
                        "None"}
                      .{" "}
                      <Link to="/map">
                        Open the environmental map and registry
                      </Link>
                      .
                    </p>
                  )}
                  <Limitations system={system} />
                </>
              }
            />
            <Route
              path="/assistant"
              element={
                <Assistant
                  system={system}
                  health={health}
                  session={session}
                  run={run}
                  setRun={setRun}
                  reset={() => {
                    setSession(crypto.randomUUID());
                    setRun(null);
                  }}
                />
              }
            />
            <Route
              path="/analytics"
              element={
                <>
                  <PageHeading
                    eyebrow="CLIMATE ANALYTICS"
                    title="The data behind the answer."
                    description="Descriptive statistics from retrieved daily values. No inferred climate significance."
                  />
                  {run?.bundle || run?.measurements ? (
                    <>
                      <Notice>
                        {run.source === "snapshot"
                          ? "Recorded snapshot, not a live retrieval."
                          : "Live retrieval selected."}{" "}
                        Query: {run.question}
                      </Notice>
                      {run.bundle && (
                        <>
                          <InsightsLoader
                            session={session}
                            context={run.bundle.context_id}
                          />
                          <Results environment={run.bundle.environment} />
                        </>
                      )}
                      {run.measurements && (
                        <Measurements value={run.measurements} />
                      )}
                    </>
                  ) : (
                    <Empty />
                  )}
                </>
              }
            />
            <Route
              path="/comparison"
              element={<Comparison system={system} />}
            />
            <Route
              path="/transparency"
              element={
                <>
                  <PageHeading
                    eyebrow="MODEL & DATA TRANSPARENCY"
                    title="Know what powers each answer."
                    description="An academic environmental intelligence prototype, toward an Earth System Digital Twin."
                  />
                  <div className="status-grid">
                    <Status
                      title="Inference checkpoint health"
                      value={
                        health?.models_loaded
                          ? "Loaded"
                          : "Unavailable / unknown"
                      }
                    />
                    <Status
                      title="Selected assistant mode"
                      value={
                        run?.mode === "demo"
                          ? "Rule demonstration"
                          : "Trained NLP (default)"
                      }
                    />
                    <Status
                      title="Provider configuration"
                      value={
                        system?.genai.configured
                          ? system.genai.provider
                          : "Not configured"
                      }
                    />
                  </div>
                  <section className="panel">
                    <h2>From language to evidence</h2>
                    <ol className="architecture">
                      <li>
                        Trained language detection → intent classification →
                        named entities
                      </li>
                      <li>
                        Deterministic normalization → validated structured query
                      </li>
                      <li>
                        Open-Meteo retrieval → deterministic environmental
                        statistics
                      </li>
                      <li>
                        Server-owned session context → optional LLM fact
                        selection
                      </li>
                      <li>
                        Strict claim validation → multilingual template
                        explanation
                      </li>
                    </ol>
                    <p>
                      English, Hindi and Nepali input. Rule demonstration is a
                      separate opt-in route, with unmeasured confidence; it
                      never replaces trained inference automatically.
                    </p>
                    <h3>Data is an estimate</h3>
                    <p>
                      ERA5 historical reanalysis combines observations and
                      physical modelling. Recent weather-model data are
                      estimates and may include forecast hours. Neither
                      represents a local station measurement. Rainfall differs
                      from total precipitation, which may include snow.
                    </p>
                    <h3>Generative AI boundaries</h3>
                    <p>
                      Provider configuration does not prove availability. The
                      LLM selects server-verified facts; it cannot author
                      authoritative numbers. Unsupported measurements and new
                      dates or places require a new query. Context expires after{" "}
                      {system?.genai.context_ttl_seconds ?? 900} seconds; a new
                      successful query replaces the session context. Credentials
                      remain on the backend.
                    </p>
                    <p>
                      Backend status detail:{" "}
                      {health?.detail || health?.status || "Unavailable"}
                    </p>
                  </section>
                  <Limitations system={system} />
                </>
              }
            />
            <Route
              path="*"
              element={
                <>
                  <h1>Page not found</h1>
                  <Link to="/">Return to overview</Link>
                </>
              }
            />
          </Routes>
          <footer>
            TerraMind · Academic research prototype · Grid estimates, not
            station observations
          </footer>
        </main>
      </div>
    </div>
  );
}
function Status({ title, value }: { title: string; value: string }) {
  return (
    <div className="panel status-card">
      <span>{title}</span>
      <strong>{value}</strong>
    </div>
  );
}
function Limitations({ system }: { system: System | null }) {
  return (
    <section className="panel">
      <h2>Scope & limitations</h2>
      <ul>
        {(
          system?.limitations || [
            "Backend status unavailable. Verified town points only; no disaster prediction, causal inference or validated climate trends.",
          ]
        ).map((l) => (
          <li key={l}>{l}</li>
        ))}
      </ul>
    </section>
  );
}
function Empty() {
  return (
    <section className="panel empty">
      <ChartNoAxesCombined size={36} />
      <h2>No environmental results yet</h2>
      <p>
        Run a supported question to populate charts and statistics with actual
        backend results.
      </p>
      <Link className="primary link-button" to="/assistant">
        Ask an environmental question
      </Link>
    </section>
  );
}
