"use client";

import { useState, type ReactNode } from "react";
import { Status } from "./ui";
import { ResponsiveDisclosure } from "./responsive-disclosure";

export function TransactionFilters({ children, active, needsAttention }: { children: ReactNode; active: boolean; needsAttention: boolean }) {
  const [pending, setPending] = useState(false);
  return <ResponsiveDisclosure id="transaction-filters" title={active ? "Filters · active" : "Filters"} mobileOpen={active || needsAttention} className="tx-panel tx-filter-disclosure"><form className="tx-filters" action="/transactions" method="get" aria-label="Transaction filters" aria-busy={pending} onSubmit={() => setPending(true)}>
    {children}
    <div className="tx-actions"><button className="button" type="submit" disabled={pending}>{pending ? "Loading transactions…" : "Apply filters"}</button><a href="/transactions">Clear filters</a></div>
    {pending && <Status>Loading matching transactions…</Status>}
  </form></ResponsiveDisclosure>;
}
