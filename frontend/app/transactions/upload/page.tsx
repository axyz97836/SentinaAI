import type { Metadata } from "next";
import { Workspace } from "../../_components/workspace";
import { PageHeading, Status } from "../../_components/ui";
import { TransactionUpload } from "../../_components/transaction-upload";
import { requireIdentity } from "../../_lib/protected-api";
import { uuid } from "../../_lib/transactions";

export const metadata: Metadata = { title: "Upload transactions" };
export default async function Upload({ searchParams }: { searchParams: Promise<{ job?: string }> }) {
  const identity = await requireIdentity();
  const { job } = await searchParams;
  const valid = typeof job === "string" && uuid.test(job);
  return <Workspace identity={identity} activeSection="transactions"><div className="tx-page"><a className="tx-back" href="/transactions">← Transactions</a>
    <PageHeading eyebrow="Signal Atlas / Synthetic ingestion" title="Upload CSV"><p className="muted">Validate a synthetic file and follow its durable processing record.</p></PageHeading>
    {job && !valid && <Status error>The job reference is invalid. Open the original saved job URL.</Status>}
    <TransactionUpload admin={identity.role === "ADMIN"} initialJob={valid ? job : ""} />
  </div></Workspace>;
}
