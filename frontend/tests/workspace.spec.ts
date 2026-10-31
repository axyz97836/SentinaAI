import { readFile, stat, mkdir } from "node:fs/promises";
import { resolve } from "node:path";
import { expect, test, type Page } from "@playwright/test";
import AxeBuilder from "@axe-core/playwright";

// Never record login payloads, passwords, cookies or CSRF proofs in traces/video.
test.use({ trace: "off", screenshot: "off", video: "off" });

async function signIn(page: Page, account: string) {
  const path = resolve(__dirname, "../../.local/demo/credentials.json");
  expect((await stat(path)).mode & 0o777).toBe(0o600);
  const saved = JSON.parse(await readFile(path, "utf8"));
  if (saved.purpose !== "LOCAL_SYNTHETIC_DEMO_ONLY" || typeof saved.accounts[account] !== "string") throw Error("Existing synthetic credentials required");
  await page.goto("/login");
  await page.getByLabel("Email address").fill(account);
  await page.getByLabel("Password", { exact: true }).fill(saved.accounts[account]);
  await page.getByRole("button", { name: "Sign in to workspace" }).click();
  await expect(page).toHaveURL(/\/dashboard$/);
  await expect(page.getByRole("heading", { name: "A place for clear decisions." })).toBeVisible();
}

for (const [account, role] of [["analyst", "Fraud analyst"], ["risk-manager", "Risk manager"], ["admin", "Administrator"]]) {
  test(`${account} signs in through the real form and revokes the session on logout`, async ({ page, context }) => {
    const errors: string[] = [];
    page.on("pageerror", error => errors.push(error.message));
    await signIn(page, `${account}@sentinel-demo.invalid`);
    await expect(page.locator(".account-role")).toHaveText(role);
    const cookie = (await context.cookies()).find(c => c.name.endsWith("sentinel_session"));
    expect(Boolean(cookie?.httpOnly && cookie.sameSite === "Lax")).toBe(true);
    expect(await page.evaluate(() => document.cookie.includes("sentinel_session"))).toBe(false);
    expect(await page.evaluate(() => localStorage.length + sessionStorage.length)).toBe(0);
    const nav = page.getByRole("navigation", { name: "Workspace", exact: true }).filter({ visible: true });
    await expect(nav.getByRole("link")).toHaveCount(1);
    await expect(nav.getByRole("link", { name: "Overview" })).toBeVisible();
    expect((await page.request.get("/api/v1/auth/me")).status()).toBe(200);
    if (account === "analyst") {
      await page.evaluate(() => document.fonts.ready);
      for (const width of [320, 375, 768, 1024, 1440, 1920]) {
        await page.setViewportSize({ width, height: 900 });
        const bounds = await page.evaluate(() => ({ viewport: innerWidth, document: document.documentElement.scrollWidth }));
        expect(bounds, `workspace layout at ${width}px`).toEqual({ viewport: width, document: width });
      }
      expect((await new AxeBuilder({ page }).withTags(["wcag2a", "wcag2aa", "wcag21aa", "wcag22aa"]).analyze()).violations).toEqual([]);
      if (process.env.PHASE9_SCREENSHOTS === "1") {
        const folder = resolve(__dirname, "../../verification/phase-9");
        await mkdir(folder, { recursive: true });
        for (const width of [1440, 375]) {
          await page.setViewportSize({ width, height: 900 });
          await page.screenshot({ path: `${folder}/workspace-${width}-refined.png`, fullPage: true });
        }
      }
    }
    const staleCookie = cookie ? `${cookie.name}=${cookie.value}` : "";
    await page.getByRole("button", { name: "Sign out", exact: true }).click();
    await expect(page).toHaveURL(/\/login\?reason=signed-out$/);
    await expect(page.getByRole("status")).toHaveText("You have been signed out.");
    expect((await page.request.get("/api/v1/auth/me", { headers: { Cookie: staleCookie } })).status()).toBe(401);
    await page.goBack();
    await expect(page.getByRole("heading", { name: "A place for clear decisions." })).toHaveCount(0);
    expect(errors).toEqual([]);
  });
}

