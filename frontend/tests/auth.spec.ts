import { readFile, stat } from "node:fs/promises";
import { resolve } from "node:path";
import { expect, test } from "@playwright/test";

// Authentication payloads must never enter trace, screenshots or video artifacts.
test.use({ trace: "off", screenshot: "off", video: "off" });

test("same-origin auth proxy keeps cookies HttpOnly and enforces logout CSRF", async ({ page }) => {
  const path = resolve(__dirname, "../../.local/demo/credentials.json");
  const info = await stat(path);
  expect(info.mode & 0o777).toBe(0o600);
  const saved = JSON.parse(await readFile(path, "utf8"));
  const email = "analyst@sentinel-demo.invalid";
  if (saved.purpose !== "LOCAL_SYNTHETIC_DEMO_ONLY" || typeof saved.accounts[email] !== "string") {
    throw new Error("Existing local fictional credentials are required; no credentials regenerated.");
  }
  await page.goto("/");
  const result = await page.evaluate(async ({ email, password }) => {
    const bootstrap = await fetch("/api/v1/auth/csrf");
    const preauth = await bootstrap.json();
    const login = await fetch("/api/v1/auth/login", {
      method: "POST", headers: { "Content-Type": "application/json", "X-CSRF-Token": preauth.csrf_token },
      body: JSON.stringify({ email, password }),
    });
    const identity = await login.json();
    if (!login.ok) return { login: login.status };
    const me = await fetch("/api/v1/auth/me");
    const visible = document.cookie.includes("sentinel_session");
    const denied = await fetch("/api/v1/auth/logout", { method: "POST" });
    const logout = await fetch("/api/v1/auth/logout", {
      method: "POST", headers: { "X-CSRF-Token": identity.csrf_token },
    });
    const after = await fetch("/api/v1/auth/me");
    return { login: login.status, me: me.status, role: identity.role,
      visible, denied: denied.status, logout: logout.status, after: after.status };
  }, { email, password: saved.accounts[email] });
  expect(result).toEqual({ login: 200, me: 200, role: "ANALYST", visible: false,
    denied: 403, logout: 204, after: 401 });
  const cookies = await page.context().cookies();
  expect(cookies.some(cookie => cookie.name.includes("sentinel_session"))).toBe(false);
});
