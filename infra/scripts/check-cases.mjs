import assert from "node:assert/strict";

export async function verifyCases({ compose, request, terminal, pass, loginAs, marker, upload }) {
  const mutate = (path, body, method = "POST", headers = {}) => request(path, {
    method, headers: { "Content-Type": "application/json", ...headers }, body: JSON.stringify(body),
  });
  const csv = await compose("run", "--rm", "--no-deps", "api", "python", "-m", "app.ml.synthetic");
  const dataset = await terminal(await upload(csv));
  assert.equal(dataset.status, "SUCCEEDED");
  const train = await mutate("/admin/models/train", { training_dataset_id: dataset.dataset_id });
  assert.equal(train.status, 202);
  const trained = await terminal((await train.json()).job_id);
  assert.equal(trained.status, "SUCCEEDED");
  assert.equal((await mutate(`/admin/models/${trained.model_version_id}/activate`, {})).status, 200);
  const settings = await (await request("/admin/settings")).json();
  assert.equal((await mutate("/admin/settings", {
    medium_threshold: settings.medium_threshold, high_threshold: settings.high_threshold,
    critical_threshold: settings.critical_threshold, alert_threshold: 0, version: settings.version,
  }, "PATCH")).status, 200);
  pass("trusted real model activated; only disposable organization configured for deterministic alerts");

  let serial = 0;
  const evidence = [];
  async function score() {
    const response = await mutate("/transactions", {
      external_id: `case-fixture-${++serial}`, customer_ref: `${marker}cases`,
      occurred_at: "2026-02-01T10:00:00Z", amount: "1000.00", currency: "INR",
      merchant_category: "electronics", country_code: "IN", channel: "WEB", device_ref: "fictional-device",
    });
    assert.equal(response.status, 201);
    const result = await response.json();
    assert.ok(result.alert_id);
    const detail = await (await request(`/transactions/${result.transaction_id}`)).json();
    const explanation = await (await request(`/transactions/${result.transaction_id}/explanation`)).json();
    assert.equal(explanation.supervised_attribution.available, true);
    evidence.push({ id: result.transaction_id, score: detail.score, explanation });
    return result;
  }
  const resolution = { resolution: "INCONCLUSIVE", resolution_note: `${marker}fictional conclusion`, version: 2 };
  let lastCase;
  for (const role of ["analyst", "risk-manager", "admin"]) {
    await loginAs(`${role}@sentinel-demo.invalid`);
    const result = await score();
    const alerts = await (await request("/alerts?status=NEW&limit=100")).json();
    assert.ok(alerts.items.some(a => a.id === result.alert_id && a.transaction_id === result.transaction_id));
    const opened = await mutate(`/alerts/${result.alert_id}/cases`, { note: `${marker}opening` });
    assert.equal(opened.status, 201);
    const body = await opened.json();
    const path = `/cases/${body.case_id}`;
    lastCase = body.case_id;
    assert.equal(body.case.status, "OPEN");
    assert.equal(body.case.version, 1);
    assert.equal(body.alert_status, "IN_CASE");
    assert.equal((await mutate(`/alerts/${result.alert_id}/cases`, { note: `${marker}opening` })).status, 200);
    assert.equal((await mutate(`/alerts/${result.alert_id}/cases`, { note: "different" })).status, 409);
    assert.equal((await mutate(`${path}/resolve`, { ...resolution, version: 1 })).status, 409);
    const initial = await (await request(path)).json();
    assert.deepEqual(initial.events.map(e => e.action), ["CASE_OPENED"]);
    assert.equal(initial.alert.status, "IN_CASE");
    assert.equal((await mutate(path, { status: "IN_REVIEW", version: 1 }, "PATCH")).status, 200);
    assert.equal((await mutate(path, { status: "IN_REVIEW", version: 1 }, "PATCH")).status, 409);
    assert.equal((await mutate(`${path}/events`, { note: `${marker}<script>inert fictional text</script>` })).status, 201);
    const closed = await mutate(`${path}/resolve`, resolution);
    assert.equal(closed.status, 200);
    const closedBody = await closed.json();
    assert.equal(closedBody.status, "CLOSED");
    assert.equal(closedBody.version, 3);
    assert.equal(closedBody.closed_at, closedBody.updated_at);
    assert.deepEqual(await (await mutate(`${path}/resolve`, resolution)).json(), closedBody);
    assert.equal((await mutate(`${path}/resolve`, { ...resolution, resolution: "FALSE_POSITIVE" })).status, 409);
    assert.equal((await mutate(`${path}/events`, { note: "late" })).status, 409);
    assert.equal((await mutate(path, { status: "IN_REVIEW", version: 3 }, "PATCH")).status, 409);
    const final = await (await request(path)).json();
    assert.deepEqual(final.events.map(e => e.action), ["CASE_OPENED", "STATUS_CHANGED", "NOTE_ADDED", "CASE_CLOSED"]);
    const second = await score();
    const dismissed = await mutate(`/alerts/${second.alert_id}/dismiss`, { reason: `${marker}fictional dismissal` });
    assert.equal(dismissed.status, 200);
    assert.equal((await dismissed.json()).status, "DISMISSED");
    assert.equal((await mutate(`/alerts/${second.alert_id}/cases`, {})).status, 409);
    pass(`${role} completes real alert-to-resolution journey, exact retries and independent dismissal`);
  }

  const race = await score();
  const requests = await Promise.all(Array.from({ length: 4 }, () => mutate(`/alerts/${race.alert_id}/cases`, {})));
  assert.deepEqual(requests.map(r => r.status).sort(), [200, 200, 200, 201]);
  const cases = await Promise.all(requests.map(r => r.json()));
  assert.equal(new Set(cases.map(c => c.case_id)).size, 1);
  const racePath = `/cases/${cases[0].case_id}`;
  const reviews = await Promise.all([1, 2].map(() => mutate(racePath, { status: "IN_REVIEW", version: 1 }, "PATCH")));
  assert.deepEqual(reviews.map(r => r.status).sort(), [200, 409]);
  pass("concurrent HTTP opening creates one case; concurrent versioned updates have one winner");

  const noteRace = await Promise.all([
    mutate(`${racePath}/events`, { note: `${marker}race note` }), mutate(`${racePath}/resolve`, resolution),
  ]);
  assert.ok([201, 409].includes(noteRace[0].status));
  assert.equal(noteRace[1].status, 200);
  assert.equal((await mutate(`${racePath}/resolve`, resolution)).status, 200);
  const raceEvents = (await (await request(racePath)).json()).events;
  assert.equal(raceEvents.at(-1).action, "CASE_CLOSED");
  assert.equal(raceEvents.filter(e => e.action === "CASE_CLOSED").length, 1);
  pass("note-versus-resolution race preserves ordered read-only closure and idempotent retry");

  const triage = await score();
  const triageRace = await Promise.all([
    mutate(`/alerts/${triage.alert_id}/cases`, {}),
    mutate(`/alerts/${triage.alert_id}/dismiss`, { reason: `${marker}race dismissal` }),
  ]);
  assert.equal(triageRace.filter(r => r.status === 409).length, 1);
  assert.ok([200, 201].includes(triageRace.find(r => r.status !== 409).status));
  pass("simultaneous dismissal and case creation cannot both succeed");

  for (const path of [`/cases/${lastCase}/events`, `/alerts/${triage.alert_id}/dismiss`]) {
    assert.equal((await mutate(path, { note: "demo", reason: "demo" }, "POST", { "X-CSRF-Token": "invalid" })).status, 403);
  }
  assert.equal((await request("/cases?limit=101")).status, 422);
  assert.equal((await mutate(`/cases/${lastCase}/events`, { note: " " })).status, 422);
  assert.equal((await mutate(`/cases/${lastCase}/resolve`, { ...resolution, resolution: "OTHER" })).status, 422);
  pass("invalid CSRF, oversized pagination and invalid note/resolution requests fail safely");

  for (const original of evidence) {
    assert.deepEqual((await (await request(`/transactions/${original.id}`)).json()).score, original.score);
    assert.deepEqual(await (await request(`/transactions/${original.id}/explanation`)).json(), original.explanation);
  }
  const verified = JSON.parse(await compose("run", "--rm", "--no-deps", "-v",
    `${process.cwd()}/infra/scripts/check-cases-db.py:/app/check_cases_db.py:ro`, "api", "python", "check_cases_db.py"));
  assert.equal(verified.transactions, evidence.length);
  assert.equal(verified.closed_cases, 4);
  pass("SQL case/event/audit reconciliation and all historical scoring/explanation snapshots remain intact");

  await compose("run", "--rm", "--no-deps", "-v", `${process.cwd()}/infra/scripts/check-scoring-db.py:/app/check_scoring_db.py:ro`,
    "api", "python", "check_scoring_db.py", "isolation");
  await loginAs("analyst@sentinel-demo.invalid");
  assert.deepEqual((await (await request("/alerts")).json()).items, []);
  assert.deepEqual((await (await request("/cases")).json()).items, []);
  assert.equal((await request(`/cases/${lastCase}`)).status, 404);
  for (const [path, body, method] of [
    [`/alerts/${race.alert_id}/cases`, {}, "POST"],
    [`/alerts/${race.alert_id}/dismiss`, { reason: "demo" }, "POST"],
    [`/cases/${lastCase}`, { status: "IN_REVIEW", version: 3 }, "PATCH"],
    [`/cases/${lastCase}/events`, { note: "demo" }, "POST"],
    [`/cases/${lastCase}/resolve`, resolution, "POST"],
  ]) assert.equal((await mutate(path, body, method)).status, 404);
  await loginAs("admin@sentinel-demo.invalid");
  pass("real foreign-organization session cannot list, read or mutate investigation records");
}
