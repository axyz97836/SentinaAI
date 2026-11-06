import "server-only";
import { cookies } from "next/headers";
import type { Identity } from "./auth";

export async function readSession(): Promise<Identity | null> {
  const jar = await cookies();
  const cookie = jar.get("__Host-sentinel_session") ?? jar.get("sentinel_session");
  if (!cookie) return null;
  const api = process.env.API_INTERNAL_URL ?? "http://127.0.0.1:8000";
  const response = await fetch(`${api}/api/v1/auth/me`, {
    headers: { Cookie: `${cookie.name}=${cookie.value}` },
    cache: "no-store", signal: AbortSignal.timeout(10000),
  });
  if (response.status === 401) return null;
  if (!response.ok) throw new Error("Session verification is unavailable.");
  return response.json() as Promise<Identity>;
}
