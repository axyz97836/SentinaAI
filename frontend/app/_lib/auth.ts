export type Identity = {
  user: { id: string; email: string; display_name: string };
  organization: { id: string; name: string };
  role: "ANALYST" | "RISK_MANAGER" | "ADMIN";
};

export const roleLabels: Record<Identity["role"], string> = {
  ANALYST: "Fraud analyst", RISK_MANAGER: "Risk manager", ADMIN: "Administrator",
};

export function authRequest(path: string, init?: RequestInit) {
  return fetch(`/api/v1/auth/${path}`, {
    ...init, cache: "no-store", credentials: "same-origin", signal: AbortSignal.timeout(10000),
  });
}

export async function csrfProof(): Promise<string> {
  const response = await authRequest("csrf");
  if (!response.ok) throw new Error("Authentication is unavailable.");
  const body = await response.json();
  if (typeof body.csrf_token !== "string") throw new Error("Authentication is unavailable.");
  return body.csrf_token;
}
