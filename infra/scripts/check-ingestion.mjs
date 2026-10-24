import assert from "node:assert/strict";
import { execFile as execFileCallback, spawn } from "node:child_process";
import { mkdir, readFile, stat, writeFile } from "node:fs/promises";
import { fileURLToPath } from "node:url";
import { promisify } from "node:util";

const execFile = promisify(execFileCallback);
const root = fileURLToPath(new URL("../../", import.meta.url));
const project = "sentinelai-ingestion-tests";
const port = 18004;
const origin = `http://127.0.0.1:${port}`;
const api = `${origin}/api/v1`;
const composeArgs = ["compose", "-p", project, "-f", ".local/ingestion-tests.compose.json"];
const credentialPath = new URL("../../.local/demo/credentials.json", import.meta.url);
const credentialBytes = await readFile(credentialPath);
assert.equal((await stat(credentialPath)).mode & 0o777, 0o600);
const credentials = JSON.parse(credentialBytes);
assert.equal(credentials.purpose, "LOCAL_SYNTHETIC_DEMO_ONLY");
const email = "admin@sentinel-demo.invalid";
const cookies = new Map();
let csrf;
let passed = 0;
let ownsStack = false;
const started = new Date().toISOString();
const marker = process.argv.includes("--models") || process.argv.includes("--scoring") ? "fictional-c-" : "phase4-e2e-fictional-marker";
const header = "external_id,customer_ref,occurred_at,amount,currency,merchant_category,country_code,channel";
const row = `${marker},fictional-customer,2026-10-20T10:00:00Z,12.34,INR,grocery,IN,WEB`;
const csv = `${header}\n${row}\n`;
const pause = ms => new Promise(resolve => setTimeout(resolve, ms));
const pass = name => { passed++; console.log(`PASS ${passed}: ${name}`); };

async function compose(...args) {
  try {
    const result = await execFile("docker", [...composeArgs, ...args], {
      cwd: root, encoding: "utf8", timeout: 300000, maxBuffer: 8 * 1024 * 1024,
    });
    return result.stdout;
  } catch {
    throw new Error(`Compose ${args[0]} failed; inspect local service state.`);
  }
}

async function request(path, options = {}) {
  const response = await fetch(`${api}${path}`, {
    ...options, headers: {
      Origin: origin, Cookie: [...cookies].map(([k, v]) => `${k}=${v}`).join("; "),
      ...(csrf ? { "X-CSRF-Token": csrf } : {}), ...options.headers,
    }, signal: AbortSignal.timeout(20000),
  });
  for (const cookie of response.headers.getSetCookie()) {
    const [pair] = cookie.split(";");
    const split = pair.indexOf("=");
    cookies.set(pair.slice(0, split), pair.slice(split + 1));
  }
  return response;
}

async function poll(path, predicate, seconds = 150) {
  const deadline = Date.now() + seconds * 1000;
  while (Date.now() < deadline) {
    try {
      const response = await request(path);
      if (response.ok) {
        const result = await response.json();
        if (predicate(result)) return result;
      }
    } catch { /* A deliberate restart can briefly refuse a connection. */ }
    await pause(1000);
  }
  throw new Error("Verification state did not arrive before the deadline.");
}

async function upload(content = csv, purpose = "TRAINING") {
  const form = new FormData();
  form.set("purpose", purpose);
  form.set("source_kind", "SYNTHETIC");
  form.set("file", new Blob([content], { type: "text/csv" }), "phase4-fixture.csv");
  const response = await request("/ingestions", { method: "POST", body: form });
  assert.equal(response.status, 202, "Synthetic upload must be accepted");
  const job = await response.json();
  assert.equal(job.status, "QUEUED");
  return job.job_id;
}

async function inspect(id, mode = "present") {
  await compose("run", "--rm", "--no-deps", "-v",
    `${root}infra/scripts/check-ingestion-storage.py:/app/check_ingestion_storage.py:ro`,
    "api", "python", "check_ingestion_storage.py", id, mode);
}
const terminal = id => poll(`/jobs/${id}`, j => ["SUCCEEDED", "FAILED"].includes(j.status));
const ready = () => poll("/health/ready", j => j.status === "ready");

async function startWorkerOnly() {
  const id = (await compose("ps", "--all", "--quiet", "worker")).trim();
  assert.match(id, /^[a-f0-9]+$/);
  // Compose start also starts dependencies, which would undo the injected storage outage.
  await execFile("docker", ["start", id], { cwd: root, timeout: 30000 });
}

async function loginAs(email) {
  if (csrf) await request("/auth/logout", { method: "POST" });
  csrf = (await (await request("/auth/csrf")).json()).csrf_token;
  const login = await request("/auth/login", { method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email, password: credentials.accounts[email] }),
  });
  assert.equal(login.status, 200, "Existing synthetic login must succeed");
  csrf = (await login.json()).csrf_token;
}

