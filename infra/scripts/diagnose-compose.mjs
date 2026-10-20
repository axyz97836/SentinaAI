// Failure-only diagnostics. Never print resolved Compose config or container env.
import { spawnSync } from "node:child_process";
import { readFile } from "node:fs/promises";
import { fileURLToPath } from "node:url";

const root = fileURLToPath(new URL("../../", import.meta.url));
const compose = ["compose", "--env-file", ".env", "-f", "infra/compose.yaml"];
const secrets = new Set();
for (const file of [".env", ".local/auth.env", ".local/migration.env", ".local/database-tests.env"]) {
  try {
    const body = await readFile(new URL(`../../${file}`, import.meta.url), "utf8");
    for (const match of body.matchAll(/^(?:.*PASSWORD|AUTH_SECRET|S3_ACCESS_KEY|S3_SECRET_KEY)=(.+)$/gm)) {
      secrets.add(match[1]);
    }
  } catch (error) {
    if (error.code !== "ENOENT") throw new Error("Cannot read redaction input; diagnostics withheld.");
  }
}
try {
  const demo = JSON.parse(await readFile(new URL("../../.local/demo/credentials.json", import.meta.url), "utf8"));
  for (const value of Object.values(demo.accounts)) secrets.add(value);
} catch (error) {
  if (error.code !== "ENOENT") throw new Error("Cannot read demo redaction input; diagnostics withheld.");
}

const redact = value => [...secrets].reduce((text, secret) => text.replaceAll(secret, "[REDACTED]"), value)
  .replace(/\$argon2id\$[^\s'"\],)]+/g, "[REDACTED_HASH]");
function docker(args) {
  const result = spawnSync("docker", args, { cwd: root, encoding: "utf8", timeout: 15000, maxBuffer: 8 * 1024 * 1024 });
  if (result.status !== 0) {
    console.log(`Diagnostic command ${args[0]} did not complete successfully.`);
    return "";
  }
  return result.stdout;
}

console.log(redact(docker([...compose, "ps", "--all"])));
const ids = docker([...compose, "ps", "--all", "--quiet"]).trim().split(/\s+/).filter(Boolean);
for (const id of ids) {
  const raw = docker(["inspect", id]);
  if (!raw) continue;
  const [container] = JSON.parse(raw);
  console.log(redact(JSON.stringify({
    service: container.Config.Labels["com.docker.compose.service"],
    status: container.State.Status, exitCode: container.State.ExitCode,
    oomKilled: container.State.OOMKilled, restartCount: container.RestartCount,
    health: container.State.Health,
  })));
}
console.log(redact(docker([...compose, "logs", "--no-color", "--tail", "100"])));
