// A separate signing key: preserve all existing infrastructure/demo credentials.
import { randomBytes } from "node:crypto";
import { chmod, lstat, mkdir, readFile, writeFile } from "node:fs/promises";

const directory = new URL("../../.local/", import.meta.url);
const file = new URL("auth.env", directory);
await mkdir(directory, { recursive: true, mode: 0o700 });
try {
  const info = await lstat(file);
  if (!info.isFile() || info.isSymbolicLink()) throw new Error("Auth configuration must be a regular file");
  const existing = await readFile(file, "utf8");
  if (!/^AUTH_SECRET=[a-f0-9]{64}\n$/.test(existing)) throw new Error("Invalid auth configuration; refusing to replace it");
  await chmod(file, 0o600);
  console.log("Existing local authentication signing key preserved.");
} catch (error) {
  if (error.code !== "ENOENT") throw error;
  await writeFile(file, `AUTH_SECRET=${randomBytes(32).toString("hex")}\n`, { flag: "wx", mode: 0o600 });
  console.log("Created private local authentication signing key (0600).");
}