async function prepareIsolatedStack() {
  const { stdout } = await execFile("docker", ["compose", "--env-file", ".env",
    "-f", "infra/compose.yaml", "config", "--format", "json"], { cwd: root });
  const config = JSON.parse(stdout);
  config.name = project;
  delete config.services.frontend;
  delete config.services["backend-checks"];
  for (const [name, volume] of Object.entries(config.volumes)) volume.name = `${project}_${name}`;
  for (const [name, network] of Object.entries(config.networks)) network.name = `${project}_${name}`;
  for (const service of Object.values(config.services)) {
    if (service.environment?.POSTGRES_DB) service.environment.POSTGRES_DB = "sentinelai_ingestion_test";
  }
  config.services.api.ports = [{ target: 8000, published: String(port), host_ip: "127.0.0.1", protocol: "tcp" }];
  config.services.api.environment.AUTH_ALLOWED_ORIGINS = origin;
  const migrationText = await readFile(new URL("../../.local/migration.env", import.meta.url), "utf8");
  const migrationPassword = migrationText.match(/^MIGRATION_DB_PASSWORD=([a-f0-9]{64})$/m)?.[1];
  assert.ok(migrationPassword, "Existing migration identity required");
  config.services.migration = {
    build: config.services.api.build,
    environment: { APP_ENV: "local", DB_HOST: "postgres", POSTGRES_DB: "sentinelai_ingestion_test",
      MIGRATION_DB_USER: "sentinel_migrator", MIGRATION_DB_PASSWORD: migrationPassword,
      APP_DB_USER: config.services.api.environment.APP_DB_USER },
    networks: ["services"], command: ["alembic", "upgrade", "head"],
  };
  await mkdir(new URL("../../.local/", import.meta.url), { recursive: true, mode: 0o700 });
  await writeFile(new URL("../../.local/ingestion-tests.compose.json", import.meta.url),
    JSON.stringify(config), { mode: 0o600 });
  assert.equal((await stat(new URL("../../.local/ingestion-tests.compose.json", import.meta.url))).mode & 0o777, 0o600);
  // Refuse to overwrite a still-running test; main resources are never addressed by this project.
  assert.equal((await compose("ps", "--all", "--quiet")).trim(), "", "Isolated test project already exists");
  ownsStack = true;
  await compose("up", "-d", "--build", "--wait", "postgres", "redis", "object-storage");
  const sql = await readFile(new URL("../postgres/provision-migrator.sql", import.meta.url), "utf8");
  await new Promise((resolve, reject) => {
    const child = spawn("docker", [...composeArgs, "exec", "-T", "postgres", "sh", "-ec",
      'psql -X -qAt -v ON_ERROR_STOP=1 -U "$POSTGRES_USER" -d "$POSTGRES_DB"'],
      { cwd: root, stdio: ["pipe", "ignore", "ignore"] });
    child.on("error", () => reject(new Error("Isolated migration provisioning failed")));
    child.on("close", code => code === 0 ? resolve() : reject(new Error("Isolated migration provisioning failed")));
    child.stdin.end(`\\set migration_password '${migrationPassword}'\n${sql}`);
  });
  await compose("run", "--rm", "--no-deps", "--build", "migration");
  // Match the credential file owner: root with cap_drop=ALL cannot read another UID's 0600 file.
  await compose("run", "--rm", "--no-deps", "--build", "--user", `${process.getuid()}:${process.getgid()}`, "-v",
    `${fileURLToPath(credentialPath)}:/run/demo/credentials.json:ro`, "api", "python", "-m", "app.seed");
  await compose("up", "-d", "--build", "--wait", "api", "worker");
  console.log("Isolated ingestion test stack ready; main services and volumes are untouched.");
}

