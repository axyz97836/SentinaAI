"use client";

import { useEffect, useRef, useState, type FormEvent } from "react";
import { transactionRequest, responseError } from "../_lib/transaction-request";
import { type IngestionJob, uuid, readable } from "../_lib/transactions";
import { useHydrated } from "../_lib/use-hydrated";
import { Button, Status } from "./ui";

export function TransactionUpload({ admin, initialJob }: { admin: boolean; initialJob: string }) {
  const hydrated = useHydrated();
  const pending = useRef(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [jobId, setJobId] = useState(() => {
    // Session revalidation remounts children; keep the accepted job across hiding.
    if (typeof window === "undefined") return initialJob;
    const saved = new URL(window.location.href).searchParams.get("job");
    return saved && uuid.test(saved) ? saved : initialJob;
  });
  const [job, setJob] = useState<IngestionJob | null>(null);
  const [pollError, setPollError] = useState("");
  const [refresh, setRefresh] = useState(0);
  const terminal = job?.status === "SUCCEEDED" || job?.status === "FAILED";

  useEffect(() => {
    if (!jobId) return;
    let stopped = false;
    let finished = false;
    let timer: ReturnType<typeof setTimeout> | undefined;
    let controller: AbortController | undefined;
    async function poll() {
      if (stopped || finished || document.hidden) return;
      const current = new AbortController(); controller = current;
      try {
        const response = await transactionRequest(`jobs/${jobId}`, { signal: AbortSignal.any([current.signal, AbortSignal.timeout(10000)]) });
        if (!response.ok) throw new Error("Job unavailable");
        const next: IngestionJob = await response.json();
        if (next.type !== "CSV_IMPORT") throw new Error("Not an ingestion job");
        if (stopped || current.signal.aborted) return;
        setJob(next); setPollError("");
        finished = ["SUCCEEDED", "FAILED"].includes(next.status);
        if (!finished) timer = setTimeout(poll, 2000);
      } catch {
        if (!stopped && !current.signal.aborted) setPollError("Job status is unavailable. Retry status retrieval; do not upload the file again. A job may still be running.");
      }
    }
    const visibility = () => { clearTimeout(timer); controller?.abort(); if (!document.hidden) void poll(); };
    void poll(); document.addEventListener("visibilitychange", visibility);
    return () => { stopped = true; clearTimeout(timer); controller?.abort(); document.removeEventListener("visibilitychange", visibility); };
  }, [jobId, refresh]);

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (pending.current) return;
    const data = new FormData(event.currentTarget);
    const file = data.get("file") as File;
    setError("");
    if (!file.size || file.size > 10 * 1024 * 1024 || !file.name.toLowerCase().endsWith(".csv")) { setError("Choose a nonempty CSV file no larger than 10 MiB."); return; }
    data.set("source_kind", "SYNTHETIC");
    pending.current = true; setBusy(true);
    try {
      const response = await transactionRequest("ingestions", { method: "POST", body: data });
      if (!response.ok) { setError(await responseError(response)); return; }
      const result = await response.json();
      if (!uuid.test(result.job_id)) throw new Error("Invalid job response");
      setJob(null); setPollError(""); setJobId(result.job_id);
      window.history.replaceState(null, "", `/transactions/upload?job=${result.job_id}`);
    } catch { setError("Upload acceptance could not be confirmed. Do not automatically resubmit: a job may already exist. Ask an administrator to check before retrying."); }
    finally { pending.current = false; setBusy(false); }
  }

  return <>
    <section className="tx-panel" aria-labelledby="upload-heading"><h2 id="upload-heading">Submit a synthetic CSV</h2><p className="muted" id="upload-guidance">Maximum 10 MiB and 10,000 rows. Public datasets are not approved by the current backend policy. Never upload personal or real financial records.</p>
      <form onSubmit={submit} aria-describedby="upload-guidance"><fieldset disabled={busy || !hydrated || Boolean(jobId && !terminal)}>
        <div className="field"><label htmlFor="csv">CSV file</label><input id="csv" name="file" type="file" accept=".csv,text/csv" required /></div>
        <div className="field"><label htmlFor="purpose">Dataset purpose</label><select id="purpose" name="purpose" aria-describedby="purpose-help"><option value="SCORING">Scoring</option>{admin && <option value="TRAINING">Training (ADMIN only)</option>}</select></div>
        <p className="form-help" id="purpose-help">Scoring creates operational transactions. Training is restricted to administrators and validates a dataset only; it does not score transactions or activate a model.</p>
        <label className="tx-checkbox"><input type="checkbox" required /> I confirm this file contains synthetic data only.</label>
        <Button type="submit">{busy ? "Submitting CSV…" : "Upload CSV"}</Button>
      </fieldset>{error && <Status error>{error}</Status>}</form>
      <noscript><p className="status">JavaScript is required for secure upload and job tracking.</p></noscript>
      <details><summary>Required CSV schema</summary><p className="tx-technical">external_id, customer_ref, occurred_at, amount, currency, merchant_category, country_code, channel</p><p>Optional: device_ref and fraud_label (0 or 1). Model training later requires both label classes; uploading alone does not train a model. Use UTC timestamps such as 2026-02-01T10:00:00Z, positive amounts with up to two decimals, ISO currency/country codes, and WEB, MOBILE or POS channels. References must be fictional; no seven consecutive digits.</p></details>
    </section>
    {jobId && <section className="tx-panel" aria-labelledby="job-heading"><p className="eyebrow">Durable processing</p><h2 id="job-heading">Ingestion job</h2><p className="tx-technical">{jobId}</p><p className="muted">Bookmark this page to return to the persisted job. Updates pause when this tab is hidden.</p>
      {pollError && <><Status error>{pollError}</Status><Button className="secondary" onClick={() => { setPollError(""); setRefresh(value => value + 1); }}>Retry status</Button></>}
      {!job && !pollError && <Status>Retrieving persisted job status…</Status>}
      {job && <><div className="tx-job-status" data-state={job.status === "SUCCEEDED" && job.failed_rows > 0 ? "ROW_ERRORS" : job.status}><Status error={job.status === "FAILED"}>{job.status === "SUCCEEDED" && job.failed_rows > 0 ? "Completed with row errors" : job.status} · {readable(job.progress_phase)}</Status></div>
        <dl className="tx-job-metrics"><div><dt>Total rows</dt><dd>{job.total_rows ?? "Not counted yet"}</dd></div><div><dt>Processed rows</dt><dd>{job.processed_rows}</dd></div><div><dt>Failed rows</dt><dd>{job.failed_rows}</dd></div><div><dt>Attempts</dt><dd>{job.attempt_count}</dd></div></dl><p className="tx-technical">Dataset ID · {job.dataset_id}</p>
        {job.status === "SUCCEEDED" && <p>{job.progress_phase === "SCORING" ? job.processed_rows > 0 ? "Scoring finished. Accepted rows are available in Transactions." : "No rows were accepted for scoring. Review the row errors before submitting a corrected file." : "Dataset validation finished. This upload did not create scored transactions."}</p>}
        {job.error_code && <Status error>{job.error_code}: {job.error_message}</Status>}
        {job.cleanup_pending && <p className="status">Private-file cleanup is pending.</p>}
        {job.errors.length > 0 && <section className="tx-row-errors" aria-labelledby="row-errors-heading"><h3 id="row-errors-heading">Row errors</h3><ul className="tx-limitations">{job.errors.slice(0, 100).map((item, index) => <li key={index}>Row {item.row_number} · <code>{item.code}</code>: {item.summary}</li>)}</ul><p className="form-help">At most 100 sanitized errors are shown. Correct rejected rows before submitting a new file.</p></section>}
        {terminal && <a className="button secondary" href="/transactions">View transactions</a>}
      </>}
    </section>}
  </>;
}
