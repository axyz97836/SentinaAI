import { randomBytes } from "node:crypto";
import { spawn } from "node:child_process";
import { chmod, mkdir, readFile, writeFile } from "node:fs/promises";
import { fileURLToPath } from "node:url";

const root = fileURLToPath(new URL("../../", import.meta.url));
const args = ["compose", "--progress", "plain", "-p", "sentinelai-db-tests",
  "-f", "infra/compose.database-tests.yaml"];
const envFile = new URL("../../.local/database-tests.env", import.meta.url);
await mkdir(new URL("../../.local/", import.meta.url), { recursive: true, mode: 0o700 });
let env;
try { env = await readFile(envFile, "utf8"); }
catch (error) {
  if (error.code !== "ENOENT") throw error;
  const values = { POSTGRES_DB: "sentinelai_schema_test", POSTGRES_USER: "sentinel_test_owner",
    APP_DB_USER: "sentinel_app", MIGRATION_DB_USER: "sentinel_migrator" };
  for (const key of ["POSTGRES_PASSWORD", "APP_DB_PASSWORD", "MIGRATION_DB_PASSWORD",
    "REDIS_PASSWORD", "S3_ACCESS_KEY", "S3_SECRET_KEY"]) values[key] = randomBytes(32).toString("hex");
  env = Object.entries(values).map(([k,v]) => `${k}=${v}\n`).join("");
  await writeFile(envFile, env, { flag: "wx", mode: 0o600 });
}
await chmod(envFile, 0o600);
if (!/^POSTGRES_DB=sentinelai_schema_test$/m.test(env)) throw new Error("Unsafe test database target");
const secrets = [...env.matchAll(/^(?:.*PASSWORD|S3_ACCESS_KEY|S3_SECRET_KEY)=(.+)$/gm)].map(m => m[1]);
const password = env.match(/^MIGRATION_DB_PASSWORD=([a-f0-9]{64})$/m)?.[1];
if (!password) throw new Error("Invalid test migration credential format");
const sanitize = value => secrets.reduce((s, secret) => s.replaceAll(secret, "[REDACTED]"), value)
  .replace(/\$argon2id\$[^\s'"\],)]+/g, "[REDACTED_HASH]");
async function compose(command, input) {
  return new Promise((resolve, reject) => {
    const child = spawn("docker", [...args, ...command], { cwd: root, stdio: ["pipe", "pipe", "pipe"] });
    // Buffer output so a credential spanning stream chunks cannot evade redaction.
    let output = "";
    child.stdout.on("data", data => { output += data; });
    child.stderr.on("data", data => { output += data; });
    child.on("error", reject);
    child.on("close", code => {
      process.stdout.write(sanitize(output));
      code === 0 ? resolve() : reject(new Error(`Database verification command failed (${code})`));
    });
    child.stdin.end(input);
  });
}
try {
  await compose(["up", "-d", "--build", "--wait", "database-test"]);
  const sql = await readFile(new URL("../postgres/provision-migrator.sql", import.meta.url), "utf8");
  await compose(["exec", "-T", "database-test", "sh", "-ec",
    'psql -X -qAt -v ON_ERROR_STOP=1 -U "$POSTGRES_USER" -d "$POSTGRES_DB"'],
    `\\set migration_password '${password}'\n${sql}`);
  await compose(["build", "database-checks"]);
  await compose(["run", "--rm", "--no-deps", "database-checks"]);
} finally {
  await compose(["down", "--volumes", "--remove-orphans"]);
}
