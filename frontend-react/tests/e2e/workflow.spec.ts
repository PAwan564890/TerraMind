// Genuine browser -> Vite proxy -> FastAPI. No mocked HTTP responses or provider.
// Requires demo-enabled backend; actual recorded data, no trained inference or live LLM.
import { test, expect } from "@playwright/test";
test("snapshot environmental workflow, disabled AI follow-up fallback", async ({
  page,
}) => {
  await page.goto("/");
  await expect(
    page.getByRole("banner").getByText("Connected", { exact: true }),
  ).toBeVisible();
  await page.getByRole("link", { name: "AI assistant", exact: true }).click();
  await page.getByLabel("Inference mode").selectOption("demo");
  await page.getByLabel("Environmental source").selectOption("snapshot");
  await page.getByRole("button", { name: "Analyze environment" }).click();
  await expect(
    page.getByRole("heading", { name: "Your question" }),
  ).toBeVisible();
  await expect(page.getByText("11.9 mm", { exact: true })).toHaveCount(2);
  await expect(page.getByText("disabled", { exact: true })).toBeVisible();
  await expect(
    page.getByText("2025-01-01 → 2025-01-07", { exact: true }),
  ).toBeVisible();
  await page.getByLabel("Contextual follow-up").fill("What is the humidity?");
  await page
    .getByRole("button", { name: "Ask follow-up", exact: true })
    .click();
  await expect(page.getByText("disabled", { exact: true })).toHaveCount(2);
  await page
    .getByRole("link", { name: "Climate analytics", exact: true })
    .click();
  await expect(page.getByText("11.9 mm", { exact: true })).toHaveCount(2);
  await page.screenshot({ path: "../work/react-desktop.png", fullPage: true });
});
test("mobile navigation and no horizontal document overflow", async ({
  page,
}) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto("/");
  await expect(
    page.getByRole("banner").getByText("Connected", { exact: true }),
  ).toBeVisible();
  await page.getByRole("link", { name: "AI assistant", exact: true }).click();
  await expect(page.getByLabel("Environmental question")).toBeVisible();
  await page.getByLabel("Inference mode").selectOption("demo");
  await page.getByLabel("Environmental source").selectOption("snapshot");
  await page.getByRole("button", { name: "Analyze environment" }).click();
  await expect(page.getByText("11.9 mm", { exact: true })).toHaveCount(2);
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= window.innerWidth,
    ),
  ).toBeTruthy();
  await page.screenshot({ path: "../work/react-mobile.png", fullPage: true });
});
test("proxy exposes actual OpenAPI and trained-model health", async ({
  request,
}) => {
  const response = await request.get("/api/openapi.json");
  expect(response.ok()).toBeTruthy();
  const schema = await response.json();
  for (const route of [
    "/health",
    "/system",
    "/nlp/analyze",
    "/environment/session",
    "/genai/explain",
  ])
    expect(schema.paths[route]).toBeTruthy();
  const health = await request.get("/api/health");
  expect(health.ok()).toBeTruthy();
  expect(typeof (await health.json()).models_loaded).toBe("boolean");
});
// Mock ONLY the successful explanation: real provider credentials are unavailable.
test("mocked AI presentation preserves facts and keyboard-accessible evidence on mobile", async ({
  page,
}) => {
  const { default: explanations } = await import("../explanations.json", {
    with: { type: "json" },
  });
  await page.setViewportSize({ width: 390, height: 844 });
  await page.route("**/api/environment/session", async (route) => {
    const response = await route.fetch();
    const body = await response.json();
    await route.fulfill({
      response,
      json: { ...body, explanation: explanations.en },
    });
  });
  await page.goto("/assistant");
  await expect(
    page.getByRole("option", { name: "Rule demonstration · not trained" }),
  ).toBeEnabled();
  await page.getByLabel("Inference mode").selectOption("demo");
  await page.getByLabel("Environmental source").selectOption("snapshot");
  await page.getByRole("button", { name: "Analyze environment" }).click();
  const summary = page.getByText("Evidence, citations & explanation details", {
    exact: true,
  });
  await expect(summary).toBeVisible();
  const details = page.locator("details").filter({ has: summary });
  await expect(details).not.toHaveAttribute("open");
  const text = explanations.en.text.split("\n\n");
  for (const fact of text.slice(1, 1 + explanations.en.claims.length))
    await expect(page.getByText(fact, { exact: true })).toBeVisible();
  await expect(page.getByText(text[0], { exact: true })).not.toBeVisible();
  await summary.focus();
  await page.keyboard.press("Enter");
  await expect(page.getByText(text[0], { exact: true })).toBeVisible();
  await expect(
    page.getByRole("link", { name: "Open original data [s0]", exact: true }),
  ).toHaveAttribute("href", explanations.en.sources[0].url);
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= innerWidth,
    ),
  ).toBeTruthy();
});
// Genuine FastAPI curated knowledge/routing; no LLM response interception.
test("general knowledge and unsupported measurements never create environmental charts", async ({
  page,
}) => {
  await page.goto("/assistant");
  await page
    .getByLabel("Environmental question")
    .fill("What does ERA5 reanalysis mean?");
  await page.getByRole("button", { name: "Analyze environment" }).click();
  await expect(
    page.getByRole("heading", { name: "ERA5 reanalysis", exact: true }),
  ).toBeVisible();
  await expect(
    page.getByText("GENERAL ENVIRONMENTAL KNOWLEDGE", { exact: true }),
  ).toBeVisible();
  await expect(page.locator(".chart[role=img]")).toHaveCount(0);
  await expect(
    page.getByRole("heading", { name: "Your question" }),
  ).toHaveCount(0);
  await page
    .getByLabel("Environmental question")
    .fill("Show humidity in Gangtok during January 2025");
  await page.getByRole("button", { name: "Analyze environment" }).click();
  await expect(
    page.getByText("UNSUPPORTED QUESTION", { exact: true }),
  ).toBeVisible();
  await expect(page.locator(".chart[role=img]")).toHaveCount(0);
});
