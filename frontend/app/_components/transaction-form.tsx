"use client";

import { useRef, useState, type FormEvent } from "react";
import { transactionRequest, responseError } from "../_lib/transaction-request";
import { useHydrated } from "../_lib/use-hydrated";
import { uuid } from "../_lib/transactions";
import { Button, Field, Status } from "./ui";

const reference = "[A-Za-z0-9][A-Za-z0-9_.\\-]*";
export function TransactionForm({ initialOpen = false }: { initialOpen?: boolean }) {
  const hydrated = useHydrated();
  const [open, setOpen] = useState(initialOpen);
  const trigger = useRef<HTMLButtonElement>(null);
  const panel = useRef<HTMLDivElement>(null);
  function toggle() {
    setOpen(!open);
    if (!open) requestAnimationFrame(() => panel.current?.querySelector("input")?.focus());
    else trigger.current?.focus();
  }
  const pending = useRef(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [fieldErrors, setFieldErrors] = useState<Record<string, string>>({});

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (pending.current) return;
    const values = Object.fromEntries(new FormData(event.currentTarget)) as Record<string, string>;
    const errors: Record<string, string> = {};
    for (const field of ["external_id", "customer_ref", "device_ref", "merchant_category"]) {
      if (/\d{7}/.test(values[field])) errors[field] = "Use a synthetic reference without seven consecutive digits.";
    }
    if (!/^\d{1,12}(\.\d{1,2})?$/.test(values.amount) || Number(values.amount) <= 0) errors.amount = "Enter an amount greater than zero, with up to 12 whole digits and 2 decimal places.";
    const stamp = new Date(`${values.occurred_at}Z`);
    if (!Number.isFinite(stamp.getTime())) errors.occurred_at = "Enter a valid UTC event date and time.";
    setFieldErrors(errors); setError("");
    if (Object.keys(errors).length) {
      event.currentTarget.querySelector<HTMLInputElement>(`[name="${Object.keys(errors)[0]}"]`)?.focus(); return;
    }
    pending.current = true; setBusy(true);
    try {
      const response = await transactionRequest("transactions", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ ...values, occurred_at: stamp.toISOString(), device_ref: values.device_ref || null }) });
      if (!response.ok) { setError(await responseError(response)); return; }
      const result = await response.json();
      if (!uuid.test(result.transaction_id)) throw new Error("Invalid response");
      window.location.assign(`/transactions/${result.transaction_id}?received=${response.status === 200 ? "replay" : "new"}`);
    } catch { setError("Submission could not be confirmed. Check your connection, then retry with the same external ID and fields to safely check for an identical replay."); }
    finally { pending.current = false; setBusy(false); }
  }

  return <><div className="tx-actions"><button ref={trigger} className="button" type="button" disabled={!hydrated || busy} aria-expanded={open} aria-controls="transaction-form-panel" onClick={toggle}>New simulated transaction</button><a className="button secondary" href="/transactions/upload">Upload CSV</a></div>
  <div ref={panel} id="transaction-form-panel" hidden={!open}><section className="tx-panel" aria-labelledby="new-heading"><p className="eyebrow">Synthetic input</p><h2 id="new-heading">New simulated transaction</h2><p className="muted" id="synthetic-guidance">Use fictional references only. Never enter real customer, account, card or payment information. Event times are UTC.</p>
    <form onSubmit={submit} aria-describedby="synthetic-guidance"><fieldset disabled={busy || !hydrated} className="tx-form-grid">
      <Field id="external_id" name="external_id" label="External reference" required maxLength={100} pattern={reference} title="Letters, numbers, underscores, dots and hyphens; start with a letter or number." error={fieldErrors.external_id} />
      <Field id="customer_ref" name="customer_ref" label="Synthetic customer reference" required maxLength={100} pattern={reference} error={fieldErrors.customer_ref} />
      <Field id="occurred_at" name="occurred_at" label="Event date and time (UTC)" type="datetime-local" required step="1" error={fieldErrors.occurred_at} />
      <Field id="amount" name="amount" label="Amount" required inputMode="decimal" error={fieldErrors.amount} />
      <Field id="currency" name="currency" label="Currency (ISO code, e.g. INR)" required pattern="[A-Z]{3}" maxLength={3} />
      <Field id="merchant_category" name="merchant_category" label="Merchant category" required maxLength={80} pattern={"[A-Za-z0-9][A-Za-z0-9 ._\\-]*"} error={fieldErrors.merchant_category} />
      <Field id="country_code" name="country_code" label="Country (ISO code, e.g. IN)" required pattern="[A-Z]{2}" maxLength={2} />
      <div className="field"><label htmlFor="channel">Channel</label><select id="channel" name="channel" required><option value="WEB">Web</option><option value="MOBILE">Mobile</option><option value="POS">Point of sale</option></select></div>
      <Field id="device_ref" name="device_ref" label="Synthetic device reference (optional)" maxLength={100} pattern={reference} error={fieldErrors.device_ref} />
      <div className="tx-form-actions"><Button type="submit">{busy ? "Scoring transaction…" : "Submit for scoring"}</Button><Button type="button" className="secondary" onClick={toggle}>Close form</Button></div>
    </fieldset>{error && <Status error>{error}</Status>}</form>
    <noscript><p className="status">JavaScript is required to submit a transaction securely.</p></noscript>
  </section></div></>;
}
