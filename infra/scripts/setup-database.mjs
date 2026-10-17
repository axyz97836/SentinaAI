import assert from "node:assert/strict";
import { randomBytes } from "node:crypto";
import { spawnSync } from "node:child_process";
import { chmod, mkdir, readFile, writeFile } from "node:fs/promises";
import { fileURLToPath } from "node:url";

const root = fileURLToPath(new URL("../../", import.meta.url));
const base = ["compose", "--env-file", ".env", "-f", "infra/compose.yaml"];
function query(input) {
  const r = spawnSync("docker", [...base, "exec", "-T", "postgres", "sh", "-ec",
    'psql -X -qAt -v ON_ERROR_STOP=1 -U "$POSTGRES_USER" -d "$POSTGRES_DB"'],
  { cwd: root, input, encoding: "utf8", timeout: 30000 });
  if (r.status !== 0) throw new Error("Migration role provisioning failed; secret-bearing output withheld.");
  return r.stdout.trim();
}
function parse(text) {
  return Object.fromEntries(text.split(/\r?\n/).filter(line => /^[A-Z_]+=/.test(line))
    .map(line => { const i = line.indexOf("="); return [line.slice(0, i), line.slice(i + 1)]; }));
}
const env = parse(await readFile(new URL("../../.env", import.meta.url), "utf8"));
assert.match(env.POSTGRES_DB, /^[a-z][a-z0-9_]*$/);
assert.match(env.APP_DB_USER, /^[a-z][a-z0-9_]*$/);
assert.notEqual(env.APP_DB_USER, "sentinel_migrator");
const local = new URL("../../.local/", import.meta.url);
await mkdir(local, { recursive: true, mode: 0o700 });
const file = new URL("migration.env", local);
let values;
try { values = parse(await readFile(file, "utf8")); }
catch (error) {
  if (error.code !== "ENOENT") throw error;
  if (query("SELECT count(*) FROM pg_roles WHERE rolname = 'sentinel_migrator';") !== "0") {
    throw new Error("Migration role already exists but its credential file is missing. Restore that file; credentials were not rotated.");
  }
  values = { APP_ENV: "local", DB_HOST: "postgres", POSTGRES_DB: env.POSTGRES_DB,
    APP_DB_USER: env.APP_DB_USER, MIGRATION_DB_USER: "sentinel_migrator",
    MIGRATION_DB_PASSWORD: randomBytes(32).toString("hex") };
  await writeFile(file, Object.entries(values).map(([key,value]) => `${key}=${value}\n`).join(""),
    { flag: "wx", mode: 0o600 });
}
assert.equal(values.APP_ENV, "local");
assert.equal(values.DB_HOST, "postgres");
assert.equal(values.POSTGRES_DB, env.POSTGRES_DB);
assert.equal(values.APP_DB_USER, env.APP_DB_USER);
assert.equal(values.MIGRATION_DB_USER, "sentinel_migrator");
if (!/^[a-f0-9]{64}$/.test(values.MIGRATION_DB_PASSWORD ?? "")) {
  throw new Error("Invalid migration credential format; existing credentials were preserved.");
}
await chmod(file, 0o600);
const sql = await readFile(new URL("../postgres/provision-migrator.sql", import.meta.url), "utf8");
query(`\\set migration_password '${values.MIGRATION_DB_PASSWORD}'\n${sql}`);
await mkdir(new URL("demo/", local), { recursive: true, mode: 0o700 });
console.log("Dedicated migration role is provisioned. Existing application credentials and privileges are unchanged.");
