import assert from "node:assert/strict";

export async function verifyModels({ compose, request, terminal, poll, ready, pass, loginAs, startWorkerOnly, marker }) {
  const csv = await compose("run", "--rm", "--no-deps", "api", "python", "-m", "app.ml.synthetic");
  assert.ok(csv.includes(`,${marker}`), "Log marker must occur in the uploaded synthetic customer data");
  const form = new FormData();
  form.set("purpose", "TRAINING");
  form.set("source_kind", "SYNTHETIC");
  form.set("file", new Blob([csv], { type: "text/csv" }), "synthetic-training.csv");
  const uploaded = await request("/ingestions", { method: "POST", body: form });
  assert.equal(uploaded.status, 202);
  const upload = await uploaded.json();
  assert.equal((await terminal(upload.job_id)).status, "SUCCEEDED");
  pass("synthetic TRAINING CSV validated by real ingestion worker");

  const train = async () => {
    const response = await request("/admin/models/train", { method: "POST",
      headers: { "Content-Type": "application/json" }, body: JSON.stringify({ training_dataset_id: upload.dataset_id }) });
    assert.equal(response.status, 202);
    const job = await response.json();
    assert.equal(job.status, "QUEUED");
    return job.job_id;
  };
  const activate = id => request(`/admin/models/${id}/activate`, { method: "POST",
    headers: { "Content-Type": "application/json" }, body: "{}" });
  const inspect = (id, mode = "verify") => compose("run", "--rm", "--no-deps", "-v",
    `${process.cwd()}/infra/scripts/check-model-storage.py:/app/check_model_storage.py:ro`,
    "api", "python", "check_model_storage.py", id, mode);

  const firstJob = await train();
  const first = await terminal(firstJob);
  assert.equal(first.status, "SUCCEEDED");
  assert.equal(first.processed_rows, 2000);
  assert.equal(first.attempt_count, 1);
  assert.ok(first.model_version_id);
  assert.equal((await request("/models/active")).status, 409);
  const evidence = JSON.parse(await inspect(firstJob));
  assert.equal(evidence.private, true);
  assert.equal(evidence.metrics.sample_count, 400);
  console.log(`Measured synthetic held-out evaluation: ${JSON.stringify(evidence.metrics)}`);
  pass("real MODEL_TRAIN job produced verified private artifact and held-out metrics without auto-activation");
  await inspect(firstJob, "redeliver");
  await new Promise(resolve => setTimeout(resolve, 3000));
  assert.equal((await (await request(`/jobs/${firstJob}`)).json()).attempt_count, 1);
  assert.equal((await activate(first.model_version_id)).status, 200);
  assert.equal((await (await request("/models/active")).json()).id, first.model_version_id);
  pass("duplicate delivery preserves candidate; explicit ADMIN activation succeeds");

  for (const role of ["analyst", "risk-manager"]) {
    await loginAs(`${role}@sentinel-demo.invalid`);
    assert.equal((await request("/models/active")).status, 200);
    assert.equal((await request("/admin/models")).status, 403);
    assert.equal((await activate(first.model_version_id)).status, 403);
    assert.equal((await request("/admin/models/train", { method: "POST",
      headers: { "Content-Type": "application/json" }, body: JSON.stringify({ training_dataset_id: upload.dataset_id }) })).status, 403);
  }
  await loginAs("admin@sentinel-demo.invalid");
  assert.equal((await request(`/admin/models/${first.model_version_id}/activate`, { method: "POST",
    headers: { "Content-Type": "application/json", "X-CSRF-Token": "invalid" }, body: "{}" })).status, 403);
  pass("all roles read active metadata; non-admin training/activation and forged CSRF are denied");

  await compose("stop", "worker", "redis");
  const secondJob = await train();
  await compose("restart", "api");
  await poll(`/jobs/${secondJob}`, job => job.status === "QUEUED");
  await compose("start", "redis", "worker");
  await ready();
  const second = await terminal(secondJob);
  assert.equal(second.status, "SUCCEEDED");
  pass("training intent survives broker outage and API restart");
  await inspect(secondJob, "tamper");
  assert.equal((await activate(second.model_version_id)).status, 409);
  assert.equal((await (await request("/models/active")).json()).id, first.model_version_id);
  pass("tampered candidate fails activation and preserves previous active model");

  await compose("stop", "worker");
  const thirdJob = await train();
  await compose("stop", "object-storage");
  await startWorkerOnly();
  const retry = await poll(`/jobs/${thirdJob}`, job => job.error_code === "STORAGE_UNAVAILABLE");
  assert.equal(retry.status, "QUEUED");
  assert.equal(retry.attempt_count, 1);
  assert.equal((await request("/health/ready")).status, 503);
  await compose("start", "object-storage");
  await ready();
  const recovered = await terminal(thirdJob);
  assert.equal(recovered.status, "SUCCEEDED");
  assert.ok(recovered.attempt_count >= 2 && recovered.attempt_count <= 3);
  await inspect(thirdJob);
  pass("real storage outage recovers with bounded durable training attempts");
}
