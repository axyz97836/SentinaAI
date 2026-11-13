import "server-only";
import { cookies } from "next/headers";
import { redirect } from "next/navigation";
import { readSession } from "./session";

export async function requireIdentity() {
  const identity = await readSession();
  if (!identity) redirect("/login?reason=expired");
  return identity;
}

export async function protectedAPI(path: string) {
  const jar = await cookies();
  const cookie = jar.get("__Host-sentinel_session") ?? jar.get("sentinel_session");
  if (!cookie) redirect("/login?reason=expired");
  const api = process.env.API_INTERNAL_URL ?? "http://127.0.0.1:8000";
  const response = await fetch(`${api}/api/v1/${path}`, {
    headers: { Cookie: `${cookie.name}=${cookie.value}` }, cache: "no-store", signal: AbortSignal.timeout(10000),
  });
  if (response.status === 401) redirect("/login?reason=expired");
  return response;
}
