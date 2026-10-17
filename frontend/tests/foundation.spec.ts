import { expect, test } from "@playwright/test";
import AxeBuilder from "@axe-core/playwright";

for (const width of [320, 375, 768, 1024, 1440]) {
  test(`foundation fits ${width}px and supports keyboard navigation`, async ({ page }) => {
    const errors: string[] = [];
    page.on("pageerror", (error) => errors.push(error.message));
    await page.setViewportSize({ width, height: 900 });
    await page.goto("/");
    await expect(page).toHaveTitle("Local foundation | SentinelAI");
    await expect(page.getByRole("heading", { level: 1 })).toHaveText("Local foundation");
    expect(await page.locator("html").getAttribute("lang")).toBe("en");
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
    const link = page.getByRole("link", { name: "Check API liveness" });
    await page.keyboard.press("Tab");
    await expect(link).toBeFocused();
    expect(await link.evaluate((element) => getComputedStyle(element).outlineStyle)).toBe("solid");
    expect((await link.boundingBox())?.height).toBeGreaterThanOrEqual(44);
    await page.keyboard.press("Tab");
    await expect(page.getByRole("link", { name: "Check dependency readiness" })).toBeFocused();
    expect(errors).toEqual([]);
  });
}

test("both health links reach the real API", async ({ page }) => {
  for (const [label, status] of [["Check API liveness", "alive"], ["Check dependency readiness", "ready"]]) {
    await page.goto("/");
    const response = page.waitForResponse((result) => result.url().includes("/api/v1/health/"));
    await page.getByRole("link", { name: label }).click();
    const result = await response;
    expect(result.status()).toBe(200);
    expect(await result.json()).toEqual({ status });
  }
});

test("foundation has no detected WCAG AA accessibility violations", async ({ page }) => {
  await page.goto("/");
  const result = await new AxeBuilder({ page }).withTags(["wcag2a", "wcag2aa", "wcag21aa", "wcag22aa"]).analyze();
  expect(result.violations).toEqual([]);
});
