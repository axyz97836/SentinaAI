import assert from "node:assert/strict";
import { execFile as execFileCallback } from "node:child_process";
import { readFile } from "node:fs/promises";
import { fileURLToPath } from "node:url";
import { promisify } from "node:util";

const execFile = promisify(execFileCallback);

const root = fileURLToPath(new URL("../../", import.meta.url));
const env = await readFile(new URL("../../.env", import.meta.url), "utf8");
const port = env.match(/^API_PORT=(\d+)$/m)?.[1] ?? "8000";
const api = `http://127.0.0.1:${port}/api/v1/health`;
const composeArgs = ["compose", "--env-file", ".env", "-f", "infra/compose.yaml"];

async function compose(...args) {
  // Keep the event loop responsive so fetch can retire idle/closed connections
  // while Docker waits for a service to stop or start.
  try {
    const result = await execFile("docker", [...composeArgs, ...args], {
      cwd: root, encoding: "utf8", timeout: 180000,
    });
    return result.stdout;
  } catch {
    throw new Error(`Compose ${args[0]} failed. Inspect this project's service status.`);
  }
}

async function status(path, expected) {
  const response = await fetch(`${api}/${path}`, { signal: AbortSignal.timeout(15000) });
  assert.equal(response.status, expected, `${path} must return ${expected}`);
  return response.json();
}

async function waitReady() {
  const deadline = Date.now() + 90000;
  while (Date.now() < deadline) {
    try {
      await status("ready", 200);
      return;
    } catch {
      await new Promise((resolve) => setTimeout(resolve, 1500));
    }
  }
  throw new Error("API did not recover within 90 seconds");
}

await status("live", 200);
await waitReady();
console.log("PASS: live and ready return 200 with dependencies running");

// Only this named Compose project's services are affected. Always restore them.
for (const dependency of ["postgres", "redis", "object-storage"]) {
  try {
    await compose("stop", dependency);
    await status("live", 200);
    const result = await status("ready", 503);
    assert.equal(result.error.code, "DEPENDENCY_UNAVAILABLE");
    assert.ok(result.error.request_id);
    console.log(`PASS: ${dependency} stopped -> readiness 503; liveness 200`);
  } finally {
    await compose("start", dependency);
    await waitReady();
  }
  console.log(`PASS: readiness recovers after ${dependency} restart`);
}

const services = await compose("config", "--format", "json");
const config = JSON.parse(services);
for (const name of ["postgres", "redis", "object-storage", "worker"]) {
  assert.equal(config.services[name].ports?.length ?? 0, 0, `${name} must have no published ports`);
}
for (const name of ["frontend", "api"]) {
  assert.ok(config.services[name].ports.every((entry) => entry.host_ip === "127.0.0.1"));
}
console.log("PASS: infrastructure has no published ports; API/frontend bind only to loopback");
