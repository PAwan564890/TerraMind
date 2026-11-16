// Mocked HTTP/map unit tests over genuine recorded backend and provider fixtures.
import { afterEach, beforeEach, describe, it, expect, vi } from "vitest";
import {
  render,
  screen,
  fireEvent,
  cleanup,
  waitFor,
} from "@testing-library/react";
import "@testing-library/jest-dom/vitest";
import { MemoryRouter } from "react-router-dom";
import Geospatial from "../src/Geospatial";
import Insights from "../src/Insights";
import Measurements from "../src/Measurements";
import { api } from "../src/api";
import type {
  LocationRegistry,
  SelectedBundle,
  MeasurementResponse,
} from "../src/contracts";
import fixture from "./foundations.json";
vi.mock("../src/TownMap", () => ({
  default: ({
    towns,
    onSelect,
  }: {
    towns: { id: string; name: string }[];
    onSelect: (id: string) => void;
  }) => (
    <div>
      {towns.map((t) => (
        <button key={t.id} onClick={() => onSelect(t.id)}>
          Map point {t.name}
        </button>
      ))}
    </div>
  ),
}));
vi.mock("recharts", () => ({
  ResponsiveContainer: ({ children }: { children: React.ReactNode }) => (
    <div>{children}</div>
  ),
  LineChart: ({ data }: { data: unknown[] }) => (
    <div>Chart records: {data.length}</div>
  ),
  BarChart: () => null,
  Line: () => null,
  Bar: () => null,
  XAxis: () => null,
  YAxis: () => null,
  CartesianGrid: () => null,
  Tooltip: () => null,
  Legend: () => null,
}));
beforeEach(() => {
  vi.spyOn(api, "locations").mockResolvedValue({
    ...fixture.registry,
    supplemental_variables: ["HUMIDITY", "WIND_SPEED"],
  } as LocationRegistry);
  vi.spyOn(api, "selected").mockResolvedValue(
    fixture.selected as SelectedBundle,
  );
  vi.spyOn(api, "measurements").mockResolvedValue(
    fixture.measurements as MeasurementResponse,
  );
});
afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
});
function mount() {
  render(
    <MemoryRouter>
      <Geospatial />
    </MemoryRouter>,
  );
}
describe("geospatial integration", () => {
  it("populates actual backend registry names and coordinates", async () => {
    mount();
    await screen.findByLabelText("Pelling");
    expect(screen.getByText("27.30158, 88.23266")).toBeInTheDocument();
    expect(screen.getByText("Lachung", { selector: "th" })).toBeInTheDocument();
  });
  it("map selection drives a real selected-endpoint request contract", async () => {
    mount();
    fireEvent.click(
      await screen.findByRole("button", { name: "Map point Namchi" }),
    );
    fireEvent.click(
      screen.getByRole("button", { name: "Retrieve selected points" }),
    );
    await waitFor(() =>
      expect(api.selected).toHaveBeenCalledWith(
        ["loc:gangtok", "loc:namchi"],
        "2025-01-01",
        "2025-01-07",
        expect.any(String),
        "live",
        expect.any(AbortSignal),
      ),
    );
    await screen.findByText(/no trained NLP prediction/);
    expect(screen.getAllByText(/11.9/).length).toBeGreaterThan(0);
  });
  it("requires at most two selections and provides comparison navigation", async () => {
    mount();
    fireEvent.click(
      await screen.findByRole("button", { name: "Map point Namchi" }),
    );
    expect(
      screen.getByRole("link", {
        name: "Open these towns in trained comparison",
      }),
    ).toHaveAttribute(
      "href",
      "/comparison?town=loc%3Agangtok&town=loc%3Anamchi",
    );
    fireEvent.click(screen.getByRole("button", { name: "Map point Pelling" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("at most two");
  });
  it("keeps weather data if supplemental retrieval fails", async () => {
    vi.mocked(api.measurements).mockRejectedValue(
      new Error("Supplemental transport unavailable"),
    );
    mount();
    fireEvent.click(await screen.findByLabelText("Relative humidity · %"));
    fireEvent.click(
      screen.getByRole("button", { name: "Retrieve selected points" }),
    );
    expect(await screen.findByRole("alert")).toHaveTextContent(
      "Supplemental transport unavailable",
    );
    expect(screen.getAllByText(/11.9/).length).toBeGreaterThan(0);
  });
  it("reports registry failure without inventing markers", async () => {
    vi.mocked(api.locations).mockRejectedValue(
      new Error("Registry unavailable"),
    );
    mount();
    expect(await screen.findByRole("alert")).toHaveTextContent(
      "Registry unavailable",
    );
    expect(
      screen.queryByRole("button", { name: "Map point Pelling" }),
    ).not.toBeInTheDocument();
  });
});
describe("backend-derived insights", () => {
  it("shows deterministic extrema, differences, source period and tied dates", () => {
    render(<Insights value={fixture.selected.insights} />);
    expect(screen.getAllByText("2025-01-06").length).toBeGreaterThan(0);
    expect(screen.getAllByText(/Warmest available day/).length).toBe(2);
    expect(screen.getByText(/loc:gangtok − loc:namchi/)).toBeInTheDocument();
    expect(screen.getAllByText(/5 tied dates/).length).toBeGreaterThan(0);
  });
  it("preserves expired context status", () => {
    render(
      <Insights
        value={{
          status: "no_context",
          results: [],
          comparisons: [],
          message: "Expired context",
        }}
      />,
    );
    expect(screen.getByText(/Expired context/)).toBeInTheDocument();
  });
  it("renders supplemental units, daily rows and real source metadata", () => {
    render(
      <Measurements value={fixture.measurements as MeasurementResponse} />,
    );
    expect(
      screen.getByText("Daily mean relative humidity · 2 m"),
    ).toBeInTheDocument();
    expect(
      screen.getByText("Daily mean scalar wind speed · 10 m"),
    ).toBeInTheDocument();
    expect(screen.getAllByText("Chart records: 7")).toHaveLength(2);
    expect(
      screen.getByRole("link", { name: "Open-Meteo ERA5", hidden: true }),
    ).toHaveAttribute("href", fixture.measurements.results[0].source_url);
    expect(
      screen.getByText(/not included in the weather GenAI context/),
    ).toBeInTheDocument();
  });
});

it("partial retrieval is visibly incomplete while available insights remain inspectable", () => {
  render(
    <Insights
      value={{
        ...fixture.selected.insights,
        status: "unavailable",
        message: "Only one town retrieved; comparison unavailable.",
        results: fixture.selected.insights.results.slice(0, 1),
        comparisons: [],
      }}
    />,
  );
  expect(screen.getByText(/Only one town retrieved/)).toBeInTheDocument();
  expect(screen.getAllByText(/Warmest available day/)).toHaveLength(1);
  expect(screen.queryByText(/Warmer:/)).not.toBeInTheDocument();
});
