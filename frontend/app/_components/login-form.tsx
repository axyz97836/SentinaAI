"use client";

import { useRef, useState, type FormEvent } from "react";
import { authRequest, csrfProof } from "../_lib/auth";
import { Button, Field, Status } from "./ui";
import { useHydrated } from "../_lib/use-hydrated";

export function LoginForm() {
  const hydrated = useHydrated();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [fields, setFields] = useState({ email: "", password: "" });
  const lock = useRef(false);

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (lock.current) return;
    const form = event.currentTarget;
    const data = new FormData(form);
    const email = String(data.get("email") ?? "").trim();
    const password = String(data.get("password") ?? "");
    const invalid = {
      email: /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email) ? "" : "Enter a valid email address.",
      password: password ? "" : "Enter your password.",
    };
    setFields(invalid); setError("");
    if (invalid.email || invalid.password) {
      form.querySelector<HTMLInputElement>(invalid.email ? "#email" : "#password")?.focus();
      return;
    }
    lock.current = true; setBusy(true);
    try {
      const csrf = await csrfProof();
      const response = await authRequest("login", {
        method: "POST", headers: { "Content-Type": "application/json", "X-CSRF-Token": csrf },
        body: JSON.stringify({ email, password }),
      });
      if (response.ok) {
        form.reset();
        // A full navigation drops any stale router/session state after a cookie change.
        window.location.replace("/dashboard");
        return;
      }
      setError(response.status === 401 ? "Email or password is incorrect." : response.status === 429
        ? "Too many sign-in attempts. Wait a few minutes and try again."
        : response.status === 403 ? "Your sign-in request expired. Please try again."
        : "Sign-in is unavailable. Please try again.");
    } catch {
      setError("Could not reach sign-in. Check your connection and try again.");
    } finally {
      lock.current = false; setBusy(false);
    }
  }

  return <form onSubmit={submit} action="/api/v1/auth/login" method="post" noValidate aria-busy={busy}>
    {!hydrated && <p className="status">Enable JavaScript to sign in with session protection.</p>}
    <fieldset disabled={busy || !hydrated}>
      <Field id="email" name="email" label="Email address" type="email" autoComplete="username" maxLength={254} required error={fields.email} />
      <Field id="password" name="password" label="Password" type="password" autoComplete="current-password" maxLength={256} required error={fields.password} />
      {error && <Status error>{error}</Status>}
      <Button type="submit" className="sign-in">{busy ? "Signing in…" : "Sign in to workspace"}<span aria-hidden="true">↗</span></Button>
    </fieldset>
    <p className="form-help">Use the demo account provided by the project owner.<br />Self-registration is not available.</p>
  </form>;
}
