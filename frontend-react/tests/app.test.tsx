// Mocked browser API tests. Environmental fixture generated from the real recorded snapshot.
import { afterEach, beforeEach, describe, it, expect, vi } from "vitest";
import {
  render,
  screen,
  fireEvent,
  waitFor,
  cleanup,
} from "@testing-library/react";
import "@testing-library/jest-dom/vitest";
import { MemoryRouter } from "react-router-dom";
import App from "../src/App";
import { api, request } from "../src/api";
import { AIExplanation, Results, safeURL } from "../src/Results";
import type { Bundle, Analysis, Explanation } from "../src/contracts";
import bundleJSON from "./bundle.json";
import analysisJSON from "./analysis.json";
import system from "./system.json";
const bundle = bundleJSON as Bundle,
  analysis = analysisJSON as Analysis;
vi.mock("recharts", () => ({
  ResponsiveContainer: ({ children }: { children: React.ReactNode }) => (
    <div>{children}</div>
  ),
  LineChart: ({ data }: { data: unknown[] }) => (
    <div>Line chart rows: {data.length}</div>
  ),
  BarChart: ({ data }: { data: unknown[] }) => (
    <div>Bar chart rows: {data.length}</div>
  ),
  Line: () => null,
  Bar: () => null,
  XAxis: () => null,
  YAxis: () => null,
  CartesianGrid: () => null,
  Tooltip: () => null,
  Legend: () => null,
}));
beforeEach(() => {
  vi.spyOn(api, "route").mockResolvedValue({
    category: "environment",
    message: "Continue trained NLP",
    knowledge: null,
  });
  vi.spyOn(api, "health").mockResolvedValue({
    status: "degraded",
    models_loaded: false,
  });
  vi.spyOn(api, "system").mockResolvedValue(system);
  vi.spyOn(api, "analyze").mockResolvedValue(analysis);
  vi.spyOn(api, "session").mockResolvedValue(bundle);
});
afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
  vi.unstubAllGlobals();
});
function mount(path = "/") {
  render(
    <MemoryRouter initialEntries={[path]}>
      <App />
    </MemoryRouter>,
  );
}
async function submit() {
  mount("/assistant");
  await screen.findByText(
    "Trained checkpoints unavailable. No automatic rule fallback will occur.",
  );
  fireEvent.click(screen.getByRole("button", { name: /Analyze environment/ }));
  await screen.findByRole("heading", { name: "Your question" });
}
describe("routes and connectivity", () => {
  it.each([
    ["/", "Understand your environment."],
    ["/assistant", "Start with a question."],
    ["/analytics", "The data behind the answer."],
    ["/comparison", "Two places. The same period."],
    ["/transparency", "Know what powers each answer."],
  ])("renders %s", async (path, title) => {
    mount(path);
    expect(screen.getByRole("heading", { name: title })).toBeInTheDocument();
    await waitFor(() => expect(api.system).toHaveBeenCalled());
  });
  it("navigates with accessible links", async () => {
    mount();
    fireEvent.click(screen.getByRole("link", { name: "AI assistant" }));
    expect(screen.getByLabelText("Environmental question")).toBeInTheDocument();
    await waitFor(() => expect(api.health).toHaveBeenCalled());
  });
  it("handles backend disconnection without invented health", async () => {
    vi.mocked(api.health).mockRejectedValue(new Error());
    mount();
    await screen.findAllByText("Unavailable");
    expect(screen.getAllByText("Unknown")).toHaveLength(2);
  });
  it("has no invented initial environmental metrics", async () => {
    mount("/analytics");
    expect(
      screen.getByText("No environmental results yet"),
    ).toBeInTheDocument();
    await waitFor(() => expect(api.health).toHaveBeenCalled());
  });
});
describe("environmental workflow", () => {
  it("preserves exact dates, analysis and session identifiers", async () => {
    await submit();
    await waitFor(() => expect(api.session).toHaveBeenCalled());
    expect(api.analyze).toHaveBeenCalledWith(
      expect.stringContaining("2025-01-07"),
      expect.any(String),
      "trained",
      expect.any(AbortSignal),
    );
    expect(api.session).toHaveBeenCalledWith(
      expect.objectContaining({
        time_period: expect.objectContaining({
          start: "2025-01-01",
          end: "2025-01-07",
        }),
      }),
      expect.any(String),
      "live",
      "en",
      expect.any(AbortSignal),
    );
    await screen.findAllByText(/11.9/);
    expect(screen.getByText(/Intent: WEATHER_QUERY/)).toBeInTheDocument();
  });
  it("keeps environmental values when provider is disabled", async () => {
    await submit();
    await screen.findByText("disabled");
    expect(screen.getAllByText(/11.9/).length).toBeGreaterThan(0);
  });
  it("renders actual daily chart rows and missing values", () => {
    const copy = structuredClone(bundle.environment);
    copy.results[0].daily[0].temperature_mean_c = null;
    render(<Results environment={copy} />);
    expect(screen.getByText("Line chart rows: 7")).toBeInTheDocument();
    expect(screen.getByText("Bar chart rows: 7")).toBeInTheDocument();
    expect(screen.getByText("Unavailable")).toBeInTheDocument();
    expect(
      screen.getByText("2025-01-07", { selector: "th" }),
    ).toBeInTheDocument();
  });
  it("labels rule inference explicitly", async () => {
    mount("/assistant");
    await waitFor(() => expect(api.system).toHaveBeenCalled());
    await screen.findByRole("option", {
      name: "Rule demonstration · not trained",
    });
    fireEvent.change(screen.getByLabelText("Inference mode"), {
      target: { value: "demo" },
    });
    expect(screen.getByText(/RULE DEMONSTRATION:/)).toBeInTheDocument();
  });
  it("shows unsupported NLP without requesting environmental data", async () => {
    vi.mocked(api.analyze).mockResolvedValue({
      ...analysis,
      status: "out_of_domain",
      structured_query: null,
    });
    await submit();
    expect(
      screen.getByText(/outside the environmental NLP domain/),
    ).toBeInTheDocument();
    expect(api.session).not.toHaveBeenCalled();
  });
  it("handles unavailable trained models", async () => {
    vi.mocked(api.analyze).mockRejectedValue(
      new Error("Trained NLP is unavailable"),
    );
    mount("/assistant");
    fireEvent.click(
      screen.getByRole("button", { name: /Analyze environment/ }),
    );
    expect(await screen.findByRole("alert")).toHaveTextContent(
      "Trained NLP is unavailable",
    );
  });
  it("retains session for valid follow-up and handles expiry", async () => {
    vi.spyOn(api, "explain").mockResolvedValue({
      ...bundle.explanation,
      status: "no_context",
      message: "Expired context",
    });
    await submit();
    fireEvent.click(
      await screen.findByRole("button", { name: "Ask follow-up" }),
    );
    await screen.findByText(/Session expired or replaced/);
    expect(api.explain).toHaveBeenCalledWith(
      expect.any(String),
      bundle.context_id,
      "What is the mean temperature?",
      "en",
      expect.any(AbortSignal),
    );
    expect(
      screen.getByRole("button", { name: "Ask follow-up" }),
    ).toBeDisabled();
    expect(screen.getAllByText(/11.9/).length).toBeGreaterThan(0);
  });
  it("renders validated explanation as text", () => {
    const value: Explanation = {
      ...bundle.explanation,
      status: "ok",
      message: "Validated",
      text: "<script>bad()</script>",
      provider: "test",
      model: "mock",
    };
    render(<AIExplanation value={value} />);
    expect(screen.getByText("<script>bad()</script>")).toBeInTheDocument();
    expect(document.querySelector("script")).toBeNull();
  });
  it("does not render text from failed explanation", () => {
    render(
      <AIExplanation
        value={{
          ...bundle.explanation,
          status: "rejected",
          text: "Untrusted prose",
        }}
      />,
    );
    expect(screen.queryByText("Untrusted prose")).not.toBeInTheDocument();
  });
  it("rejects unsafe source URLs", () =>
    expect(safeURL("javascript:alert(1)")).toBeUndefined());
});
describe("HTTP transport", () => {
  it("uses the real trained endpoint and JSON contract", async () => {
    vi.mocked(api.analyze).mockRestore();
    const fetcher = vi
      .fn()
      .mockResolvedValue({ ok: true, json: async () => analysis });
    vi.stubGlobal("fetch", fetcher);
    await api.analyze("query", "session", "trained");
    expect(fetcher).toHaveBeenCalledWith(
      "/api/nlp/analyze",
      expect.objectContaining({
        body: JSON.stringify({ query: "query", session_id: "session" }),
      }),
    );
  });
  it("reports rejected dates safely", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({ ok: false, status: 422 }),
    );
    await expect(request("/nlp/analyze", {})).rejects.toThrow(
      "chronological order",
    );
  });
  it("reports transport failure", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockRejectedValue(new Error("private transport detail")),
    );
    await expect(request("/health")).rejects.toThrow(
      "Cannot reach a valid FastAPI",
    );
  });
  it("cancels an aborted request", async () => {
    const c = new AbortController();
    c.abort();
    vi.stubGlobal(
      "fetch",
      vi.fn().mockRejectedValue(new DOMException("Aborted", "AbortError")),
    );
    await expect(request("/health", undefined, c.signal)).rejects.toThrow(
      "cancelled",
    );
  });
});
describe("follow-up and comparison contracts", () => {
  it("displays successful validated follow-up with stored context", async () => {
    vi.spyOn(api, "explain").mockResolvedValue({
      ...bundle.explanation,
      status: "ok",
      message: "Validated follow-up",
      text: "Mocked validated temperature explanation.",
      provider: "mock",
      model: "mock",
    });
    await submit();
    fireEvent.click(
      await screen.findByRole("button", { name: "Ask follow-up" }),
    );
    expect(
      await screen.findByText("Mocked validated temperature explanation."),
    ).toBeInTheDocument();
    const session = vi.mocked(api.analyze).mock.calls[0][1];
    expect(api.explain).toHaveBeenCalledWith(
      session,
      bundle.context_id,
      expect.any(String),
      "en",
      expect.any(AbortSignal),
    );
  });
  it("retains environmental results when follow-up is rejected", async () => {
    vi.spyOn(api, "explain").mockResolvedValue({
      ...bundle.explanation,
      status: "unsupported",
      message: "Humidity absent from context",
    });
    await submit();
    fireEvent.change(await screen.findByLabelText("Contextual follow-up"), {
      target: { value: "What is the humidity?" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Ask follow-up" }));
    expect(
      await screen.findByText("Humidity absent from context"),
    ).toBeInTheDocument();
    expect(screen.getAllByText(/11.9/).length).toBeGreaterThan(0);
  });
  it("clears results and creates a new conversation", async () => {
    await submit();
    await screen.findByRole("button", { name: "Ask follow-up" });
    fireEvent.click(screen.getByRole("button", { name: "New conversation" }));
    expect(
      screen.queryByRole("heading", { name: "Your question" }),
    ).not.toBeInTheDocument();
    expect(
      screen.queryByLabelText("Contextual follow-up"),
    ).not.toBeInTheDocument();
  });
  it("sends supported comparison through trained NLP", async () => {
    mount("/comparison");
    await screen.findByLabelText("Gangtok");
    fireEvent.click(
      screen.getByRole("button", { name: "Compare town points" }),
    );
    await waitFor(() => expect(api.session).toHaveBeenCalled());
    expect(api.analyze).toHaveBeenCalledWith(
      "Compare temperature and rainfall in Gangtok and Namchi from 2025-01-01 to 2025-01-07.",
      expect.any(String),
      "trained",
      expect.any(AbortSignal),
    );
  });
  it("requires exactly two comparison towns", async () => {
    mount("/comparison");
    fireEvent.click(await screen.findByLabelText("Mangan"));
    fireEvent.click(
      screen.getByRole("button", { name: "Compare town points" }),
    );
    expect(await screen.findByRole("alert")).toHaveTextContent(
      "Select exactly two",
    );
    expect(api.analyze).not.toHaveBeenCalled();
  });
  it("preserves the detected Hindi explanation language", async () => {
    vi.mocked(api.analyze).mockResolvedValue({
      ...analysis,
      language: { code: "hi", confidence: 0.9 },
    });
    await submit();
    await waitFor(() =>
      expect(api.session).toHaveBeenCalledWith(
        expect.anything(),
        expect.any(String),
        "live",
        "hi",
        expect.any(AbortSignal),
      ),
    );
  });
  it("keeps analytics across page navigation", async () => {
    await submit();
    await screen.findByRole("button", { name: "Ask follow-up" });
    fireEvent.click(screen.getByRole("link", { name: "Climate analytics" }));
    expect(screen.getAllByText(/11.9/).length).toBeGreaterThan(0);
  });
  it("retains analysis when environmental retrieval fails", async () => {
    vi.mocked(api.session).mockRejectedValue(
      new Error("Environmental retrieval unavailable"),
    );
    await submit();
    expect(await screen.findByRole("alert")).toHaveTextContent(
      "Environmental retrieval unavailable",
    );
    expect(
      screen.getByRole("heading", { name: "Your question" }),
    ).toBeInTheDocument();
  });
});
describe("explicit question routing", () => {
  const knowledge = {
    topic: "era5",
    title: "ERA5 reanalysis",
    text: "Curated reference description, not town measurements.",
    language: "en" as const,
    label: "General environmental knowledge · not measured data",
    sources: [
      {
        name: "Open-Meteo",
        url: "https://open-meteo.com/en/docs/historical-weather-api",
      },
    ],
  };
  it("separates reference knowledge without NLP, AI calls or charts", async () => {
    vi.mocked(api.route).mockResolvedValue({
      category: "general_knowledge",
      message: knowledge.label,
      knowledge,
    });
    mount("/assistant");
    fireEvent.change(screen.getByLabelText("Environmental question"), {
      target: { value: "What is ERA5 reanalysis?" },
    });
    fireEvent.click(
      screen.getByRole("button", { name: /Analyze environment/ }),
    );
    expect(
      await screen.findByRole("heading", { name: "ERA5 reanalysis" }),
    ).toBeInTheDocument();
    expect(screen.getByText(knowledge.text)).toBeInTheDocument();
    expect(api.analyze).not.toHaveBeenCalled();
    expect(api.session).not.toHaveBeenCalled();
    expect(screen.queryByRole("img")).not.toBeInTheDocument();
  });
  it.each(["unsupported", "clarification"] as const)(
    "shows %s without invented model results",
    async (category) => {
      vi.mocked(api.route).mockResolvedValue({
        category,
        message: "Choose a supported town, measurement and period.",
        knowledge: null,
      });
      mount("/assistant");
      fireEvent.click(
        screen.getByRole("button", { name: /Analyze environment/ }),
      );
      expect(
        await screen.findByText(
          "Choose a supported town, measurement and period.",
        ),
      ).toBeInTheDocument();
      expect(api.analyze).not.toHaveBeenCalled();
      expect(screen.queryByText("NLP ANALYSIS")).not.toBeInTheDocument();
    },
  );
  it("routes a main-input follow-up to the same server context without new NLP", async () => {
    vi.spyOn(api, "explain").mockResolvedValue({
      ...bundle.explanation,
      status: "unsupported",
      message: "Comparison requires two complete town results.",
    });
    await submit();
    await screen.findByRole("button", { name: "Ask follow-up" });
    const session = vi.mocked(api.analyze).mock.calls[0][1];
    vi.mocked(api.route).mockResolvedValue({
      category: "contextual",
      message: "Stored context",
      knowledge: null,
    });
    fireEvent.change(screen.getByLabelText("Environmental question"), {
      target: { value: "Which town was warmer?" },
    });
    fireEvent.click(
      screen.getByRole("button", { name: /Analyze environment/ }),
    );
    await screen.findByText("Comparison requires two complete town results.");
    expect(api.analyze).toHaveBeenCalledTimes(1);
    expect(api.explain).toHaveBeenCalledWith(
      session,
      bundle.context_id,
      "Which town was warmer?",
      "en",
      expect.any(AbortSignal),
    );
    expect(screen.getAllByText(/11.9/).length).toBeGreaterThan(0);
  });
  it("retains previous environmental context across general knowledge", async () => {
    await submit();
    await screen.findByRole("button", { name: "Ask follow-up" });
    vi.mocked(api.route).mockResolvedValue({
      category: "general_knowledge",
      message: knowledge.label,
      knowledge,
    });
    fireEvent.change(screen.getByLabelText("Environmental question"), {
      target: { value: "What is ERA5?" },
    });
    fireEvent.click(
      screen.getByRole("button", { name: /Analyze environment/ }),
    );
    await screen.findByRole("heading", { name: "ERA5 reanalysis" });
    expect(
      screen.queryByRole("heading", { name: "Your question" }),
    ).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole("link", { name: "Climate analytics" }));
    expect(screen.getAllByText(/11.9/).length).toBeGreaterThan(0);
  });
});
