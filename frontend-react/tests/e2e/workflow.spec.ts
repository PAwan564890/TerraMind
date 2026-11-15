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
