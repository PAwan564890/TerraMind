// Real HTTP with expanded registry. Recorded weather only; no live trained/Groq claim.
import { test, expect } from "@playwright/test";
test("real map markers change selections and trained comparison parameters", async ({
  page,
}) => {
  await page.goto("/map");
  await expect(page.getByLabel("Pelling", { exact: true })).toBeVisible();
  const point = page.getByRole("button", {
    name: "Map point Pelling",
    exact: true,
  });
  await expect(point).toBeVisible();
  await expect(point).toHaveAttribute("data-latitude", "27.30158");
  await expect(point).toHaveAttribute("data-longitude", "88.23266");
  await point.focus();
  await page.keyboard.press("Enter");
  await expect(page.getByLabel("Pelling", { exact: true })).toBeChecked();
  await expect(
    page.getByRole("link", { name: "Open these towns in trained comparison" }),
  ).toHaveAttribute("href", /loc%3Apelling/);
  await page
    .getByRole("link", { name: "Open these towns in trained comparison" })
    .click();
  await expect(page.getByLabel("Pelling", { exact: true })).toBeChecked();
  await expect(page.getByLabel("Gangtok", { exact: true })).toBeChecked();
});
test("selected snapshot data feeds real backend insights and retains correct seven-day rain", async ({
  page,
}) => {
  await page.goto("/map");
  await page.getByLabel("Namchi", { exact: true }).check();
  await page
    .getByRole("combobox", { name: "Data source", exact: true })
    .selectOption("snapshot");
  await page.getByRole("button", { name: "Retrieve selected points" }).click();
  await expect(
    page.getByText("What the retrieved period shows", { exact: true }),
  ).toBeVisible();
  await expect(page.getByText(/Explicit user-selected registry/)).toBeVisible();
  await expect(
    page.getByText("Gangtok − Namchi", { exact: true }),
  ).toBeVisible();
  await expect(
    page.getByText("2025-01-06", { exact: true }).first(),
  ).toBeVisible();
  await expect(page.getByText("11.9 mm", { exact: true })).toHaveCount(2);
  await expect(page.getByText("disabled", { exact: true })).toBeVisible();
});
test("mobile tile failure retains accessible selectors and backed selection state", async ({
  page,
}) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await page.route("**/tile.openstreetmap.org/**", (route) => route.abort());
  await page.goto("/map");
  await expect(page.getByText(/Basemap tiles unavailable/)).toBeVisible();
  await page.getByLabel("Pelling", { exact: true }).check();
  await expect(page.getByLabel("Pelling", { exact: true })).toBeChecked();
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= innerWidth,
    ),
  ).toBeTruthy();
});
test("pipeline inspector exposes actual rule/NLP distinction and source evidence using keyboard", async ({
  page,
}) => {
  await page.goto("/assistant");
  await page.getByLabel("Inference mode").selectOption("demo");
  await page.getByLabel("Environmental source").selectOption("snapshot");
  await page.getByRole("button", { name: "Analyze environment" }).click();
  await expect(
    page.getByRole("heading", { name: "Your question" }),
  ).toBeVisible();
  const summary = page.getByText("AI Pipeline Inspector", { exact: true });
  await expect(page.locator(".pipeline-inspector")).not.toHaveAttribute("open");
  await summary.focus();
  await page.keyboard.press("Enter");
  await expect(
    page.getByText("Rule demonstration — not trained inference", {
      exact: true,
    }),
  ).toBeVisible();
  await expect(
    page.getByRole("link", { name: "Environmental source", exact: true }),
  ).toHaveAttribute("href", /archive-api.open-meteo.com/);
  await expect(
    page.getByText("C. Grounded Generative AI", { exact: true }),
  ).toBeVisible();
  await expect(
    page
      .locator(".pipeline-inspector")
      .getByText("Explanation status: disabled", { exact: true }),
  ).toBeVisible();
});
