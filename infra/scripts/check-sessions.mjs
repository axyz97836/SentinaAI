import assert from "node:assert/strict";
import { chromium, expect } from "../../frontend/node_modules/@playwright/test/index.mjs";

// Runs only through the guarded disposable stack, using real elapsed server time.
export async function verifySessions({ credentials, pass }) {
  const browser = await chromium.launch();
  const origin = "http://127.0.0.1:18009";
  let step = "production sign-in";
  try {
    const idle = await browser.newPage();
    const active = await browser.newPage();
    async function login(page, role) {
      const email = `${role}@sentinel-demo.invalid`;
      await page.goto(`${origin}/login`);
      await page.getByLabel("Email address").fill(email);
      await page.getByLabel("Password", { exact: true }).fill(credentials.accounts[email]);
      await page.getByRole("button", { name: "Sign in to workspace" }).click();
      await expect(page).toHaveURL(`${origin}/dashboard`);
      await expect(page.getByRole("button", { name: "Sign out", exact: true })).toBeEnabled();
    }
    await login(idle, "analyst");
    await login(active, "admin");
    const staleCookie = (await active.context().cookies()).filter(c => c.name.endsWith("sentinel_session"))
      .map(c => `${c.name}=${c.value}`).join("; ");
    assert.ok(staleCookie, "Actual session cookie required");
    pass("real form login and server-verified workspace on the isolated production frontend");
    const started = Date.now();
    for (let interval = 1; interval <= 6; interval++) {
      step = `elapsed session interval ${interval}`;
      await new Promise(resolve => setTimeout(resolve, 51000));
      if (interval === 2) {
        assert.equal((await idle.request.get(`${origin}/api/v1/auth/me`)).status(), 401);
        await idle.evaluate(() => window.dispatchEvent(new Event("focus")));
        await expect(idle).toHaveURL(`${origin}/login?reason=expired`);
        await expect(idle.getByRole("status")).toContainText("Sign in again");
        pass("idle session expires after real inactivity and protected UI redirects on focus");
      }
      if (interval < 6) {
        assert.equal((await active.request.get(`${origin}/api/v1/auth/me`)).status(), 200);
      }
      console.log(`Observed ${Math.floor((Date.now() - started) / 1000)} seconds of real session time.`);
    }
    pass("activity keeps the session valid across five idle windows before the absolute deadline");
    step = "absolute expiration";
    assert.equal((await active.request.get(`${origin}/api/v1/auth/me`, { headers: { Cookie: staleCookie } })).status(), 401);
    await active.evaluate(() => window.dispatchEvent(new Event("focus")));
    await expect(active).toHaveURL(`${origin}/login?reason=expired`);
    await expect(active.getByRole("status")).toContainText("Sign in again");
    pass("absolute expiry rejects the original cookie despite activity and clears protected UI");
  } catch {
    // Browser request errors can include credentials; retain only the named step.
    throw new Error(`Elapsed session verification failed during ${step}; no credentials logged.`);
  } finally {
    await browser.close();
  }
}
