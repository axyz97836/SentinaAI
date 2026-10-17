import { randomBytes } from "node:crypto";
import { chmod, mkdir, readFile, writeFile } from "node:fs/promises";
import { fileURLToPath } from "node:url";
import path from "node:path";

const root = fileURLToPath(new URL("../../", import.meta.url));
const envPath = path.join(root, ".env");
const secretNames = ["POSTGRES_PASSWORD", "APP_DB_PASSWORD", "REDIS_PASSWORD", "S3_ACCESS_KEY", "S3_SECRET_KEY"];
let contents;
try {
  contents = await readFile(envPath, "utf8");
} catch (error) {
  if (error.code !== "ENOENT") throw error;
  contents = await readFile(path.join(root, ".env.example"), "utf8");
  for (const name of secretNames) {
    contents = contents.replace(new RegExp(`^${name}=$`, "m"), `${name}=${randomBytes(32).toString("hex")}`);
  }
  await writeFile(envPath, contents, { flag: "wx", mode: 0o600 });
}
const values = Object.fromEntries(contents.split(/\r?\n/).filter((line) => /^[A-Z][A-Z0-9_]*=/.test(line)).map((line) => {
  const index = line.indexOf("=");
  return [line.slice(0, index), line.slice(index + 1)];
}));
for (const name of secretNames) {
  if (!/^[a-f0-9]{64}$/.test(values[name] ?? "")) {
    throw new Error(`${name} must be 64 hexadecimal characters. Existing .env was preserved.`);
  }
}
if (!/^[a-z0-9][a-z0-9-]{1,61}[a-z0-9]$/.test(values.S3_BUCKET ?? "")) {
  throw new Error("S3_BUCKET must be a simple lowercase bucket name.");
}
await chmod(envPath, 0o600);
await mkdir(path.join(root, ".local"), { recursive: true, mode: 0o700 });
const storageConfig = {
  identities: [{
    name: "sentinel-app",
    credentials: [{ accessKey: values.S3_ACCESS_KEY, secretKey: values.S3_SECRET_KEY }],
    actions: ["Read", "Write", "List", "Tagging"].map((action) => `${action}:${values.S3_BUCKET}`),
  }],
};
await writeFile(path.join(root, ".local/seaweedfs.json"), JSON.stringify(storageConfig), { mode: 0o600 });
console.log("Local environment is ready. Secrets remain in ignored files and were not printed.");
