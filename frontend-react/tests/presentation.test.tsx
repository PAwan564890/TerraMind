// Server-template fixtures from recorded data; no live LLM was used.
import { afterEach, describe, it, expect, vi } from "vitest";
import { render, screen, cleanup, fireEvent } from "@testing-library/react";
import "@testing-library/jest-dom/vitest";
import { AIExplanation, explanationParts, Metrics } from "../src/Results";
import { formatMetric } from "../src/format";
import type { Explanation, Bundle } from "../src/contracts";
import explanations from "./explanations.json";
import bundleJSON from "./bundle.json";
const bundle = bundleJSON as Bundle;
afterEach(cleanup);
describe("display precision", () => {
  it.each([
    [11.228571428571428, "°C", "11.23"],
    [11.899999999999999, "mm", "11.9"],
    [20, "°C", "20.00"],
    [0, "mm", "0.0"],
    [-4.12345, "°C", "-4.12"],
    [null, "mm", "Unavailable"],
  ] as const)("formats %s %s only at display", (value, unit, expected) =>
    expect(formatMetric(value, unit)).toBe(expected),
  );
  it("leaves the complete original response unchanged", () => {
    const before = JSON.stringify(bundle);
    render(<Metrics result={bundle.environment.results[0]} />);
    expect(screen.getByText(/11.23/)).toBeInTheDocument();
    expect(JSON.stringify(bundle)).toBe(before);
    expect(bundle.environment.results[0].summary.rainfall_total_mm).toBe(
      11.899999999999999,
    );
  });
});
describe("concise multilingual explanation", () => {
  it.each(["en", "hi", "ne"] as const)(
    "retains every original paragraph and exact facts in %s",
    (lang) => {
      const value = explanations[lang] as Explanation;
      const before = JSON.stringify(value);
      const parts = explanationParts(value)!;
      expect(parts).not.toBeNull();
      render(<AIExplanation value={value} />);
      const details = screen
        .getByText("Evidence, citations & explanation details")
        .closest("details")!;
      expect(details).not.toHaveAttribute("open");
      for (const text of parts.facts) {
        const paragraph = screen.getByText(text);
        expect(details.contains(paragraph)).toBe(false);
      }
      expect(details.textContent).toContain(parts.notice);
      parts.sources.forEach((text) =>
        expect(details.textContent).toContain(text),
      );
      expect(
        [parts.notice, ...parts.facts, ...parts.sources].join("\n\n"),
      ).toBe(value.text);
      expect(screen.getByText(parts.notice).closest("p")).toHaveAttribute(
        "lang",
        lang,
      );
      expect(screen.getAllByText(value.message)).toHaveLength(1);
      expect(
        screen.getByRole("link", {
          name: "Open original data [s0]",
          hidden: true,
        }),
      ).toHaveAttribute("href", value.sources[0].url);
      expect(JSON.stringify(value)).toBe(before);
    },
  );
  it("falls back to verbatim output for an unfamiliar layout", () => {
    const value = {
      ...explanations.en,
      text:
        explanations.en.text +
        "\n\nAdditional scientifically important limitation.",
    } as Explanation;
    expect(explanationParts(value)).toBeNull();
    render(<AIExplanation value={value} />);
    expect(document.querySelector(".explanation")?.textContent).toBe(
      value.text,
    );
  });
  it("keeps unavailable-provider messages visible", () => {
    render(<AIExplanation value={bundle.explanation} />);
    expect(screen.getByText(bundle.explanation.message)).toBeInTheDocument();
    expect(
      screen.queryByText("Evidence, citations & explanation details"),
    ).not.toBeInTheDocument();
  });
});

describe("comparison summaries", () => {
  it("uses labelled unit-aware cards without raw float tails", async () => {
    const { default: Comparison } = await import("../src/Comparison");
    const { api } = await import("../src/api");
    const { default: system } = await import("./system.json");
    const { default: analysis } = await import("./analysis.json");
    const original = JSON.stringify(bundle);
    vi.spyOn(api, "analyze").mockResolvedValue(
      analysis as import("../src/contracts").Analysis,
    );
    vi.spyOn(api, "session").mockResolvedValue(bundle);
    try {
      render(<Comparison system={system} />);
      fireEvent.click(
        screen.getByRole("button", { name: "Compare town points" }),
      );
      await screen.findAllByText(/11.23/);
      const cards = document.querySelector(".comparison-summary")!;
      expect(cards.textContent).toContain("Mean temperature");
      expect(cards.textContent).toContain("11.23");
      expect(cards.textContent).toContain("Rainfall total");
      expect(cards.textContent).toContain("11.9");
      expect(cards.textContent).toContain("Asia/Kolkata");
      expect(cards.textContent).toContain("2025-01-07");
      expect(cards.textContent).not.toContain("11.228571428571428");
      expect(JSON.stringify(bundle)).toBe(original);
    } finally {
      vi.restoreAllMocks();
    }
  });
});
