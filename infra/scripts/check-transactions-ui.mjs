import assert from "node:assert/strict";
import { mkdir, readFile, readdir } from "node:fs/promises";
import { chromium, expect } from "../../frontend/node_modules/@playwright/test/index.mjs";
import AxeBuilder from "../../frontend/node_modules/@axe-core/playwright/dist/index.mjs";

// Real production frontend and disposable backend. No traces, videos, automatic
// screenshots or password-bearing failure contexts are enabled by this driver.
export async function verifyTransactionsUI({ compose, request, terminal, pass, marker, upload, credentials }) {
  const origin = "http://127.0.0.1:18010";
  const browser = await chromium.launch();
  const context = await browser.newContext({ viewport: { width: 1440, height: 1000 } });
  const page = await context.newPage();
  let step = "initial readiness";
  const check = name => { step = name; };
  const mutation = (path, value) => request(path, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(value) });
  const fixture = mode => compose("run", "--rm", "--no-deps", "-v", `${process.cwd()}/infra/scripts/check-scoring-db.py:/app/check_scoring_db.py:ro`, "api", "python", "check_scoring_db.py", mode);
  const payload = { external_id: "ui-partial", customer_ref: `${marker}ui`, occurred_at: "2026-02-01T10:00:00Z", amount: "1000.00", currency: "INR", merchant_category: "electronics", country_code: "IN", channel: "WEB", device_ref: "device-new" };
  async function login(target, role) {
    const email = `${role}@sentinel-demo.invalid`;
    try {
      await target.goto(`${origin}/login`);
      await target.getByLabel("Email address").fill(email);
      await target.getByLabel("Password", { exact: true }).fill(credentials.accounts[email]);
      await target.getByRole("button", { name: "Sign in to workspace" }).click();
      await expect(target).toHaveURL(`${origin}/dashboard`);
      await expect(target.getByRole("button", { name: "Sign out", exact: true })).toBeEnabled();
    } catch { throw new Error("Real form login failed; credentials omitted"); }
  }
  async function fillTransaction(value) {
    await page.goto(`${origin}/transactions?new=1`);
    await expect(page.getByRole("button", { name: "Submit for scoring" })).toBeEnabled();
    for (const [key, content] of Object.entries(value)) {
      if (key === "channel") await page.locator(`[name="${key}"]`).selectOption(content);
      else await page.locator(`[name="${key}"]`).fill(key === "occurred_at" ? content.replace(/:00Z$/, "") : content);
    }
  }
  async function submitTransaction(value) {
    await fillTransaction(value);
    await page.getByRole("button", { name: "Submit for scoring" }).click();
  }
  async function uploadUI(content, purpose = "SCORING", target = page) {
    await target.goto(`${origin}/transactions/upload`);
    await expect(target.getByRole("button", { name: "Upload CSV", exact: true })).toBeEnabled();
    await target.getByLabel("CSV file", { exact: true }).setInputFiles({ name: "synthetic-fixture.csv", mimeType: "text/csv", buffer: Buffer.from(content) });
    await target.getByLabel("Dataset purpose").selectOption(purpose);
    await target.getByRole("checkbox").check();
    await target.getByRole("button", { name: "Upload CSV", exact: true }).click();
    await expect(target).toHaveURL(/\/transactions\/upload\?job=[a-f0-9-]+$/);
    return new URL(target.url()).searchParams.get("job");
  }
  const csv = rows => `${Object.keys(payload).join(",")}\n${rows.map(row => Object.keys(payload).map(key => row[key]).join(",")).join("\n")}\n`;
  async function browserPost(target, path, data, invalidCSRF = false) {
    return target.evaluate(async ({ path, data, invalidCSRF }) => {
      const proof = (await (await fetch("/api/v1/auth/csrf")).json()).csrf_token;
      const response = await fetch(`/api/v1/${path}`, { method: "POST", headers: { "Content-Type": "application/json", "X-CSRF-Token": invalidCSRF ? "invalid" : proof }, body: JSON.stringify(data) });
      return response.status;
    }, { path, data, invalidCSRF });
  }
  try {
    for (const route of ["/transactions", "/transactions/upload", "/transactions/00000000-0000-0000-0000-000000000000"]) {
      const response = await page.request.get(`${origin}${route}`, { maxRedirects: 0 });
      console.log(`Anonymous route ${route}: HTTP ${response.status()}`);
      assert.equal(response.status(), 307);
      assert.ok(!((await response.text()).includes("Recorded transactions")));
    }
    pass("unauthenticated transaction routes redirect on the server without protected records");

    check("analyst login, empty state and no active model");
    await login(page, "analyst");
    check("analyst navigation to transaction list");
    await page.getByRole("navigation", { name: "Workspace", exact: true }).filter({ visible: true }).getByRole("link", { name: "Transactions", exact: true }).click();
    await expect(page.getByRole("heading", { name: "No matching transactions" })).toBeVisible();
    check("new transaction form without active model");
    await submitTransaction(payload);
    await expect(page.locator("main").getByRole("alert")).toContainText("activate a model");
    pass("real analyst navigation, organization empty state and ACTIVE_MODEL_REQUIRED feedback");

    check("inline synthetic-field validation");
    await fillTransaction({ ...payload, amount: "0", customer_ref: "customer1234567" });
    await page.getByRole("button", { name: "Submit for scoring" }).click();
    await expect(page.locator("#amount-error")).toContainText("greater than zero");
    await expect(page.locator("#customer_ref-error")).toContainText("seven consecutive digits");
    await expect(page.locator("#customer_ref")).toBeFocused();
    await page.locator("#external_id").fill("invalid!reference");
    assert.equal(await page.locator("#external_id").evaluate(el => el.validity.patternMismatch), true);
    pass("invalid amount and nonsynthetic references produce associated field errors and focus");

    check("mobile submission disclosure preserves values and backend errors");
    await page.setViewportSize({ width: 375, height: 1000 });
    await page.goto(`${origin}/transactions`);
    const newTransaction = page.getByRole("button", { name: "New simulated transaction", exact: true });
    await expect(newTransaction).toBeEnabled();
    await expect(newTransaction).toHaveAttribute("aria-expanded", "false");
    await expect(page.locator("#transaction-form-panel")).toBeHidden();
    await newTransaction.focus(); await page.keyboard.press("Enter");
    await expect(page.locator("#external_id")).toBeFocused();
    await page.locator("#external_id").fill("fictional-preserved-draft");
    await page.getByRole("button", { name: "Close form", exact: true }).click();
    await expect(newTransaction).toBeFocused();
    await expect(page.locator("#transaction-form-panel")).toBeHidden();
    await page.keyboard.press("Enter");
    await expect(page.locator("#external_id")).toBeFocused();
    await expect(page.locator("#external_id")).toHaveValue("fictional-preserved-draft");
    const outline = await page.locator("#external_id").evaluate(el => {
      const style = getComputedStyle(el);
      return { style: style.outlineStyle, width: style.outlineWidth, color: style.outlineColor };
    });
    assert.deepEqual(outline, { style: "solid", width: "3px", color: "rgb(4, 106, 56)" });
    console.log("Observed keyboard focus outline:", outline);
    await fillTransaction({ ...payload, amount: "0" });
    await page.getByRole("button", { name: "Submit for scoring" }).click();
    await expect(page.locator("#amount-error")).toContainText("greater than zero");
    await page.getByRole("button", { name: "Close form", exact: true }).click();
    await page.getByRole("button", { name: "New simulated transaction", exact: true }).click();
    await expect(page.locator("#amount")).toHaveValue("0");
    await expect(page.locator("#amount-error")).toContainText("greater than zero");
    await submitTransaction(payload);
    await expect(page.locator("main").getByRole("alert")).toContainText("activate a model");
    await expect(page.locator("#transaction-form-panel")).toBeVisible();
    await expect(page.getByRole("button", { name: "New simulated transaction", exact: true })).toHaveAttribute("aria-expanded", "true");
    await page.setViewportSize({ width: 1440, height: 1000 });
    pass("mobile form opens by keyboard, restores focus, retains draft values and stays open on real submission failure");

    check("failed scoring upload without active model");
    const noModelJob = await uploadUI(csv([payload]));
    assert.equal((await terminal(noModelJob)).error_code, "ACTIVE_MODEL_REQUIRED");
    await expect(page.getByRole("alert").filter({ hasText: "FAILED" })).toBeVisible();
    pass("real job-level scoring failure remains visibly FAILED");

    check("real isolated model training and activation");
    const trainingCSV = await compose("run", "--rm", "--no-deps", "api", "python", "-m", "app.ml.synthetic");
    const validated = await terminal(await upload(trainingCSV));
    assert.equal(validated.status, "SUCCEEDED");
    const started = await mutation("/admin/models/train", { training_dataset_id: validated.dataset_id });
    assert.equal(started.status, 202);
    const trained = await terminal((await started.json()).job_id);
    assert.equal(trained.status, "SUCCEEDED");
    assert.equal((await mutation(`/admin/models/${trained.model_version_id}/activate`, {})).status, 200);
    pass("real Linux ARM64 model training and activation in disposable resources only");

    check("real transaction submission and PARTIAL explanation");
    await submitTransaction(payload);
    await expect(page).toHaveURL(/\/transactions\/[a-f0-9-]+\?received=new$/);
    const partialId = new URL(page.url()).pathname.split("/").at(-1);
    const partial = await (await request(`/transactions/${partialId}/explanation`)).json();
    assert.equal(partial.explanation_status, "PARTIAL");
    await expect(page.getByRole("status").filter({ hasText: "Explanation PARTIAL" })).toBeVisible();
    await expect(page.locator("#risk-heading")).toHaveText(`${partial.risk_score} / 100`);
    await expect(page.locator(".tx-rule")).toHaveCount(3);
    await expect(page.locator(".tx-attributions li")).toHaveCount(partial.supervised_attribution.top_features.length);
    pass("real submission displays matching persisted score, genuine SHAP and honest PARTIAL rule evidence");

    check("identical replay and conflicting external ID");
    await submitTransaction(payload);
    await expect(page).toHaveURL(`${origin}/transactions/${partialId}?received=replay`);
    await expect(page.getByRole("status").filter({ hasText: "Already received" })).toBeVisible();
    await submitTransaction({ ...payload, amount: "2000.00" });
    await expect(page.locator("main").getByRole("alert")).toContainText("different transaction");
    pass("identical replay retains transaction ID; conflicting payload is rejected without invented score");

    check("COMPLETE evidence from real configured rules and prior history");
    await fixture("rules");
    for (const [external_id, occurred_at] of [["ui-prior-a", "2026-02-01T09:59:00Z"], ["ui-prior-b", "2026-02-01T09:59:30Z"]]) assert.equal((await mutation("/transactions", { ...payload, external_id, occurred_at, amount: "10.00", device_ref: "device-prior" })).status, 201);
    await submitTransaction({ ...payload, external_id: "ui-complete" });
    await expect(page).toHaveURL(/received=new$/);
    const completeId = new URL(page.url()).pathname.split("/").at(-1);
    const evidence = await (await request(`/transactions/${completeId}/explanation`)).json();
    assert.equal(evidence.explanation_status, "COMPLETE");
    assert.equal(evidence.rule_hits.length, 3);
    await expect(page.getByRole("status").filter({ hasText: "Explanation COMPLETE" })).toBeVisible();
    for (const feature of evidence.supervised_attribution.top_features) await expect(page.locator(".tx-attributions")).toContainText(feature.transformed_feature);
    await expect(page.locator(".tx-attributions li")).toHaveCount(evidence.supervised_attribution.top_features.length);
    pass("COMPLETE explanation renders persisted rule hits and model-specific supervised SHAP");

    check("independent mobile evidence disclosures and no-JavaScript evidence");
    await page.setViewportSize({ width: 375, height: 1000 });
    await page.goto(`${origin}/transactions/${partialId}`);
    await expect(page.getByRole("button", { name: "Sign out", exact: true })).toBeEnabled();
    await expect(page.getByText("Some rules were not evaluated.", { exact: false })).toBeVisible();
    await page.goto(`${origin}/transactions/${completeId}`);
    await expect(page.locator("#components-evidence")).toHaveAttribute("open", "");
    await expect(page.locator("#rules-evidence")).not.toHaveAttribute("open");
    await expect(page.locator("#shap-evidence")).not.toHaveAttribute("open");
    for (const id of ["rules-evidence", "shap-evidence"]) {
      await page.locator(`#${id} > summary`).focus(); await page.keyboard.press("Enter");
      await expect(page.locator(`#${id}`)).toHaveAttribute("open", "");
    }
    await page.locator("#components-evidence > summary").click();
    await expect(page.locator("#components-evidence")).not.toHaveAttribute("open");
    await expect(page.locator("#rules-evidence")).toHaveAttribute("open", "");
    await expect(page.locator("#shap-evidence")).toHaveAttribute("open", "");
    for (const feature of evidence.supervised_attribution.top_features) await expect(page.getByText(feature.transformed_feature, { exact: true })).toBeVisible();
    await expect(page.locator("#risk-heading")).toBeVisible();
    await expect(page.getByText("This score is a screening signal, not proof of fraud or a calibrated fraud probability.", { exact: true })).toBeVisible();
    assert.deepEqual((await new AxeBuilder({ page }).withTags(["wcag2a", "wcag2aa", "wcag21aa", "wcag22aa"]).analyze()).violations.map(v => v.id), []);
    const noJS = await browser.newContext({ javaScriptEnabled: false, viewport: { width: 375, height: 1000 } });
    await noJS.addCookies(await context.cookies());
    const staticPage = await noJS.newPage();
    await staticPage.goto(`${origin}/transactions/${completeId}`);
    await expect(staticPage.locator("#risk-heading")).toBeVisible();
    await expect(staticPage.locator(".tx-attributions li")).toHaveCount(evidence.supervised_attribution.top_features.length);
    await expect(staticPage.locator(".tx-attributions")).toBeVisible();
    await noJS.close();
    await page.setViewportSize({ width: 1440, height: 1000 });
    for (const id of ["components-evidence", "rules-evidence", "shap-evidence"]) await expect(page.locator(`#${id}`)).toHaveAttribute("open", "");
    pass("mobile evidence opens independently; essential/missing evidence stays visible; desktop and no-JS preserve all evidence");

    check("list filters and cursor pagination");
    for (let i = 0; i < 12; i++) assert.equal((await mutation("/transactions", { ...payload, external_id: `ui-list-${String(i).padStart(2, "0")}`, occurred_at: "2026-02-02T10:00:00Z" })).status, 201);
    await page.goto(`${origin}/transactions?search=ui-list&limit=10`);
    await expect(page.locator(".tx-table tbody tr")).toHaveCount(10);
    const firstRefs = await page.locator(".tx-table tbody th a").allTextContents();
    await page.getByRole("link", { name: "Next page", exact: true }).click();
    await expect(page.locator(".tx-table tbody tr")).toHaveCount(2);
    assert.ok((await page.locator(".tx-table tbody th a").allTextContents()).every(ref => !firstRefs.includes(ref)));
    await page.getByLabel("Search reference or customer").fill("ui-complete");
    await page.getByLabel("Risk band", { exact: true }).selectOption(evidence.risk_band);
    await page.getByLabel("From date").fill("2026-02-01");
    await page.getByLabel("Before date").fill("2026-02-02");
    await page.getByRole("button", { name: "Apply filters" }).click();
    assert.ok(!new URL(page.url()).searchParams.has("cursor"));
    await expect(page.locator(".tx-table tbody tr")).toHaveCount(1);
    await expect(page.locator(".tx-table tbody")).toContainText("ui-complete");
    await page.getByLabel("From date").fill("2026-02-02");
    await page.getByRole("button", { name: "Apply filters" }).click();
    await expect(page.locator("main").getByRole("alert")).toContainText("increasing date range");
    pass("real list search, band/date filters, invalid range and stable cursor pages; filter changes reset cursor");

    check("mobile filter disclosure, active state and cursor reset");
    await page.setViewportSize({ width: 375, height: 1000 });
    await page.goto(`${origin}/transactions?limit=10`);
    await expect(page.locator("#transaction-filters")).not.toHaveAttribute("open");
    await page.locator("#transaction-filters > summary").focus(); await page.keyboard.press("Enter");
    await expect(page.getByLabel("Search reference or customer")).toBeVisible();
    await page.getByLabel("Search reference or customer").fill("ui-list");
    await page.getByRole("button", { name: "Apply filters", exact: true }).click();
    await expect(page.locator("#transaction-filters > summary")).toContainText("active");
    await expect(page.locator("#transaction-filters")).toHaveAttribute("open", "");
    await page.getByRole("link", { name: "Next page", exact: true }).click();
    assert.ok(new URL(page.url()).searchParams.get("cursor"));
    await page.getByLabel("Search reference or customer").fill("ui-complete");
    await page.getByRole("button", { name: "Apply filters", exact: true }).click();
    assert.ok(!new URL(page.url()).searchParams.has("cursor"));
    await expect(page.locator(".tx-mobile .tx-card")).toHaveCount(1);
    assert.deepEqual((await new AxeBuilder({ page }).withTags(["wcag2a", "wcag2aa", "wcag21aa", "wcag22aa"]).analyze()).violations.map(v => v.id), []);
    await page.getByRole("link", { name: "Clear filters", exact: true }).click();
    await expect(page.locator("#transaction-filters")).not.toHaveAttribute("open");
    await page.setViewportSize({ width: 1440, height: 1000 });
    await expect(page.getByLabel("Search reference or customer")).toBeVisible();
    await page.getByLabel("Search reference or customer").focus();
    await page.setViewportSize({ width: 375, height: 1000 });
    await expect(page.locator("#transaction-filters > summary")).toBeFocused();
    await page.setViewportSize({ width: 1440, height: 1000 });
    pass("mobile filters expose active state, preserve real queries, reset opaque cursors and remain visible on desktop");

    check("SCORING upload and durable queued job");
    await compose("stop", "worker");
    const scoringJob = await uploadUI(csv([{ ...payload, external_id: "ui-csv-valid" }]));
    await expect(page.getByRole("status")).toContainText("QUEUED");
    await page.evaluate(() => window.dispatchEvent(new Event("pagehide")));
    await expect(page.getByRole("heading", { name: "Checking your session…" })).toBeVisible();
    await page.evaluate(() => window.dispatchEvent(new Event("pageshow")));
    await expect(page.getByRole("heading", { name: "Ingestion job", exact: true })).toBeVisible();
    await expect(page.getByRole("status")).toContainText("QUEUED");
    await page.reload();
    await expect(page.getByRole("status")).toContainText("QUEUED");
    await compose("start", "worker");
    assert.equal((await terminal(scoringJob)).status, "SUCCEEDED");
    await expect(page.getByRole("status")).toContainText("SUCCEEDED");
    await expect(page.getByText("Scoring finished.", { exact: false })).toBeVisible();
    assert.equal((await (await request("/transactions?search=ui-csv-valid")).json()).items.length, 1);
    let terminalPolls = 0;
    const observe = req => { if (req.url().endsWith(`/jobs/${scoringJob}`)) terminalPolls++; };
    page.on("request", observe);
    await new Promise(resolve => setTimeout(resolve, 4500));
    page.off("request", observe); assert.equal(terminalPolls, 0);
    pass("real CSV scoring job survives reload/worker pause, creates a transaction and stops terminal polling");

    check("row-partial scoring success");
    const rowJob = await uploadUI(csv([{ ...payload, external_id: "ui-csv-partial" }, { ...payload, amount: "2000.00" }]));
    const rowResult = await terminal(rowJob);
    assert.equal(rowResult.status, "SUCCEEDED"); assert.equal(rowResult.failed_rows, 1);
    await expect(page.getByRole("status")).toContainText("Completed with row errors");
    await expect(page.getByText("Row errors", { exact: true })).toBeVisible();
    pass("real duplicate-conflict row preserves partial success and bounded sanitized row errors");

    check("CSV client and server validation");
    await page.goto(`${origin}/transactions/upload`);
    await expect(page.getByRole("button", { name: "Upload CSV", exact: true })).toBeEnabled();
    await page.getByLabel("CSV file", { exact: true }).setInputFiles({ name: "too-large.csv", mimeType: "text/csv", buffer: Buffer.alloc(10 * 1024 * 1024 + 1, "a") });
    await page.getByRole("checkbox").check();
    await page.getByRole("button", { name: "Upload CSV", exact: true }).click();
    await expect(page.locator("main").getByRole("alert")).toContainText("10 MiB");
    await page.getByLabel("CSV file", { exact: true }).setInputFiles({ name: "invalid.csv", mimeType: "text/csv", buffer: Buffer.from("wrong,headers\na,b\n") });
    await page.getByRole("button", { name: "Upload CSV", exact: true }).click();
    await expect(page.locator("main").getByRole("alert")).toBeVisible();
    const invalidRowJob = await uploadUI(csv([{ ...payload, external_id: "ui-csv-invalid", amount: "NaN" }]));
    const invalidRowResult = await terminal(invalidRowJob);
    console.log(`Invalid scoring row: status=${invalidRowResult.status}, processed=${invalidRowResult.processed_rows}, failed=${invalidRowResult.failed_rows}`);
    assert.equal(invalidRowResult.status, "SUCCEEDED");
    assert.equal(invalidRowResult.processed_rows, 0);
    assert.equal(invalidRowResult.failed_rows, 1);
    assert.equal(invalidRowResult.errors[0].code, "INVALID_AMOUNT");
    assert.equal((await (await request("/transactions?search=ui-csv-invalid")).json()).items.length, 0);
    await expect(page.getByRole("status")).toContainText("Completed with row errors");
    await expect(page.getByText("No rows were accepted for scoring.", { exact: false })).toBeVisible();
    pass("oversized/schema-invalid files rejected; invalid scoring row records its error, creates no transaction and reports zero accepted rows");

    check("training role authorization and CSRF");
    await page.goto(`${origin}/transactions/upload`);
    await expect(page.locator("#purpose option")).toHaveCount(1);
    const denied = await page.evaluate(async () => {
      const proof = (await (await fetch("/api/v1/auth/csrf")).json()).csrf_token;
      const data = new FormData(); data.set("file", new Blob(["invalid"], { type: "text/csv" }), "synthetic.csv"); data.set("purpose", "TRAINING"); data.set("source_kind", "SYNTHETIC");
      return (await fetch("/api/v1/ingestions", { method: "POST", headers: { "X-CSRF-Token": proof }, body: data })).status;
    });
    assert.equal(denied, 403);
    assert.equal(await browserPost(page, "transactions", { ...payload, external_id: "ui-csrf-denied" }, true), 403);
    assert.equal((await request("/transactions", { method: "POST", headers: { "Content-Type": "application/json", Origin: "https://untrusted.invalid" }, body: JSON.stringify(payload) })).status, 403);
    await page.route("**/api/v1/transactions", route => route.continue({ headers: { ...route.request().headers(), "x-csrf-token": "invalid" } }));
    await submitTransaction({ ...payload, external_id: "ui-csrf-form-denied" });
    await expect(page.locator("main").getByRole("alert")).toContainText("security proof could not be verified");
    await page.unroute("**/api/v1/transactions");
    assert.equal((await (await request("/transactions?search=ui-csrf-form-denied")).json()).items.length, 0);
    pass("non-admin TRAINING, invalid CSRF and foreign Origin are rejected by the real backend");

    check("ADMIN training upload distinction");
    const admin = await browser.newPage(); await login(admin, "admin");
    const trainingJob = await uploadUI(trainingCSV, "TRAINING", admin);
    assert.equal((await terminal(trainingJob)).status, "SUCCEEDED");
    await expect(admin.getByText("This upload did not create scored transactions.", { exact: false })).toBeVisible();
    await admin.close();
    pass("ADMIN can upload real training data; UI explicitly distinguishes validation from transaction scoring");

    check("six-width responsiveness, accessibility, keyboard and screenshots");
    const folder = new URL("../../verification/phase-10/", import.meta.url);
    await mkdir(folder, { recursive: true });
    const screens = [["transactions", "/transactions?limit=10"], ["submission", "/transactions?new=1"], ["upload", `/transactions/upload?job=${rowJob}`], ["detail", `/transactions/${completeId}`]];
    for (const [name, path] of screens) {
      await page.goto(`${origin}${path}`);
      await expect(page.getByRole("button", { name: "Sign out", exact: true })).toBeEnabled();
      if (name === "upload") await expect(page.getByRole("status")).toContainText("Completed with row errors");
      await page.evaluate(() => document.fonts.ready);
      for (const width of [320, 375, 768, 1024, 1440, 1920]) {
        check(`${name}: responsive bounds at ${width}px`);
        await page.setViewportSize({ width, height: 1000 });
        assert.equal(await page.evaluate(() => document.documentElement.scrollWidth), width, `${name} overflow at ${width}px`);
        if ([375, 1440].includes(width)) {
          check(`${name}: automated accessibility at ${width}px`);
          assert.deepEqual((await new AxeBuilder({ page }).withTags(["wcag2a", "wcag2aa", "wcag21aa", "wcag22aa"]).analyze()).violations.map(v => ({ id: v.id, targets: v.nodes.map(n => n.target) })), []);
          check(`${name}: explicit screenshot at ${width}px`);
          if (name === "submission") await expect(page.locator("#transaction-form-panel")).toBeVisible();
          await page.screenshot({ path: new URL(`${name}-${width}-polished.png`, folder).pathname, fullPage: true });
        }
      }
    }
    await page.setViewportSize({ width: 375, height: 1000 });
    await page.getByRole("button", { name: "Open navigation" }).click();
    const drawer = page.getByRole("dialog");
    for (let i = 0; i < 10; i++) { await page.keyboard.press(i % 2 ? "Shift+Tab" : "Tab"); assert.ok(await drawer.evaluate(el => el.contains(document.activeElement))); }
    await page.keyboard.press("Escape"); await expect(page.getByRole("button", { name: "Open navigation" })).toBeFocused();
    await page.emulateMedia({ reducedMotion: "reduce" });
    assert.equal(await page.locator(".button").first().evaluate(el => getComputedStyle(el).transitionDuration), "0s");
    await page.addStyleTag({ content: "html {font-size:200%} * {font-family:Arial,sans-serif !important}" });
    assert.equal(await page.evaluate(() => document.documentElement.scrollWidth), 375);
    pass("four screens at six widths, eight axe scans, drawer keyboard, reduced motion, fallback/text scaling and eight real screenshots");

    check("foreign organization isolation");
    await fixture("isolation");
    for (const path of [`transactions/${completeId}`, `transactions/${completeId}/explanation`, `jobs/${rowJob}`]) assert.equal((await page.request.get(`${origin}/api/v1/${path}`)).status(), 404);
    const foreign = await page.request.get(`${origin}/transactions/${completeId}`);
    const foreignBody = await foreign.text();
    assert.ok(!foreignBody.includes("ui-complete") && !foreignBody.includes(trained.model_version_id));
    pass("foreign organization cannot retrieve transaction, explanation or job; protected page omits original records");

    check("logout, session revocation and secret-free artifacts");
    const oldCookie = (await page.context().cookies()).filter(c => c.name.endsWith("sentinel_session")).map(c => `${c.name}=${c.value}`).join("; ");
    await page.goto(`${origin}/transactions`);
    await page.getByRole("button", { name: "Sign out", exact: true }).click();
    await expect(page).toHaveURL(/reason=signed-out$/);
    assert.equal((await page.request.get(`${origin}/api/v1/transactions`, { headers: { Cookie: oldCookie } })).status(), 401);
    await page.goto(`${origin}/transactions/upload`); await expect(page).toHaveURL(/\/login\?reason=expired$/);
    for (const file of await readdir(folder)) {
      const bytes = await readFile(new URL(file, folder));
      for (const secret of Object.values(credentials.accounts)) assert.ok(!bytes.includes(Buffer.from(secret)), "No credential in captured artifacts");
    }
    pass("logout invalidates original cookie, protected routes redirect and screenshots contain no credential bytes");
  } catch (error) {
    // Named steps and public assertion metadata are useful; never dump browser call
    // logs, request bodies, cookies, DOM snapshots or automatic failure attachments.
    const reason = error?.code === "ERR_ASSERTION" ? `assertion failed${typeof error.actual === "number" && typeof error.expected === "number" ? ` (observed ${error.actual}, expected ${error.expected})` : ""}` : "browser or request check failed";
    let summary = String(error?.message ?? "Unknown failure").split("\n")[0];
    for (const secret of Object.values(credentials.accounts)) summary = summary.replaceAll(secret, "[redacted]");
    console.log("Sanitized error:", summary.replace(/[A-Za-z0-9_+/=.-]{24,}/g, "[redacted]"));
    console.log(`Failure location: ${new URL(page.url()).pathname}; visible headings: ${JSON.stringify(await page.getByRole("heading").allTextContents().catch(() => []))}`);
    if (new URL(page.url()).pathname.startsWith("/transactions")) console.log("Field validity (no values):", await page.locator("main input").evaluateAll(fields => fields.map(field => ({ name: field.name, valid: field.validity.valid, patternMismatch: field.validity.patternMismatch, badInput: field.validity.badInput, stepMismatch: field.validity.stepMismatch, valueMissing: field.validity.valueMissing }))));
    if (new URL(page.url()).pathname.startsWith("/transactions")) console.log("Application feedback:", await page.getByRole("alert").allTextContents());
    throw new Error(`Transaction UI verification failed during ${step}: ${reason}. No credentials logged.`);
  } finally { await browser.close(); }
}
