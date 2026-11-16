// Rendering tests over backend response fixtures; no genuine trained/provider inference.
import { afterEach, it, expect } from "vitest";
import { render, screen, cleanup } from "@testing-library/react";
import "@testing-library/jest-dom/vitest";
import Inspector from "../src/PipelineInspector";
import type { Run, Explanation } from "../src/contracts";
import analysis from "./analysis.json";
import bundle from "./bundle.json";
import explanations from "./explanations.json";
afterEach(cleanup);
const run = {
  question: "Fixture query",
  analysis,
  bundle,
  mode: "demo",
  source: "snapshot",
} as Run;
it("is collapsed by default and distinguishes all three stages", () => {
  render(
    <Inspector
      run={run}
      route={null}
      explanation={bundle.explanation as Explanation}
      configured={{
        provider: "disabled",
        configured: false,
        generation: "validated",
        context_ttl_seconds: 900,
      }}
    />,
  );
  const details = screen.getByText("AI Pipeline Inspector").closest("details");
  expect(details).not.toHaveAttribute("open");
  expect(
    screen.getByText("A. Trained NLP / explicit rule demonstration"),
  ).toBeInTheDocument();
  expect(
    screen.getByText("B. Environmental data & deterministic analytics"),
  ).toBeInTheDocument();
  expect(screen.getByText("C. Grounded Generative AI")).toBeInTheDocument();
  expect(
    screen.getByText("Rule demonstration — not trained inference"),
  ).toBeInTheDocument();
  expect(screen.getByText(/Rule confidence is unmeasured/)).toBeInTheDocument();
});
it("shows actual environmental attribution, dates, statistics and coverage", () => {
  render(
    <Inspector
      run={run}
      route={null}
      explanation={null}
      configured={undefined}
    />,
  );
  expect(
    screen.getByRole("link", { name: "Environmental source", hidden: true }),
  ).toHaveAttribute("href", bundle.environment.results[0].source_url);
  expect(
    screen.getByText(/retrieved 2026-11-15T12:27:17.330464Z/),
  ).toBeInTheDocument();
  expect(document.body.textContent).toContain("11.899999999999999");
  expect(document.body.textContent).toContain("valid_days");
});
it("shows validated facts and source IDs from returned explanation", () => {
  const value = explanations.en as Explanation;
  const before = JSON.stringify(value);
  render(
    <Inspector
      run={{ ...run, mode: "trained" }}
      route={null}
      explanation={value}
      configured={undefined}
    />,
  );
  expect(screen.getByText("Trained NLP inference")).toBeInTheDocument();
  expect(
    screen.getByText("Explanation status: ok", { selector: "strong" }),
  ).toBeInTheDocument();
  expect(
    screen.getByRole("link", {
      name: "[s0] Open-Meteo / ERA5 reanalysis",
      hidden: true,
    }),
  ).toHaveAttribute("href", value.sources[0].url);
  expect(document.body.textContent).toContain("0:temperature_mean_c");
  expect(JSON.stringify(value)).toBe(before);
});
it("keeps failure status visible without inventing provider or model", () => {
  render(
    <Inspector
      run={run}
      route={null}
      explanation={
        {
          ...bundle.explanation,
          status: "unavailable",
          message: "Provider timeout [code=timeout]",
        } as Explanation
      }
      configured={undefined}
    />,
  );
  expect(
    screen.getByText("Explanation status: unavailable", { selector: "strong" }),
  ).toBeInTheDocument();
  expect(screen.getByText(/Provider timeout/)).toBeInTheDocument();
  expect(document.body.textContent).toContain("Model: Not exposed by backend");
});
it("does not misattribute previous measurements to general knowledge", () => {
  render(
    <Inspector
      run={run}
      route={{
        category: "general_knowledge",
        message: "Curated knowledge",
        knowledge: null,
      }}
      explanation={explanations.en as Explanation}
      configured={undefined}
    />,
  );
  expect(
    screen.getByText("Not invoked for this routing category."),
  ).toBeInTheDocument();
  expect(
    screen.getByText(
      "No environmental retrieval was performed for this routing answer.",
    ),
  ).toBeInTheDocument();
  expect(
    screen.getByText("No LLM call was made for this routing answer."),
  ).toBeInTheDocument();
  expect(
    screen.queryByRole("link", { name: "Environmental source", hidden: true }),
  ).not.toBeInTheDocument();
});
