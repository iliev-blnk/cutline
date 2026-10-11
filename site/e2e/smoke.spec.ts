import { expect, test } from "@playwright/test";

test("grid renders 36 clubs", async ({ page }) => {
  await page.goto("/");
  await expect(page.locator(".grid .row[data-club]")).toHaveCount(36);
});

test("forcing a result changes the home club's top-8 chance, and the hash restores it", async ({ page }) => {
  await page.goto("/");
  const fixture = page.locator(".fixture").first();
  const home = await fixture.getAttribute("data-home");
  const cell = page.locator(`.grid .row[data-club="${home}"] .top8`);
  const before = await cell.textContent();
  await fixture.click();
  await page.locator(".picker button", { hasText: "1–0" }).click();
  await expect(cell).not.toHaveText(before!, { timeout: 3000 });
  const url = page.url();
  expect(url).toContain("#f=");
  await page.goto("about:blank");
  await page.goto(url);
  await expect(page.locator(".fixture.forced").first()).toContainText("1–0");
  await expect(cell).not.toHaveText(before!, { timeout: 3000 });
});

test("record page lists the v0 snapshot with its MD2 fixtures", async ({ page }) => {
  await page.goto("record.html");
  const first = page.locator(".snapshot").first();
  await expect(first).toContainText("before Matchday 2");
  await expect(first.locator(".rfix")).toHaveCount(18);
});

test("method page loads", async ({ page }) => {
  await page.goto("method.html");
  await expect(page.locator("h1, p").first()).toContainText("cutline");
});
