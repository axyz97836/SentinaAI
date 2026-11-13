import type { Metadata } from "next";
import { notFound } from "next/navigation";
import { Workspace } from "../../_components/workspace";
import { PageHeading, Status } from "../../_components/ui";
import { RiskLabel, ScoringEvidence } from "../../_components/transaction-evidence";
import { protectedAPI, requireIdentity } from "../../_lib/protected-api";
import { money, number, timestamp, uuid, type TransactionDetail, type Explanation } from "../../_lib/transactions";

export const metadata: Metadata = { title: "Transaction evidence" };
export default async function Detail({ params, searchParams }: { params: Promise<{ id: string }>; searchParams: Promise<{ received?: string }> }) {
  const identity = await requireIdentity();
  const { id } = await params;
  if (!uuid.test(id)) notFound();
  const [response, evidenceResponse] = await Promise.all([protectedAPI(`transactions/${id}`), protectedAPI(`transactions/${id}/explanation`)]);
  if (response.status === 404 || evidenceResponse.status === 404) notFound();
  const data: TransactionDetail | null = response.ok ? await response.json() : null;
  const evidence: Explanation | null = evidenceResponse.ok ? await evidenceResponse.json() : null;
  const { received } = await searchParams;
  const tx = data?.transaction;
  return <Workspace identity={identity} activeSection="transactions"><div className="tx-page"><a className="tx-back" href="/transactions">← Transactions</a>
    <PageHeading eyebrow="Signal Atlas / Persisted screening" title={tx?.external_id ?? "Transaction evidence"}><p className="muted">Historical evidence from the original scoring event.</p></PageHeading>
    {!data || !tx ? <Status error>Transaction evidence could not be loaded. Reload this page to try again.</Status> : <>
      {received === "replay" && <Status>Already received · The identical transaction is shown below. No duplicate score was created.</Status>}
      {received === "new" && <Status>Transaction received · The persisted score is shown below.</Status>}
      <section className="tx-panel tx-risk" aria-labelledby="risk-heading"><div><p className="eyebrow">Screening score</p><h2 id="risk-heading">{number(data.score.risk_score, 2)} <span>/ 100</span></h2><RiskLabel band={data.score.risk_band} /></div><div><p>This score is a screening signal, not proof of fraud or a calibrated fraud probability.</p><p className="tx-technical">Model {data.score.model_version_id}</p><p className="muted">Scored {timestamp(data.score.scored_at)}</p></div></section>
      <section className="tx-panel" aria-labelledby="identity-heading"><h2 id="identity-heading">Transaction record</h2><dl className="tx-facts">{Object.entries({ "Event (UTC)": timestamp(tx.occurred_at), Amount: money(tx.amount, tx.currency), "Customer reference": tx.customer_ref, "Merchant category": tx.merchant_category, Country: tx.country_code, Channel: tx.channel, "Device reference": tx.device_ref ?? "Not supplied", Source: tx.source, "Transaction ID": tx.id, "Score ID": data.score.id }).map(([label, value]) => <div key={label}><dt>{label}</dt><dd>{value}</dd></div>)}</dl></section>
      {evidence ? <><Status>Explanation {evidence.explanation_status}{evidence.explanation_status === "PARTIAL" ? " · Some rule or feature-attribution evidence is unavailable. Available historical evidence is shown below." : " · Evidence recorded at scoring time."}</Status><ScoringEvidence evidence={evidence} /></> : <Status error>Explanation retrieval is unavailable. The persisted score above remains unchanged. Reload to retry.</Status>}
      {(data.alert_id || data.case_id) && <section className="tx-panel"><h2>Related records</h2><dl className="tx-facts">{data.alert_id && <div><dt>Alert ID</dt><dd>{data.alert_id}</dd></div>}{data.case_id && <div><dt>Case ID</dt><dd>{data.case_id}</dd></div>}</dl><p className="muted">The current API provides identifiers only. Alert and case interfaces are not yet available.</p></section>}
    </>}
  </div></Workspace>;
}