test("mobile navigation traps focus, closes with Escape and restores focus", async ({ page }) => {
  await page.setViewportSize({ width: 375, height: 900 });
  await signIn(page, "risk-manager@sentinel-demo.invalid");
  const menu = page.getByRole("button", { name: "Open navigation" });
  await expect(menu).toBeEnabled();
  await menu.focus(); await page.keyboard.press("Enter");
  const dialog = page.getByRole("dialog", { name: "Navigation" });
  await expect(dialog).toBeVisible();
  await expect(menu).toHaveAttribute("aria-expanded", "true");
  for (let i = 0; i < 7; i++) {
    await page.keyboard.press("Tab");
    expect(await dialog.evaluate(el => el.contains(document.activeElement))).toBe(true);
  }
  expect((await new AxeBuilder({ page }).withTags(["wcag2a", "wcag2aa", "wcag21aa", "wcag22aa"]).analyze()).violations).toEqual([]);
  await page.keyboard.press("Escape");
  await expect(dialog).not.toBeVisible(); await expect(menu).toBeFocused();
  await expect(menu).toHaveAttribute("aria-expanded", "false");
  await menu.click();
  await expect(dialog).toBeVisible();
  await page.evaluate(() => window.dispatchEvent(new Event("focus")));
  await expect(menu).toBeEnabled();
  await expect(menu).toHaveAttribute("aria-expanded", "false");
  await expect(dialog).not.toBeVisible();
  await page.getByRole("button", { name: "Sign out", exact: true }).click();
  await expect(page).toHaveURL(/reason=signed-out/);
});

test("server-revoked session is hidden and redirected on focus", async ({ page }) => {
  await signIn(page, "admin@sentinel-demo.invalid");
  const revoked = await page.evaluate(async () => {
    const proof = await (await fetch("/api/v1/auth/csrf")).json();
    const response = await fetch("/api/v1/auth/logout", { method: "POST", headers: { "X-CSRF-Token": proof.csrf_token } });
    return response.status;
  });
  expect(revoked).toBe(204);
  await page.evaluate(() => window.dispatchEvent(new Event("focus")));
  await expect(page).toHaveURL(/\/login\?reason=expired$/);
  await expect(page.getByRole("status")).toContainText("Sign in again");
  await expect(page.getByRole("heading", { name: "A place for clear decisions." })).toHaveCount(0);
});

test("login validation, invalid credentials and unavailable backend give actionable feedback", async ({ page }) => {
  await page.goto("/login");
  await page.getByRole("button", { name: "Sign in to workspace" }).click();
  await expect(page.getByLabel("Email address")).toBeFocused();
  await expect(page.getByText("Enter a valid email address.")).toBeVisible();
  await page.getByLabel("Email address").fill("nonexistent@sentinel-demo.invalid");
  await page.getByLabel("Password", { exact: true }).fill("not-a-real-password");
  await page.getByRole("button", { name: "Sign in to workspace" }).click();
  await expect(page.getByRole("region", { name: "Welcome back." }).getByRole("alert")).toHaveText("Email or password is incorrect.");
  await page.route("**/api/v1/auth/csrf", route => route.abort());
  await page.getByRole("button", { name: "Sign in to workspace" }).click();
  await expect(page.getByRole("region", { name: "Welcome back." }).getByRole("alert")).toContainText("Check your connection");
  await expect(page.getByRole("button", { name: "Sign in to workspace" })).toBeEnabled();
});

test("capture credential-free login review images", async ({ page }) => {
  await page.goto("/login");
  await expect(page.getByLabel("Password", { exact: true })).toHaveValue("");
  if (process.env.PHASE9_SCREENSHOTS === "1") {
    const folder = resolve(__dirname, "../../verification/phase-9");
    await mkdir(folder, { recursive: true });
    await page.evaluate(() => document.fonts.ready);
    for (const width of [1440, 375]) {
      await page.setViewportSize({ width, height: 900 });
      await page.screenshot({ path: `${folder}/login-${width}-refined.png`, fullPage: true });
    }
  }
});