try {
  await prepareIsolatedStack();
  await ready();
  await loginAs(email);
  if (process.argv.includes("--scoring")) {
    const { verifyScoring } = await import("./check-scoring.mjs");
    await verifyScoring({ compose, request, terminal, poll, ready, pass, loginAs, startWorkerOnly, marker, upload, inspect });
  } else if (process.argv.includes("--models")) {
    const { verifyModels } = await import("./check-models.mjs");
    await verifyModels({ compose, request, terminal, poll, ready, pass, loginAs, startWorkerOnly, marker });
  } else {
  const valid = await upload();
  const validated = await terminal(valid);
  assert.equal(validated.status, "SUCCEEDED");
  assert.equal(validated.processed_rows, 1);
  assert.equal(validated.attempt_count, 1);
  await inspect(valid);
  pass("authenticated upload, real Celery validation, durable counts, private object and no transactions");
  await inspect(valid, "redeliver");
  await pause(3000);
  const duplicate = await (await request(`/jobs/${valid}`)).json();
  assert.equal(duplicate.attempt_count, 1);
  assert.equal(duplicate.processed_rows, 1);
  pass("real duplicate task delivery preserves terminal counts");

  const invalid = await upload(csv.replace("12.34", "NaN"));
  const rejected = await terminal(invalid);
  assert.equal(rejected.error_code, "ROW_VALIDATION_FAILED");
  assert.equal(rejected.failed_rows, 1);
  await poll(`/jobs/${invalid}`, j => j.status === "FAILED" && !j.cleanup_pending);
  await inspect(invalid, "absent");
  pass("invalid row fails truthfully and rejected private object is deleted");

  const scoring = await terminal(await upload(csv, "SCORING"));
  assert.equal(scoring.status, "FAILED");
  assert.equal(scoring.error_code, "ACTIVE_MODEL_REQUIRED");
  pass("SCORING remains blocked without invented scores");

  const large = `${header}\n${Array.from({ length: 10001 }, (_, i) => row.replace(marker, `fictional-${i}`)).join("\n")}\n`;
  const overRows = await upload(large);
  assert.equal((await terminal(overRows)).error_code, "ROW_LIMIT_EXCEEDED");
  await poll(`/jobs/${overRows}`, j => !j.cleanup_pending);
  await inspect(overRows, "absent");
  pass("real worker rejects row 10,001 and cleanup removes the object");

  await compose("stop", "worker");
  const restart = await upload();
  await compose("restart", "api");
  await ready();
  assert.equal((await (await request(`/jobs/${restart}`)).json()).status, "QUEUED");
  await compose("start", "worker");
  assert.equal((await terminal(restart)).status, "SUCCEEDED");
  pass("PostgreSQL job survives API restart and stopped worker");

  await compose("stop", "worker", "redis");
  const broker = await upload();
  assert.equal((await (await request(`/jobs/${broker}`)).json()).status, "QUEUED");
  await compose("start", "redis", "worker");
  await ready();
  assert.equal((await terminal(broker)).status, "SUCCEEDED");
  pass("upload remains durable during broker outage and is published after recovery");

  await compose("stop", "worker");
  const retry = await upload();
  await compose("stop", "object-storage");
  await startWorkerOnly();
  const unavailable = await poll(`/jobs/${retry}`, j => j.error_code === "STORAGE_UNAVAILABLE" && j.attempt_count >= 1);
  assert.equal(unavailable.status, "QUEUED");
  assert.equal(unavailable.processed_rows, 0);
  const storageId = (await compose("ps", "--all", "--quiet", "object-storage")).trim();
  assert.match(storageId, /^[a-f0-9]+$/);
  const state = await execFile("docker", ["inspect", "--format", "{{.State.Running}}", storageId]);
  assert.equal(state.stdout.trim(), "false", "Storage must remain stopped through the failed worker attempt");
  assert.equal((await request("/health/ready")).status, 503);
  console.log(`Observed storage stopped; job QUEUED, attempt ${unavailable.attempt_count}, STORAGE_UNAVAILABLE, zero processed rows.`);
  await compose("start", "object-storage");
  await ready();
  const retried = await terminal(retry);
  assert.equal(retried.status, "SUCCEEDED");
  assert.ok(retried.attempt_count >= 2 && retried.attempt_count <= 3);
  assert.equal(retried.processed_rows, 1);
  pass("real storage outage retries with durable attempts and no duplicate progress");

  }
  const logs = await compose("logs", "--since", started, "api", "worker");
  assert.ok(logs.includes("http_request"), "API log capture must include actual requests");
  assert.ok(logs.includes("worker-1"), "Worker log capture must include the test worker");
  assert.ok(!logs.includes(marker), "Raw CSV must not enter logs");
  for (const secret of [...Object.values(credentials.accounts), ...cookies.values(), csrf]) {
    if (secret) assert.ok(!logs.includes(secret), "Credentials must not enter logs");
  }
  assert.ok(credentialBytes.equals(await readFile(credentialPath)), "Credentials must remain unchanged");
  pass("API/worker logs omit fixture rows and credentials; credential file unchanged");
} catch (error) {
  if (ownsStack) {
    try {
      const logs = await compose("logs", "--no-color", "api", "worker");
      await writeFile(new URL("../../.local/integration-failure.log", import.meta.url), logs,
        { mode: 0o600 });
    } catch { /* Preserve the original failure if diagnostics are unavailable. */ }
  }
  throw error;
} finally {
  // This fixed project owns only isolated test volumes, never the main development volumes.
  if (ownsStack) await compose("down", "--volumes", "--remove-orphans");
}
console.log(`${passed} ${process.argv.includes("--scoring") ? "scoring" : process.argv.includes("--models") ? "model" : "ingestion"} integration checks passed; isolated resources removed.`);
