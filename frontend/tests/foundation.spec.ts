import { expect, test } from "@playwright/test";
import AxeBuilder from "@axe-core/playwright";

for (const width of [320, 375, 768, 1024, 1440, 1920]) {
  test(`login fits ${width}px and supports keyboard navigation`, async ({ page }) => {
    const errors: string[] = [];
    page.on("pageerror", (error) => errors.push(error.message));
    await page.setViewportSize({ width, height: 900 });
    await page.goto("/");
    await expect(page).toHaveURL(/\/login$/);
    await expect(page).toHaveTitle("Sign in | SentinelAI");
    await expect(page.getByRole("heading", { level: 1 })).toHaveText("See the signal.Trace the reason.");
    expect(await page.locator("html").getAttribute("lang")).toBe("en");
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
    await page.keyboard.press("Tab");
    await expect(page.getByRole("link", { name: "Skip to main content" })).toBeFocused();
    await page.keyboard.press("Tab");
    const brand = page.getByRole("link", { name: "SentinelAI home" });
    await expect(brand).toBeFocused();
    expect(await brand.evaluate((element) => getComputedStyle(element).outlineStyle)).toBe("solid");
    expect((await brand.boundingBox())?.height).toBeGreaterThanOrEqual(44);
    await page.keyboard.press("Tab");
    await expect(page.getByLabel("Email address")).toBeFocused();
    await page.keyboard.press("Tab");
    await expect(page.getByLabel("Password", { exact: true })).toBeFocused();
    expect(errors).toEqual([]);
  });
}

test("both health endpoints reach the real API", async ({ request }) => {
  for (const [path, status] of [["live", "alive"], ["ready", "ready"]]) {
    const result = await request.get(`/api/v1/health/${path}`);
    expect(result.status()).toBe(200);
    expect(await result.json()).toEqual({ status });
  }
});

for (const route of ["/login", "/privacy", "/terms", "/not-a-real-page"]) {
  test(`${route} has no detected WCAG AA violations`, async ({ page }) => {
    await page.goto(route);
    expect((await new AxeBuilder({ page }).withTags(["wcag2a", "wcag2aa", "wcag21aa", "wcag22aa"]).analyze()).violations).toEqual([]);
  });
}

test("legal links, logo and 404 have working destinations", async ({ page }) => {
  await page.goto("/login");
  await page.getByRole("link", { name: "Privacy draft", exact: true }).click();
  await expect(page).toHaveTitle("Privacy draft | SentinelAI");
  await expect(page.getByText("Owner-review draft / Not final policy")).toBeVisible();
  await page.getByRole("link", { name: "Terms draft", exact: true }).click();
  await expect(page).toHaveTitle("Terms draft | SentinelAI");
  await page.getByRole("link", { name: "SentinelAI home" }).click();
  await expect(page).toHaveURL(/\/login$/);
  const missing = await page.goto("/not-a-real-page");
  expect(missing?.status()).toBe(404);
  await expect(page.getByRole("heading", { name: "This page is off the map." })).toBeVisible();
  await page.getByRole("link", { name: "Return to workspace" }).click();
  await expect(page).toHaveURL(/\/login$/);
});

test("unauthenticated dashboard never includes protected content", async ({ request, page }) => {
  const response = await request.get("/dashboard", { maxRedirects: 0 });
  expect(response.status()).toBe(307);
  expect(response.headers().location).toBe("/login?reason=expired");
  expect(await response.text()).not.toContain("Foundation is ready");
  await page.goto("/dashboard");
  await expect(page).toHaveURL(/\/login\?reason=expired$/);
  await expect(page.getByRole("status")).toContainText("Sign in again");
});

test("fonts fall back without remote requests; reduced motion and 200% text remain usable", async ({ page }) => {
  const remote: string[] = [];
  page.on("request", r => { if (/fonts\.(googleapis|gstatic)\.com/.test(r.url())) remote.push(r.url()); });
  await page.route("**/*.woff2", route => route.abort());
  await page.emulateMedia({ reducedMotion: "reduce" });
  await page.setViewportSize({ width: 375, height: 900 });
  await page.goto("/login");
  await page.addStyleTag({ content: "html { font-size: 200% }" });
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
  await expect(page.getByRole("button", { name: "Sign in to workspace" })).toBeVisible();
  expect(await page.getByLabel("Email address").evaluate(el => getComputedStyle(el).transitionDuration)).toBe("0s");
  expect(remote).toEqual([]);
});

test("sign-in cannot submit credentials before hydration or with JavaScript disabled", async ({ browser, baseURL }) => {
  const context = await browser.newContext({ javaScriptEnabled: false });
  const page = await context.newPage();
  await page.goto(`${baseURL}/login`);
  await expect(page.getByLabel("Email address")).toBeDisabled();
  await expect(page.getByLabel("Password", { exact: true })).toBeDisabled();
  await expect(page.getByRole("button", { name: "Sign in to workspace" })).toBeDisabled();
  await expect(page.getByText("Enable JavaScript to sign in with session protection.")).toBeVisible();
  await context.close();
});
