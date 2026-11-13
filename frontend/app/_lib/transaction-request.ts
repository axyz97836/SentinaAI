import { csrfProof } from "./auth";

export async function transactionRequest(path: string, init: RequestInit = {}) {
  const proof = init.method === "POST" ? await csrfProof() : undefined;
  const response = await fetch(`/api/v1/${path}`, {
    ...init, cache: "no-store", credentials: "same-origin",
    signal: init.signal ?? AbortSignal.timeout(20000),
    headers: { ...init.headers, ...(proof ? { "X-CSRF-Token": proof } : {}) },
  });
  if (response.status === 401) { window.location.replace("/login?reason=expired"); throw new Error("Session expired"); }
  return response;
}

export async function responseError(response: Response) {
  const code = (await response.json().catch(() => null))?.error?.code;
  const messages: Record<string, string> = {
    ACTIVE_MODEL_REQUIRED: "An administrator must activate a model before transactions can be scored.",
    DUPLICATE_TRANSACTION_CONFLICT: "This external ID already belongs to a different transaction. Use a new synthetic reference or replay the original fields exactly.",
    VALIDATION_ERROR: "Check the required fields and formats. Use synthetic references and valid currency and country codes.",
    CSRF_REJECTED: "The security proof could not be verified. Reload this page before trying again.",
    PUBLIC_DATASET_NOT_APPROVED: "Public datasets are not approved. Upload synthetic data only.",
    FILE_TOO_LARGE: "The CSV must be no larger than 10 MiB.",
  };
  return messages[code] ?? (response.status === 403 ? "Your account is not authorized for this action." : response.status === 422 ? "The file or fields were rejected. Check the schema and use synthetic data only." : "The request could not be completed. Check your connection and try again.");
}
