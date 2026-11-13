import type { Metadata } from "next";
import { Workspace } from "../_components/workspace";
import { PageHeading, Status } from "../_components/ui";
import { TransactionRows } from "../_components/transaction-evidence";
import { TransactionForm } from "../_components/transaction-form";
import { TransactionFilters } from "../_components/transaction-filters";
import { protectedAPI, requireIdentity } from "../_lib/protected-api";
import type { TransactionList } from "../_lib/transactions";

export const metadata: Metadata = { title: "Transactions" };
export default async function Transactions({ searchParams }: { searchParams: Promise<Record<string, string | string[] | undefined>> }) {
  const identity = await requireIdentity();
  const params = await searchParams;
  const value = (key: string) => typeof params[key] === "string" ? params[key] as string : "";
  const query = new URLSearchParams();
  for (const key of ["search", "risk_band", "cursor", "limit"]) if (value(key)) query.set(key, value(key));
  for (const key of ["date_from", "date_to"]) if (value(key)) query.set(key, `${value(key)}T00:00:00Z`);
  const response = await protectedAPI(`transactions?${query}`);
  const data: TransactionList | null = response.ok ? await response.json() : null;
  const next = new URLSearchParams();
  for (const key of ["search", "risk_band", "date_from", "date_to", "limit"]) if (value(key)) next.set(key, value(key));
  const first = `/transactions?${next}`;
  if (data?.next_cursor) next.set("cursor", data.next_cursor);
  return <Workspace identity={identity} activeSection="transactions"><div className="tx-page">
    <PageHeading eyebrow="Signal Atlas / Transaction evidence" title="Transactions"><p className="muted">Explore organization-scoped synthetic transactions and their persisted screening evidence.</p></PageHeading>
    <TransactionForm initialOpen={value("new") === "1"} />
    <TransactionFilters active={Boolean(value("search") || value("risk_band") || value("date_from") || value("date_to"))} needsAttention={!response.ok}>
      <div className="field"><label htmlFor="search">Search reference or customer</label><input id="search" name="search" defaultValue={value("search")} maxLength={100} pattern={"[A-Za-z0-9][A-Za-z0-9_.\\-]*"} title="Use letters, numbers, dots, underscores or hyphens. Search is case sensitive." /></div>
      <div className="field"><label htmlFor="risk_band">Risk band</label><select id="risk_band" name="risk_band" defaultValue={value("risk_band")}><option value="">All bands</option>{["LOW", "MEDIUM", "HIGH", "CRITICAL"].map(band => <option key={band}>{band}</option>)}</select></div>
      <div className="field"><label htmlFor="date_from">From date (UTC, inclusive)</label><input id="date_from" name="date_from" type="date" defaultValue={value("date_from")} /></div>
      <div className="field"><label htmlFor="date_to">Before date (UTC, exclusive)</label><input id="date_to" name="date_to" type="date" defaultValue={value("date_to")} /></div>
      <div className="field"><label htmlFor="limit">Rows per page</label><select id="limit" name="limit" defaultValue={value("limit") || "20"}>{[10, 20, 50].map(count => <option key={count}>{count}</option>)}</select></div>
    </TransactionFilters>
    {!data ? <Status error>{response.status === 422 ? "The filters or pagination cursor are invalid. Check the reference format and use an increasing date range, or clear the filters." : "Transactions could not be loaded. Reload this page to try again."}</Status> : data.items.length ? <>
      <div className="tx-list-heading"><h2>Recorded transactions</h2><p className="muted">{data.items.length} on this page · newest event first</p></div><TransactionRows items={data.items} />
      <nav className="tx-pagination" aria-label="Transaction pages">{value("cursor") && <a className="button secondary" href={first}>First page</a>}{data.next_cursor && <a className="button secondary" href={`/transactions?${next}`}>Next page</a>}</nav>
    </> : <section className="tx-panel"><h2>No matching transactions</h2><p className="muted">Adjust the filters, submit a simulated transaction or upload a synthetic scoring CSV. No sample records have been invented.</p></section>}
  </div></Workspace>;
}
